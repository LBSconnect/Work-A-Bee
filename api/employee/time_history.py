from datetime import timedelta

from flask import Blueprint, g, jsonify

from api.auth import api_employee_required
from models import get_db
from payroll import calculate_payroll, get_period_bounds, get_prior_periods
from tz import today_in

api_employee_time_history_bp = Blueprint("api_employee_time_history", __name__, url_prefix="/api/v1/employee")


@api_employee_time_history_bp.route("/time-history", methods=["GET"])
@api_employee_required
def time_history():
    emp = g.api_employee
    org = g.api_org

    with get_db() as conn:
        recent_entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s ORDER BY clock_in DESC LIMIT 25",
            (emp["id"],),
        ).fetchall()

        period_start, _ = get_period_bounds(today_in(org["timezone"]))
        weekly_history = []
        for start, end in [(period_start, period_start + timedelta(days=6))] + get_prior_periods(period_start, count=8):
            rows = calculate_payroll(conn, org, start, end)
            mine = next((r for r in rows if r["employee_code"] == emp["employee_code"]), None)
            weekly_history.append({
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "hours": mine["total_hours"] if mine else 0.0,
                "pay": mine["pay"] if mine else 0.0,
            })

    history = []
    for e in recent_entries:
        hours = None
        if e["clock_out"]:
            hours = round((e["clock_out"] - e["clock_in"]).total_seconds() / 3600, 2)
        history.append({
            "clock_in": e["clock_in"].isoformat(),
            "clock_out": e["clock_out"].isoformat() if e["clock_out"] else None,
            "hours": hours,
        })

    return jsonify({"history": history, "weekly_history": weekly_history})
