"""One-time migration: convert the single-tenant schema to multi-tenant.

This app used to assume exactly one business. It now supports multiple
organizations sharing the same database, isolated by a new `org_id` column
on `admin_users`, `employees`, and `report_log`. This script performs that
conversion against an existing (pre-migration) database, seeding the
current live business (Linton Business Solutions / LBSconnect) as the
first organization, with zero data loss.

IMPORTANT - run this BEFORE deploying any app code that expects org_id to
exist. This script only touches the database; the currently-deployed app
code is completely unaffected by it, so it's always safe to run against a
still-running old-schema app. Do NOT deploy new app code (that expects
org_id) until this script's backfill (--dry-run then real run) has
completed and been verified.

Usage (run from the project root, e.g. in Render's Shell):
    python3 migrate_to_multitenant.py --backfill --company-code lbsconnect \
        --company-name "Linton Business Solutions" \
        --report-recipients info@lbsconnect.net --dry-run

    python3 migrate_to_multitenant.py --backfill --company-code lbsconnect \
        --company-name "Linton Business Solutions" \
        --report-recipients info@lbsconnect.net

    # Only after new org-aware app code is deployed and verified working:
    python3 migrate_to_multitenant.py --lock-constraints
"""
import argparse

from models import get_db
from orgs import normalize_company_code, is_valid_company_code


def _backfill(args):
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                company_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'America/Chicago',
                default_hourly_rate REAL NOT NULL DEFAULT 16.00,
                report_recipients TEXT,
                report_hour INTEGER NOT NULL DEFAULT 17,
                report_minute INTEGER NOT NULL DEFAULT 0,
                report_weekday INTEGER NOT NULL DEFAULT 4,
                plan TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id)")
        conn.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id)")
        conn.execute("ALTER TABLE report_log ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id)")
        conn.commit()
        print("Schema check: organizations table exists, org_id columns present (nullable).")

        code = normalize_company_code(args.company_code)
        if not is_valid_company_code(code):
            raise SystemExit(
                f"Invalid --company-code '{args.company_code}': must be 3-32 chars, "
                "lowercase letters/numbers/hyphens only."
            )

        existing_org = conn.execute(
            "SELECT * FROM organizations WHERE company_code=%s", (code,)
        ).fetchone()
        if existing_org:
            org_id = existing_org["id"]
            print(f"Organization '{code}' already exists (id={org_id}); reusing it.")
        else:
            if args.dry_run:
                print(f"[dry-run] Would insert organization: company_code={code!r}, "
                      f"name={args.company_name!r}, report_recipients={args.report_recipients!r}")
                org_id = None
            else:
                row = conn.execute(
                    """
                    INSERT INTO organizations
                        (company_code, name, report_recipients)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (code, args.company_name, args.report_recipients),
                ).fetchone()
                conn.commit()
                org_id = row["id"]
                print(f"Created organization '{code}' (id={org_id}).")

        for table in ("admin_users", "employees", "report_log"):
            count = conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE org_id IS NULL").fetchone()["c"]
            if args.dry_run:
                print(f"[dry-run] Would backfill org_id on {count} row(s) in {table}.")
            elif org_id is not None:
                conn.execute(f"UPDATE {table} SET org_id=%s WHERE org_id IS NULL", (org_id,))
                conn.commit()
                print(f"Backfilled org_id on {count} row(s) in {table}.")

        if not args.dry_run:
            print("\nVerification:")
            for table in ("admin_users", "employees", "report_log"):
                remaining = conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE org_id IS NULL").fetchone()["c"]
                print(f"  {table}: {remaining} row(s) still missing org_id (expect 0)")
            emp_count = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
            entry_count = conn.execute("SELECT COUNT(*) AS c FROM time_entries").fetchone()["c"]
            print(f"  employees total: {emp_count} (compare to your pre-migration count)")
            print(f"  time_entries total: {entry_count} (compare to your pre-migration count - untouched by this script)")
            print(f"\nDone. Company Code for '{args.company_name}' is: {code}")
            print("Next: deploy the new org-aware app code, verify it works, THEN run "
                  "'python3 migrate_to_multitenant.py --lock-constraints'.")


def _lock_constraints():
    with get_db() as conn:
        for table, unique_cols, old_col in (
            ("admin_users", "org_id, username", "username"),
            ("employees", "org_id, employee_code", "employee_code"),
            ("report_log", "org_id, report_date", "report_date"),
        ):
            conn.execute(f"ALTER TABLE {table} ALTER COLUMN org_id SET NOT NULL")
            conn.execute(f"""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE table_name = '{table}' AND constraint_name = '{table}_{old_col}_key'
                    ) THEN
                        ALTER TABLE {table} DROP CONSTRAINT {table}_{old_col}_key;
                    END IF;
                END $$;
            """)
            conn.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.table_constraints
                        WHERE table_name = '{table}' AND constraint_name = '{table}_org_{old_col}_key'
                    ) THEN
                        ALTER TABLE {table} ADD CONSTRAINT {table}_org_{old_col}_key UNIQUE ({unique_cols});
                    END IF;
                END $$;
            """)
            conn.commit()
            print(f"{table}: org_id is NOT NULL, composite unique ({unique_cols}) in place, old global unique dropped.")
    print("\nDone. Schema is now fully multi-tenant.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backfill", action="store_true",
                         help="Create organizations table, add nullable org_id columns, seed the "
                              "given org, and backfill org_id onto existing rows.")
    parser.add_argument("--lock-constraints", action="store_true",
                         help="Set org_id NOT NULL and swap old global unique constraints for "
                              "composite (org_id, ...) ones. Run ONLY after new app code is deployed "
                              "and verified working against the backfilled data.")
    parser.add_argument("--company-code", help="Required with --backfill, e.g. 'lbsconnect'.")
    parser.add_argument("--company-name", help="Required with --backfill, e.g. 'Linton Business Solutions'.")
    parser.add_argument("--report-recipients", default="",
                         help="Comma-separated recipient email(s) for the weekly report.")
    parser.add_argument("--dry-run", action="store_true", help="Show what --backfill would do without writing.")
    args = parser.parse_args()

    if args.backfill:
        if not args.company_code or not args.company_name:
            raise SystemExit("--backfill requires --company-code and --company-name.")
        _backfill(args)
    elif args.lock_constraints:
        _lock_constraints()
    else:
        raise SystemExit("Specify --backfill or --lock-constraints. See --help.")


if __name__ == "__main__":
    main()
