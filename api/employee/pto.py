from datetime import datetime

from flask import Blueprint, g, jsonify, request

import audit
from api.auth import api_employee_required
from api.errors import ApiError
from models import get_db

api_employee_pto_bp = Blueprint("api_employee_pto", __name__, url_prefix="/api/v1/employee")


def _serialize(row):
    return {
        "id": row["id"],
        "start_date": row["start_date"].isoformat(),
        "end_date": row["end_date"].isoformat(),
        "hours": row["hours"],
        "reason": row["reason"],
        "status": row["status"],
        "requested_at": row["requested_at"].isoformat() if row["requested_at"] else None,
    }


@api_employee_pto_bp.route("/pto", methods=["GET"])
@api_employee_required
def list_pto():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM pto_requests WHERE employee_id=%s ORDER BY requested_at DESC",
            (g.api_employee["id"],),
        ).fetchall()
    return jsonify({"requests": [_serialize(r) for r in rows]})


@api_employee_pto_bp.route("/pto", methods=["POST"])
@api_employee_required
def create_pto():
    data = request.get_json(silent=True) or {}
    emp = g.api_employee
    org = g.api_org

    fields = {}
    try:
        start_date = datetime.strptime(data.get("start_date", ""), "%Y-%m-%d").date()
    except ValueError:
        fields["start_date"] = "Enter a valid date (YYYY-MM-DD)."
    try:
        end_date = datetime.strptime(data.get("end_date", ""), "%Y-%m-%d").date()
    except ValueError:
        fields["end_date"] = "Enter a valid date (YYYY-MM-DD)."
    try:
        hours = float(data.get("hours"))
    except (TypeError, ValueError):
        fields["hours"] = "Enter a number of hours."

    if fields:
        raise ApiError("validation_error", "Check the highlighted fields.", 422, fields=fields)
    if end_date < start_date:
        raise ApiError("validation_error", "End date must be on or after the start date.", 422,
                        fields={"end_date": "Must be on or after the start date."})
    if hours <= 0:
        raise ApiError("validation_error", "Hours requested must be greater than zero.", 422,
                        fields={"hours": "Must be greater than zero."})

    reason = (data.get("reason") or "").strip() or None

    with get_db() as conn:
        row = conn.execute(
            "INSERT INTO pto_requests (org_id, employee_id, start_date, end_date, hours, reason) "
            "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
            (org["id"], emp["id"], start_date, end_date, hours, reason),
        ).fetchone()
        audit.log(conn, org["id"], "employee", emp["id"], "pto.requested", f"{start_date} - {end_date} ({hours}h)")
        conn.commit()

    return jsonify({"request": _serialize(row)}), 201
