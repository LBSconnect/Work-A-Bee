from datetime import date, datetime, timedelta

from tz import now_in


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


def _round_dt(dt, minutes):
    if not minutes or minutes <= 0:
        return dt
    epoch = datetime(1970, 1, 1)
    delta_minutes = (dt - epoch).total_seconds() / 60
    rounded = round(delta_minutes / minutes) * minutes
    return epoch + timedelta(minutes=rounded)


def _split_overtime(hours_by_day, total_hours, rule, threshold):
    if rule == "daily_8":
        regular, overtime = 0.0, 0.0
        for day_hours in hours_by_day.values():
            if day_hours > 8:
                regular += 8
                overtime += day_hours - 8
            else:
                regular += day_hours
        return round(regular, 2), round(overtime, 2)
    if rule in ("weekly_40", "custom"):
        t = 40.0 if rule == "weekly_40" else (threshold or 40.0)
        regular = min(total_hours, t)
        overtime = max(total_hours - t, 0.0)
        return round(regular, 2), round(overtime, 2)
    return total_hours, 0.0


def get_period_entries(conn, org, period_start: date, period_end: date):
    """Per-employee clock in/out detail for the period, with running hours/pay totals."""
    org_id = org["id"]
    tz_name = org["timezone"]
    round_minutes = org.get("round_clock_minutes") or 0
    auto_lunch = bool(org.get("auto_lunch_deduction"))
    lunch_minutes = org.get("lunch_duration_minutes") or 30
    overtime_rule = org.get("overtime_rule") or "none"
    overtime_threshold = org.get("overtime_threshold_hours")

    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    now = now_in(tz_name)

    employees = conn.execute(
        "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name",
        (org_id,),
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
        hours_by_day = {}
        for e in time_entries:
            clock_in = _round_dt(e["clock_in"], round_minutes)
            if e["clock_out"]:
                clock_out = _round_dt(e["clock_out"], round_minutes)
                hours = (clock_out - clock_in).total_seconds() / 3600
                if auto_lunch and hours > 6:
                    hours = max(hours - lunch_minutes / 60, 0)
            else:
                incomplete = True
                accrued_through = min(now, period_end_dt)
                hours = max((accrued_through - clock_in).total_seconds(), 0) / 3600
            running_hours += hours
            hours_by_day[clock_in.date()] = hours_by_day.get(clock_in.date(), 0.0) + hours
            entries.append({
                "clock_in": e["clock_in"],
                "clock_out": e["clock_out"],
                "hours": round(hours, 2),
                "running_hours": round(running_hours, 2),
                "running_due": round(running_hours * emp["hourly_rate"], 2),
            })

        total_hours = round(running_hours, 2)
        regular_hours, overtime_hours = _split_overtime(hours_by_day, total_hours, overtime_rule, overtime_threshold)
        pay = round(regular_hours * emp["hourly_rate"] + overtime_hours * emp["hourly_rate"] * 1.5, 2)

        results.append({
            "employee_code": emp["employee_code"],
            "name": emp["name"],
            "worker_type": emp["worker_type"],
            "hourly_rate": emp["hourly_rate"],
            "entries": entries,
            "total_hours": total_hours,
            "regular_hours": regular_hours,
            "overtime_hours": overtime_hours,
            "total_due": pay,
            "incomplete": incomplete,
        })
    return results


def calculate_payroll(conn, org, period_start: date, period_end: date):
    detail = get_period_entries(conn, org, period_start, period_end)
    return [
        {
            "employee_code": d["employee_code"],
            "name": d["name"],
            "worker_type": d["worker_type"],
            "hourly_rate": d["hourly_rate"],
            "total_hours": d["total_hours"],
            "regular_hours": d["regular_hours"],
            "overtime_hours": d["overtime_hours"],
            "pay": d["total_due"],
            "incomplete": d["incomplete"],
        }
        for d in detail
    ]
