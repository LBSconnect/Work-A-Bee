"""Create (or reset) a system admin account - platform-wide, cross-tenant access.

This is intentionally an off-band CLI action, not a public route: system admins
can see every organization's admins and employees, so new accounts should only
be created by whoever operates the platform, run directly against the database.

Usage:
    python3 create_system_admin.py --username admin --password 'TempPass123!'

The account is created (or its password reset) with must_change_password=True,
so whoever logs in with this password is forced to set their own before doing
anything else. Password is never printed back or logged - only hashed and
stored.
"""
import argparse
import getpass

from werkzeug.security import generate_password_hash

from models import get_db


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", help="Omit to be prompted (recommended - avoids shell history).")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Temporary password for this account: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")

    password_hash = generate_password_hash(password)

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM system_admins WHERE username=%s", (args.username,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE system_admins SET password_hash=%s, must_change_password=TRUE WHERE id=%s",
                (password_hash, existing["id"]),
            )
            conn.commit()
            print(f"Reset password for existing system admin '{args.username}' (id={existing['id']}).")
        else:
            row = conn.execute(
                "INSERT INTO system_admins (username, password_hash, must_change_password) "
                "VALUES (%s, %s, TRUE) RETURNING id",
                (args.username, password_hash),
            ).fetchone()
            conn.commit()
            print(f"Created system admin '{args.username}' (id={row['id']}).")

    print("They'll be required to set a new password on first login at /system/login.")


if __name__ == "__main__":
    main()
