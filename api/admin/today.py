from flask import Blueprint, g, jsonify

import reports
from api.auth import api_admin_required
from models import get_db
from tz import today_in

api_admin_today_bp = Blueprint("api_admin_today", __name__, url_prefix="/api/v1/admin")


def _serialize_clocked_in(row):
    return {
        "employee_id": row["id"],
        "name": row["name"],
        "employee_code": row["employee_code"],
        "clock_in": row["clock_in"].isoformat(),
    }


def _serialize_exception(row):
    return {
        "employee_code": row["employee_code"],
        "name": row["name"],
        "date": row["date"].isoformat(),
        "scheduled_start": row["scheduled_start"].isoformat() if row["scheduled_start"] else None,
        "scheduled_end": row["scheduled_end"].isoformat() if row["scheduled_end"] else None,
        "actual_in": row["actual_in"].isoformat() if row["actual_in"] else None,
        "actual_out": row["actual_out"].isoformat() if row["actual_out"] else None,
        "flags": row["flags"],
    }


@api_admin_today_bp.route("/today", methods=["GET"])
@api_admin_required
def today_status():
    org = g.api_org
    today = today_in(org["timezone"])

    with get_db() as conn:
        clocked_in = conn.execute(
            "SELECT e.id, e.name, e.employee_code, t.clock_in FROM time_entries t "
            "JOIN employees e ON t.employee_id = e.id "
            "WHERE e.org_id=%s AND t.clock_out IS NULL ORDER BY t.clock_in",
            (org["id"],),
        ).fetchall()
        attendance = reports.daily_attendance_rows(conn, org, today, today)

    exceptions = [r for r in attendance if r["flags"] != "OK"]

    return jsonify({
        "date": today.isoformat(),
        "clocked_in_now": [_serialize_clocked_in(r) for r in clocked_in],
        "exceptions": [_serialize_exception(r) for r in exceptions],
    })
