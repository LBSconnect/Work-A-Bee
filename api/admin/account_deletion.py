from flask import Blueprint, g, jsonify

import config
import notify_email
from api.auth import api_admin_required
from models import get_db

# Satisfies Apple App Store Guideline 5.1.1(v). Unlike employee accounts
# (provisioned by an employer admin - see api/employee/account_deletion.py),
# admin accounts ARE created self-service, via the web signup wizard with an
# admin-chosen email/password (see signup_wizard.py). An app that lets
# someone sign into a self-service account must offer an in-app way to
# delete it or request its deletion - the employee flow's "route it to your
# admin" carve-out doesn't apply to the admin role itself, since there's no
# in-app "admin's admin" within the org to route to.
#
# Deleting an admin account here effectively means deleting the whole
# organization (its employees, schedules, payroll history, billing
# subscription, ...), which isn't something to automate blind from a single
# mobile tap. So, same "request routed to a human who reviews it" pattern as
# the employee flow, just routed to Work-A-Beez's own platform support
# contact instead of an in-app recipient. There is no automated deletion
# pipeline behind this and none is implied to the admin.
api_admin_account_deletion_bp = Blueprint(
    "api_admin_account_deletion", __name__, url_prefix="/api/v1/admin"
)

# Same dedupe rationale as the employee endpoint: stops a repeated tap from
# flooding platform support with duplicate emails for the same request. The
# notifications row here has no in-app admin inbox to surface it in (admins
# don't have a notifications feed today) - it exists purely as this
# dedupe/audit record, keyed to the requesting admin's own admin_id.
_DEDUPE_WINDOW = "24 hours"


@api_admin_account_deletion_bp.route("/account-deletion-request", methods=["POST"])
@api_admin_required
def request_account_deletion():
    admin = g.api_admin
    org = g.api_org

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM notifications "
            "WHERE org_id=%s AND admin_id=%s AND kind='account_deletion_requested' "
            "AND created_at > NOW() - INTERVAL %s",
            (org["id"], admin["id"], _DEDUPE_WINDOW),
        ).fetchone()
        if existing:
            return jsonify({"ok": True, "already_requested": True})

        detail = (
            f"Admin {admin['username']} ({admin['email'] or 'no email on file'}) of "
            f"'{org['name']}' (org #{org['id']}) requested their Work-A-Beez account and "
            "organization be deleted via the mobile app. Review any billing/payroll/legal "
            "retention requirements before removing them."
        )

        conn.execute(
            "INSERT INTO notifications (org_id, admin_id, kind, title, body) "
            "VALUES (%s,%s,%s,%s,%s)",
            (org["id"], admin["id"], "account_deletion_requested",
             f"{admin['username']} requested account deletion", detail),
        )
        conn.commit()

        notify_email.send_email(
            config.PLATFORM_SUPPORT_EMAIL,
            f"Account deletion requested: {org['name']}",
            detail,
        )

    return jsonify({"ok": True, "already_requested": False})
