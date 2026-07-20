from datetime import date, datetime, timedelta


def get_period_bounds(reference_date: date):
    """Monday-Friday bounds of the week containing reference_date."""
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=4)
    return week_start, week_end


def calculate_payroll(conn, period_start: date, period_end: date):
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    employees = conn.execute(
        "SELECT * FROM employees WHERE active=1 ORDER BY name"
    ).fetchall()

    results = []
    for emp in employees:
        entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s AND clock_in>=%s AND clock_in<=%s",
            (emp["id"], period_start_dt, period_end_dt),
        ).fetchall()

        total_seconds = 0.0
        incomplete = False
        for e in entries:
            clock_in = e["clock_in"]
            if e["clock_out"]:
                total_seconds += (e["clock_out"] - clock_in).total_seconds()
            else:
                incomplete = True

        total_hours = round(total_seconds / 3600, 2)
        pay = round(total_hours * emp["hourly_rate"], 2)
        results.append({
            "employee_code": emp["employee_code"],
            "name": emp["name"],
            "worker_type": emp["worker_type"],
            "hourly_rate": emp["hourly_rate"],
            "total_hours": total_hours,
            "pay": pay,
            "incomplete": incomplete,
        })
    return results
