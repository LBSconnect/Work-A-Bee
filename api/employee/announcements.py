from flask import Blueprint, g, jsonify

from api.auth import api_employee_required
from models import get_db

api_employee_announcements_bp = Blueprint("api_employee_announcements", __name__, url_prefix="/api/v1/employee")


@api_employee_announcements_bp.route("/announcements", methods=["GET"])
@api_employee_required
def announcements():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM announcements WHERE org_id=%s ORDER BY created_at DESC LIMIT 25",
            (g.api_org["id"],),
        ).fetchall()

    return jsonify({
        "announcements": [
            {
                "id": a["id"],
                "title": a["title"],
                "body": a["body"],
                "created_at": a["created_at"].isoformat(),
            }
            for a in rows
        ]
    })
