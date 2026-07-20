from datetime import date, datetime, timedelta

from tz import now_central


def get_period_bounds(reference_date: date):
    """Monday-Friday bounds of the week containing reference_date."""
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=4)
    return week_start, week_end


def get_prior_periods(period_start: date, count: int = 4):
    """The `count` Monday-Friday periods immediately before period_start, most recent first."""
    periods = []
    for i in range(1, count + 1):
        start = period_start - timedelta(days=7 * i)
        end = start + timedelta(days=4)
        periods.append((start, end))
    return periods


def get_period_entries(conn, period_start: date, period_end: date):
    """Per-employee clock in/out detail for the period, with running hours/pay totals."""
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    now = now_central()

    employees = conn.execute(
        "SELECT * FROM employees WHERE active=1 ORDER BY name"
    ).fetchall()

    results = []
    for emp in employees:
        time_entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s AND clock_in>=%s AND clock_in<=%s "
            "ORDER BY clock_in",
            (emp["id"], period_start_dt, period_end_dt),
        ).fetchall()

        entries = []
        running_hours = 0.0
        incomplete = False
        for e in time_entries:
            clock_in = e["clock_in"]
            if e["clock_out"]:
                hours = (e["clock_out"] - clock_in).total_seconds() / 3600
            else:
                incomplete = True
                accrued_through = min(now, period_end_dt)
                hours = max((accrued_through - clock_in).total_seconds(), 0) / 3600
            running_hours += hours
            entries.append({
                "clock_in": clock_in,
                "clock_out": e["clock_out"],
                "hours": round(hours, 2),
                "running_hours": round(running_hours, 2),
                "running_due": round(running_hours * emp["hourly_rate"], 2),
            })

        total_hours = round(running_hours, 2)
        results.append({
            "employee_code": emp["employee_code"],
            "name": emp["name"],
            "worker_type": emp["worker_type"],
            "hourly_rate": emp["hourly_rate"],
            "entries": entries,
            "total_hours": total_hours,
            "total_due": round(total_hours * emp["hourly_rate"], 2),
            "incomplete": incomplete,
        })
    return results


def calculate_payroll(conn, period_start: date, period_end: date):
    detail = get_period_entries(conn, period_start, period_end)
    return [
        {
            "employee_code": d["employee_code"],
            "name": d["name"],
            "worker_type": d["worker_type"],
            "hourly_rate": d["hourly_rate"],
            "total_hours": d["total_hours"],
            "pay": d["total_due"],
            "incomplete": d["incomplete"],
        }
        for d in detail
    ]
