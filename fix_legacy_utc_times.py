"""One-time migration: correct clock in/out times recorded before the app
tracked Central time explicitly.

Before that fix, timestamps were taken from the server's system clock
(UTC on Render) but stored and displayed as if already Central time. Any
row inserted before the fix went live has its clock_in/clock_out
mislabeled: the stored value is actually a UTC wall-clock reading, not
Central.

This script finds rows with clock_in earlier than --cutoff (a UTC
timestamp) and corrects them by reinterpreting the stored value as UTC
and converting it to America/Chicago - which correctly accounts for
CDT/CST at that specific historical moment - then storing the result as
the new naive value. Rows at/after the cutoff are left untouched, since
they were already recorded correctly.

Usage (run from the project root, e.g. in Render's Shell):
    python3 fix_legacy_utc_times.py --cutoff 2026-07-20T17:30:00 --dry-run
    python3 fix_legacy_utc_times.py --cutoff 2026-07-20T17:30:00

Always run with --dry-run first and review the printed before/after
values before applying for real.
"""
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from models import get_db

UTC = ZoneInfo("UTC")
CENTRAL = ZoneInfo("America/Chicago")


def utc_naive_to_central_naive(value):
    """Reinterpret a naive datetime as UTC and convert it to Central wall-clock time."""
    return value.replace(tzinfo=UTC).astimezone(CENTRAL).replace(tzinfo=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--cutoff",
        required=True,
        help="UTC timestamp (ISO 8601, e.g. 2026-07-20T17:30:00). Entries with "
             "clock_in before this are treated as legacy UTC values and corrected.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing them.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    cutoff = datetime.fromisoformat(args.cutoff)

    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, clock_in, clock_out FROM time_entries WHERE clock_in < %s ORDER BY clock_in",
            (cutoff,),
        ).fetchall()

        if not rows:
            print("No entries found before the cutoff. Nothing to do.")
            return

        print(f"{len(rows)} entries recorded before {cutoff} (UTC) will be corrected:\n")
        changes = []
        for r in rows:
            new_clock_in = utc_naive_to_central_naive(r["clock_in"])
            new_clock_out = utc_naive_to_central_naive(r["clock_out"]) if r["clock_out"] else None
            changes.append((r["id"], new_clock_in, new_clock_out))
            print(f"  id={r['id']:>4}  clock_in:  {r['clock_in']} -> {new_clock_in}")
            print(f"           clock_out: {r['clock_out']} -> {new_clock_out}")

        if args.dry_run:
            print("\nDry run only - no changes written. Re-run without --dry-run to apply.")
            return

        if not args.yes:
            confirm = input(f"\nApply these {len(changes)} corrections? Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                print("Aborted, no changes made.")
                return

        for entry_id, new_clock_in, new_clock_out in changes:
            conn.execute(
                "UPDATE time_entries SET clock_in=%s, clock_out=%s WHERE id=%s",
                (new_clock_in, new_clock_out, entry_id),
            )
        conn.commit()
        print(f"\nDone - corrected {len(changes)} entries.")


if __name__ == "__main__":
    main()
