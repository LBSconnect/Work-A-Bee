from flask import Blueprint, g, jsonify

import plans
from api.auth import api_employee_required
from api.errors import ApiError
from models import get_db

api_employee_notifications_bp = Blueprint("api_employee_notifications", __name__, url_prefix="/api/v1/employee")


def _require_notifications_feature(org):
    if not plans.feature_available(org, "notifications"):
        raise ApiError(
            "feature_not_available", "Notifications aren't available on your current plan.", 403,
            required_plan=plans.FEATURE_TIERS["notifications"],
        )


@api_employee_notifications_bp.route("/notifications", methods=["GET"])
@api_employee_required
def list_notifications():
    org = g.api_org
    _require_notifications_feature(org)

    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE employee_id=%s ORDER BY created_at DESC LIMIT 50",
            (g.api_employee["id"],),
        ).fetchall()

    return jsonify({
        "notifications": [
            {
                "id": n["id"],
                "kind": n["kind"],
                "title": n["title"],
                "body": n["body"],
                "link": n["link"],
                "read": n["read_at"] is not None,
                "created_at": n["created_at"].isoformat(),
            }
            for n in rows
        ]
    })


@api_employee_notifications_bp.route("/notifications/read", methods=["POST"])
@api_employee_required
def mark_notifications_read():
    org = g.api_org
    _require_notifications_feature(org)

    with get_db() as conn:
        conn.execute(
            "UPDATE notifications SET read_at=NOW() WHERE employee_id=%s AND read_at IS NULL",
            (g.api_employee["id"],),
        )
        conn.commit()

    return jsonify({"ok": True})
