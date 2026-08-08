from flask import Blueprint, g, jsonify, request, url_for

import audit
import notifications
import reports
from api.auth import api_admin_required
from api.errors import ApiError
from models import get_db

api_admin_corrections_bp = Blueprint("api_admin_corrections", __name__, url_prefix="/api/v1/admin")


def _serialize(row):
    return {
        "id": row["id"],
        "employee_id": row["employee_id"],
        "name": row["name"],
        "employee_code": row["employee_code"],
        "issue_type": row["issue_type"],
        "issue_date": row["issue_date"].isoformat(),
        "requested_clock_in": row["requested_clock_in"].isoformat() if row["requested_clock_in"] else None,
        "requested_clock_out": row["requested_clock_out"].isoformat() if row["requested_clock_out"] else None,
        "reason": row["reason"],
        "status": row["status"],
        "manager_comment": row["manager_comment"],
    }


@api_admin_corrections_bp.route("/corrections", methods=["GET"])
@api_admin_required
def list_corrections():
    with get_db() as conn:
        rows = reports.corrections_queue(conn, g.api_org)
    return jsonify({"requests": [_serialize(r) for r in rows]})


@api_admin_corrections_bp.route("/corrections/<int:correction_id>/approve", methods=["POST"])
@api_admin_required
def approve_correction(correction_id):
    org = g.api_org
    admin = g.api_admin
    with get_db() as conn:
        c = reports.approve_correction(conn, org["id"], correction_id, admin["id"])
        if c is None:
            raise ApiError("not_found", "That request has already been reviewed.", 404)

        audit.log(
            conn, org["id"], "admin", admin["id"], "time_entry.correction_approved",
            f"{c['name']} ({c['employee_code']}): {c['issue_type']} on {c['issue_date']} - "
            f"clock_in={c['requested_clock_in']}, clock_out={c['requested_clock_out']}",
        )
        notifications.notify_employee(
            conn, org["id"], c["employee_id"], "punch_correction_approved",
            "Your punch correction was approved",
            body=f"{c['issue_date'].strftime('%b %d, %Y')} - your timecard has been updated.",
            link=url_for("time_history_page"),
        )
        conn.commit()

    return jsonify({"request": _serialize(c)})


@api_admin_corrections_bp.route("/corrections/<int:correction_id>/deny", methods=["POST"])
@api_admin_required
def deny_correction(correction_id):
    data = request.get_json(silent=True) or {}
    comment = (data.get("comment") or "").strip()
    if not comment:
        raise ApiError("validation_error", "A comment explaining why is required to deny a correction request.",
                        422, fields={"comment": "Required."})

    org = g.api_org
    admin = g.api_admin
    with get_db() as conn:
        c = reports.deny_correction(conn, org["id"], correction_id, admin["id"], comment)
        if c is None:
            raise ApiError("not_found", "That request has already been reviewed.", 404)

        audit.log(
            conn, org["id"], "admin", admin["id"], "time_entry.correction_denied",
            f"{c['name']} ({c['employee_code']}): {c['issue_type']} on {c['issue_date']} - \"{comment}\"",
        )
        notifications.notify_employee(
            conn, org["id"], c["employee_id"], "punch_correction_denied",
            "Your punch correction request was denied",
            body=f"{c['issue_date'].strftime('%b %d, %Y')}. {comment}",
            link=url_for("time_history_page"),
        )
        conn.commit()

    return jsonify({"request": _serialize(c)})
