from flask import Blueprint, g, jsonify, url_for

import notifications
from api.auth import api_employee_required
from models import get_db

# Satisfies Apple App Store Guideline 5.1.1(v): an app that lets someone sign
# into an account must offer an in-app way to have it deleted. This app's
# accounts are provisioned by an employer admin (not self-service signup),
# and payroll/timekeeping records typically carry their own legal retention
# requirements the employer has to weigh - so this deliberately isn't a
# self-service "delete my account now" button. It's a request, routed to the
# org's admins (same notify_admins path as every other admin-facing event -
# in-app notification, email, and push), who review and act on it, same as
# they'd handle any other account change today. There is no automated
# deletion pipeline behind this and none is implied to the employee.
api_employee_account_deletion_bp = Blueprint(
    "api_employee_account_deletion", __name__, url_prefix="/api/v1/employee"
)

# Stops a repeated tap (or an impatient employee re-opening the screen) from
# flooding admins with duplicate notifications for the same request. A
# lightweight window check against the existing notifications table, rather
# than a dedicated status table, since this endpoint's whole job is firing
# that one notification - there's no multi-step workflow state to track.
_DEDUPE_WINDOW = "24 hours"


@api_employee_account_deletion_bp.route("/account-deletion-request", methods=["POST"])
@api_employee_required
def request_account_deletion():
    emp = g.api_employee
    org_id = g.api_org["id"]
    edit_link = url_for("admin_employee_edit", emp_id=emp["id"])

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM notifications "
            "WHERE org_id=%s AND kind='account_deletion_requested' AND link=%s "
            "AND created_at > NOW() - INTERVAL %s",
            (org_id, edit_link, _DEDUPE_WINDOW),
        ).fetchone()
        if existing:
            return jsonify({"ok": True, "already_requested": True})

        notifications.notify_admins(
            conn,
            org_id,
            "account_deletion_requested",
            f"{emp['name']} requested account deletion",
            body=(
                f"{emp['name']} ({emp['employee_code']}) asked to have their Work-A-Beez "
                "account and data deleted. Review their record and any legal/payroll "
                "retention requirements before removing them."
            ),
            link=edit_link,
        )
        conn.commit()

    return jsonify({"ok": True, "already_requested": False})
