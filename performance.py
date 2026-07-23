from datetime import timedelta

GRACE_MINUTES = 10


def shift_attendance(conn, org_id, now, weeks=8, employee_id=None):
    """Match each completed shift in the window to a clock-in that day.

    Returns a list of rows: shift_id, employee_id, shift_start, punch_in, status
    where status is one of 'on_time', 'late', 'missed'.
    """
    since = now - timedelta(weeks=weeks)
    params = [org_id, now, since]
    emp_filter = ""
    if employee_id is not None:
        emp_filter = "AND s.employee_id=%s"
        params.append(employee_id)

    rows = conn.execute(
        f"""
        SELECT s.id AS shift_id, s.employee_id, s.shift_start,
               (SELECT MIN(t.clock_in) FROM time_entries t
                WHERE t.employee_id = s.employee_id AND t.clock_in::date = s.shift_start::date) AS punch_in
        FROM shifts s
        WHERE s.org_id=%s AND s.shift_end < %s AND s.shift_start >= %s {emp_filter}
        ORDER BY s.shift_start DESC
        """,
        tuple(params),
    ).fetchall()

    results = []
    for r in rows:
        if r["punch_in"] is None:
            status = "missed"
        elif r["punch_in"] > r["shift_start"] + timedelta(minutes=GRACE_MINUTES):
            status = "late"
        else:
            status = "on_time"
        results.append({**r, "status": status})
    return results


def summarize_attendance(rows):
    total = len(rows)
    on_time = sum(1 for r in rows if r["status"] == "on_time")
    late = sum(1 for r in rows if r["status"] == "late")
    missed = sum(1 for r in rows if r["status"] == "missed")
    return {
        "total_shifts": total,
        "on_time": on_time,
        "late": late,
        "missed": missed,
        "attendance_rate": round((on_time + late) / total * 100, 1) if total else None,
        "punctuality_rate": round(on_time / total * 100, 1) if total else None,
    }


def org_leaderboard(conn, org_id, now, weeks=8):
    """Per-employee attendance summary for every employee with at least one completed shift."""
    rows = shift_attendance(conn, org_id, now, weeks=weeks)
    by_employee = {}
    for r in rows:
        by_employee.setdefault(r["employee_id"], []).append(r)

    employees = conn.execute(
        "SELECT id, name, employee_code FROM employees WHERE org_id=%s", (org_id,)
    ).fetchall()
    emp_lookup = {e["id"]: e for e in employees}

    leaderboard = []
    for emp_id, emp_rows in by_employee.items():
        emp = emp_lookup.get(emp_id)
        if emp is None:
            continue
        summary = summarize_attendance(emp_rows)
        leaderboard.append({"employee": emp, **summary})

    leaderboard.sort(key=lambda x: (x["punctuality_rate"] is None, x["punctuality_rate"]))
    return leaderboard
