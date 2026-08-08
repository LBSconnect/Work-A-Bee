from flask import Blueprint, g, jsonify, url_for

import audit
import notifications
import reports
from api.auth import api_admin_required
from api.errors import ApiError
from models import get_db

api_admin_pto_bp = Blueprint("api_admin_pto", __name__, url_prefix="/api/v1/admin")


def _serialize(row):
    return {
        "id": row["id"],
        "employee_id": row["employee_id"],
        "employee_name": row["employee_name"],
        "employee_code": row["employee_code"],
        "start_date": row["start_date"].isoformat(),
        "end_date": row["end_date"].isoformat(),
        "hours": row["hours"],
        "reason": row["reason"],
        "status": row["status"],
        "requested_at": row["requested_at"].isoformat() if row["requested_at"] else None,
    }


@api_admin_pto_bp.route("/pto", methods=["GET"])
@api_admin_required
def list_pto():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT r.*, e.name AS employee_name, e.employee_code, e.pto_balance_hours FROM pto_requests r "
            "JOIN employees e ON r.employee_id = e.id "
            "WHERE r.org_id=%s ORDER BY (r.status = 'pending') DESC, r.requested_at DESC",
            (g.api_org["id"],),
        ).fetchall()
    return jsonify({"requests": [_serialize(r) for r in rows]})


@api_admin_pto_bp.route("/pto/<int:request_id>/approve", methods=["POST"])
@api_admin_required
def approve_pto(request_id):
    org = g.api_org
    admin = g.api_admin
    with get_db() as conn:
        req = reports.approve_pto(conn, org["id"], request_id, admin["id"])
        if req is None:
            raise ApiError("not_found", "Request not found or already reviewed.", 404)

        audit.log(conn, org["id"], "admin", admin["id"], "pto.approved", f"{req['employee_name']}: {req['hours']}h")
        notifications.notify_employee(
            conn, org["id"], req["employee_id"], "pto_approved",
            "Your time off request was approved",
            body=f"{req['start_date'].strftime('%b %d')} - {req['end_date'].strftime('%b %d')} ({req['hours']}h) approved.",
            link=url_for("pto_requests_page"),
        )
        conn.commit()

    response = {"request": _serialize(req)}
    if req["hours"] > req["pto_balance_hours"]:
        response["warning"] = (
            f"{req['employee_name']} only had {req['pto_balance_hours']:.1f} PTO hours available; "
            "the balance is now negative."
        )
    return jsonify(response)


@api_admin_pto_bp.route("/pto/<int:request_id>/deny", methods=["POST"])
@api_admin_required
def deny_pto(request_id):
    org = g.api_org
    admin = g.api_admin
    with get_db() as conn:
        req = reports.deny_pto(conn, org["id"], request_id, admin["id"])
        if req is None:
            raise ApiError("not_found", "Request not found or already reviewed.", 404)

        audit.log(conn, org["id"], "admin", admin["id"], "pto.denied", f"{req['employee_name']}: {req['hours']}h")
        notifications.notify_employee(
            conn, org["id"], req["employee_id"], "pto_denied",
            "Your time off request was denied",
            body=f"{req['start_date'].strftime('%b %d')} - {req['end_date'].strftime('%b %d')} ({req['hours']}h) denied.",
            link=url_for("pto_requests_page"),
        )
        conn.commit()

    return jsonify({"request": _serialize(req)})
