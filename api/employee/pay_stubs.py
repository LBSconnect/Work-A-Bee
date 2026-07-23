from datetime import datetime

from flask import Blueprint, abort, g, jsonify

from api.auth import api_employee_required
from models import get_db
from payroll import calculate_payroll, get_period_bounds, get_period_entries, get_prior_periods
from tz import today_in

api_employee_pay_stubs_bp = Blueprint("api_employee_pay_stubs", __name__, url_prefix="/api/v1/employee")


@api_employee_pay_stubs_bp.route("/pay-stubs", methods=["GET"])
@api_employee_required
def pay_stubs():
    emp = g.api_employee
    org = g.api_org

    with get_db() as conn:
        period_start, period_end = get_period_bounds(today_in(org["timezone"]))
        periods = [(period_start, period_end)] + get_prior_periods(period_start, count=11)
        stubs = []
        for start, end in periods:
            rows = calculate_payroll(conn, org, start, end)
            mine = next((r for r in rows if r["employee_code"] == emp["employee_code"]), None)
            stubs.append({
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "hours": mine["total_hours"] if mine else 0.0,
                "regular_hours": mine["regular_hours"] if mine else 0.0,
                "overtime_hours": mine["overtime_hours"] if mine else 0.0,
                "pay": mine["pay"] if mine else 0.0,
            })

    return jsonify({"stubs": stubs})


@api_employee_pay_stubs_bp.route("/pay-stubs/<period_start>", methods=["GET"])
@api_employee_required
def pay_stub_detail(period_start):
    emp = g.api_employee
    org = g.api_org

    try:
        start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
    except ValueError:
        abort(404)

    with get_db() as conn:
        _, end_date = get_period_bounds(start_date)
        detail = get_period_entries(conn, org, start_date, end_date)
        mine = next((d for d in detail if d["employee_code"] == emp["employee_code"]), None)

    if mine is None:
        mine = {
            "entries": [], "total_hours": 0.0, "regular_hours": 0.0,
            "overtime_hours": 0.0, "total_due": 0.0, "hourly_rate": emp["hourly_rate"],
        }

    entries = [
        {
            "clock_in": e["clock_in"].isoformat() if e.get("clock_in") else None,
            "clock_out": e["clock_out"].isoformat() if e.get("clock_out") else None,
            "hours": e.get("hours"),
            "running_hours": e.get("running_hours"),
            "running_due": e.get("running_due"),
            "is_manual": e.get("is_manual", False),
        }
        for e in mine["entries"]
    ]

    return jsonify({
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "hourly_rate": mine["hourly_rate"],
        "total_hours": mine["total_hours"],
        "regular_hours": mine["regular_hours"],
        "overtime_hours": mine["overtime_hours"],
        "total_due": mine["total_due"],
        "entries": entries,
    })
