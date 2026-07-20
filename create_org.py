"""Manually provision a new tenant organization.

Self-serve signup is intentionally not exposed as a public route (see the
multi-tenant migration plan) - creating a new org is an off-band action run
by whoever operates the platform. This script does that: it creates an
`organizations` row with the given company code and settings. The new
tenant's first admin account is then created by that org's own admin
visiting /admin/setup with the company code you give them here.

Usage:
    python3 create_org.py --company-code acme --company-name "Acme Corp" \
        --report-recipients payroll@acme.example.com \
        [--timezone America/New_York] [--default-hourly-rate 18.00] \
        [--report-weekday 4] [--report-hour 17] [--report-minute 0]
"""
import argparse

from models import get_db
from orgs import normalize_company_code, is_valid_company_code

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-code", required=True)
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--report-recipients", required=True,
                         help="Comma-separated recipient email(s) for this org's weekly report.")
    parser.add_argument("--timezone", default="America/Chicago",
                         help="IANA timezone name, e.g. America/Chicago, America/New_York.")
    parser.add_argument("--default-hourly-rate", type=float, default=16.00)
    parser.add_argument("--report-weekday", type=int, default=4, choices=range(7),
                         help="0=Monday .. 6=Sunday (default 4 = Friday).")
    parser.add_argument("--report-hour", type=int, default=17, choices=range(24))
    parser.add_argument("--report-minute", type=int, default=0, choices=range(60))
    args = parser.parse_args()

    code = normalize_company_code(args.company_code)
    if not is_valid_company_code(code):
        raise SystemExit(
            f"Invalid --company-code '{args.company_code}': must be 3-32 chars, "
            "lowercase letters/numbers/hyphens only."
        )

    with get_db() as conn:
        existing = conn.execute("SELECT id FROM organizations WHERE company_code=%s", (code,)).fetchone()
        if existing:
            raise SystemExit(f"An organization with company_code '{code}' already exists (id={existing['id']}).")

        row = conn.execute(
            """
            INSERT INTO organizations
                (company_code, name, timezone, default_hourly_rate, report_recipients,
                 report_weekday, report_hour, report_minute)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (code, args.company_name, args.timezone, args.default_hourly_rate, args.report_recipients,
             args.report_weekday, args.report_hour, args.report_minute),
        ).fetchone()
        conn.commit()

    print(f"Created organization '{args.company_name}' (id={row['id']}).")
    print(f"Company Code: {code}")
    print(f"Weekly report: {WEEKDAY_NAMES[args.report_weekday]} at {args.report_hour:02d}:{args.report_minute:02d} "
          f"{args.timezone}, sent to {args.report_recipients}")
    print(f"\nGive '{code}' to that organization's first admin - they create their account "
          f"at /admin/setup using it.")


if __name__ == "__main__":
    main()
