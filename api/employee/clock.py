from flask import Blueprint, g, jsonify

import payroll
from api.auth import api_employee_required
from models import get_db
from tz import now_in, today_in

api_employee_clock_bp = Blueprint("api_employee_clock", __name__, url_prefix="/api/v1/employee")


def _status_payload(conn):
    emp = g.api_employee
    org = g.api_org

    open_entry = conn.execute(
        "SELECT * FROM time_entries WHERE employee_id=%s AND clock_out IS NULL", (emp["id"],)
    ).fetchone()

    today = today_in(org["timezone"])
    period_start, period_end = payroll.get_period_bounds(today)
    period_detail = payroll.get_period_entries(conn, org, period_start, period_end)
    my_current = next((d for d in period_detail if d["employee_code"] == emp["employee_code"]), None)

    return {
        "clocked_in": open_entry is not None,
        "clock_in_at": open_entry["clock_in"].isoformat() if open_entry else None,
        "current_period_hours": my_current["total_hours"] if my_current else 0.0,
        "current_period_pay": my_current["total_due"] if my_current else 0.0,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


@api_employee_clock_bp.route("/clock/status", methods=["GET"])
@api_employee_required
def clock_status():
    with get_db() as conn:
        return jsonify(_status_payload(conn))


@api_employee_clock_bp.route("/clock", methods=["POST"])
@api_employee_required
def clock_toggle():
    emp = g.api_employee
    org = g.api_org

    with get_db() as conn:
        open_entry = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s AND clock_out IS NULL", (emp["id"],)
        ).fetchone()

        now = now_in(org["timezone"])
        if open_entry:
            conn.execute("UPDATE time_entries SET clock_out=%s WHERE id=%s", (now, open_entry["id"]))
            action = "clocked_out"
        else:
            conn.execute(
                "INSERT INTO time_entries (employee_id, clock_in) VALUES (%s, %s)", (emp["id"], now)
            )
            action = "clocked_in"
        conn.commit()

        payload = _status_payload(conn)

    payload["action"] = action
    payload["at"] = now.isoformat()
    return jsonify(payload)
