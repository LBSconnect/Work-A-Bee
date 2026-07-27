import csv
import io
from datetime import datetime, timedelta

from flask import Response

from payroll import get_period_entries
from tz import now_in


def csv_response(filename, columns, rows):
    """columns: list of (key, header_label) tuples. rows: list of dicts."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([label for _, label in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _ in columns])
    resp = Response(buf.getvalue(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _employees_by_code(conn, org_id):
    emps = conn.execute(
        "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (org_id,)
    ).fetchall()
    return {e["employee_code"]: e for e in emps}


def _pto_hours_by_employee(conn, org_id, period_start, period_end, statuses=("approved",)):
    placeholders = ",".join(["%s"] * len(statuses))
    rows = conn.execute(
        f"SELECT employee_id, SUM(hours) AS hours FROM pto_requests "
        f"WHERE org_id=%s AND status IN ({placeholders}) "
        f"AND start_date <= %s AND end_date >= %s "
        f"GROUP BY employee_id",
        (org_id, *statuses, period_end, period_start),
    ).fetchall()
    return {r["employee_id"]: (r["hours"] or 0.0) for r in rows}


def timesheet_summary_rows(conn, org, period_start, period_end):
    """Regular, overtime, PTO, and total hours by employee for the period."""
    detail = get_period_entries(conn, org, period_start, period_end)
    employees = _employees_by_code(conn, org["id"])
    pto_hours = _pto_hours_by_employee(conn, org["id"], period_start, period_end)

    rows = []
    for d in detail:
        emp = employees.get(d["employee_code"])
        pto = pto_hours.get(emp["id"], 0.0) if emp else 0.0
        rows.append({
            "employee_code": d["employee_code"],
            "name": d["name"],
            "regular_hours": d["regular_hours"],
            "overtime_hours": d["overtime_hours"],
            "pto_hours": round(pto, 2),
            "total_hours": round(d["regular_hours"] + d["overtime_hours"] + pto, 2),
            "incomplete": d["incomplete"],
        })
    return rows


def daily_attendance_rows(conn, org, period_start, period_end):
    """Per employee, per day: scheduled vs actual clock times and attendance flags."""
    org_id = org["id"]
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    now = now_in(org["timezone"])

    employees = conn.execute(
        "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (org_id,)
    ).fetchall()

    rows = []
    for emp in employees:
        shifts = conn.execute(
            "SELECT * FROM shifts WHERE employee_id=%s AND shift_start>=%s AND shift_start<=%s "
            "ORDER BY shift_start",
            (emp["id"], period_start_dt, period_end_dt),
        ).fetchall()
        entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s AND clock_in>=%s AND clock_in<=%s "
            "ORDER BY clock_in",
            (emp["id"], period_start_dt, period_end_dt),
        ).fetchall()

        shifts_by_day = {}
        for s in shifts:
            shifts_by_day.setdefault(s["shift_start"].date(), []).append(s)
        entries_by_day = {}
        for e in entries:
            entries_by_day.setdefault(e["clock_in"].date(), []).append(e)

        for day in sorted(set(shifts_by_day) | set(entries_by_day)):
            day_shifts = shifts_by_day.get(day, [])
            day_entries = entries_by_day.get(day, [])
            shift = day_shifts[0] if day_shifts else None
            first_in = min((e["clock_in"] for e in day_entries), default=None)
            outs = [e["clock_out"] for e in day_entries if e["clock_out"]]
            last_out = max(outs) if outs else None
            has_open_entry = any(e["clock_out"] is None for e in day_entries)

            flags = []
            if shift and first_in and first_in > shift["shift_start"] + timedelta(minutes=5):
                flags.append("Late")
            if shift and last_out and last_out < shift["shift_end"] - timedelta(minutes=5):
                flags.append("Early Departure")
            if shift and not day_entries and shift["shift_start"] < now:
                flags.append("No-Show")
            if has_open_entry:
                flags.append("Missing Clock-Out")

            rows.append({
                "employee_code": emp["employee_code"],
                "name": emp["name"],
                "date": day,
                "scheduled_start": shift["shift_start"] if shift else None,
                "scheduled_end": shift["shift_end"] if shift else None,
                "actual_in": first_in,
                "actual_out": last_out,
                "flags": ", ".join(flags) if flags else "OK",
            })

    rows.sort(key=lambda r: (r["date"], r["name"]))
    return rows


def missing_punches_rows(conn, org, period_start, period_end):
    """Open clock-outs and no-shows for shifts already in the past."""
    org_id = org["id"]
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    now = now_in(org["timezone"])

    open_entries = conn.execute(
        "SELECT te.*, e.name, e.employee_code FROM time_entries te "
        "JOIN employees e ON te.employee_id=e.id "
        "WHERE e.org_id=%s AND te.clock_in>=%s AND te.clock_in<=%s AND te.clock_out IS NULL "
        "ORDER BY te.clock_in",
        (org_id, period_start_dt, period_end_dt),
    ).fetchall()
    rows = [
        {
            "employee_code": e["employee_code"],
            "name": e["name"],
            "date": e["clock_in"].date(),
            "issue": "Missing Clock-Out",
            "detail": f'Clocked in {e["clock_in"].strftime("%I:%M %p").lstrip("0")}, never clocked out',
        }
        for e in open_entries
        if e["clock_in"].date() < now.date()
    ]

    shifts = conn.execute(
        "SELECT s.*, e.name, e.employee_code FROM shifts s JOIN employees e ON s.employee_id=e.id "
        "WHERE s.org_id=%s AND s.shift_start>=%s AND s.shift_start<=%s AND s.shift_start<%s "
        "ORDER BY s.shift_start",
        (org_id, period_start_dt, period_end_dt, now),
    ).fetchall()
    for s in shifts:
        has_entry = conn.execute(
            "SELECT 1 FROM time_entries WHERE employee_id=%s AND clock_in::date=%s",
            (s["employee_id"], s["shift_start"].date()),
        ).fetchone()
        if not has_entry:
            rows.append({
                "employee_code": s["employee_code"],
                "name": s["name"],
                "date": s["shift_start"].date(),
                "issue": "Missing Clock-In (No-Show)",
                "detail": f'Scheduled {s["shift_start"].strftime("%I:%M %p").lstrip("0")}'
                          f'–{s["shift_end"].strftime("%I:%M %p").lstrip("0")}, no clock-in recorded',
            })

    rows.sort(key=lambda r: r["date"])
    return rows


def overtime_rows(conn, org, period_start, period_end):
    """Employees approaching or exceeding the org's overtime threshold."""
    detail = get_period_entries(conn, org, period_start, period_end)
    threshold = org.get("overtime_threshold_hours") or 40.0

    rows = []
    for d in detail:
        pct = round(d["total_hours"] / threshold * 100) if threshold else 0
        if d["overtime_hours"] > 0:
            status = "Over Threshold"
        elif pct >= 90:
            status = "Approaching"
        else:
            status = "OK"
        rows.append({
            "employee_code": d["employee_code"],
            "name": d["name"],
            "regular_hours": d["regular_hours"],
            "overtime_hours": d["overtime_hours"],
            "total_hours": d["total_hours"],
            "threshold_hours": threshold,
            "pct_of_threshold": pct,
            "status": status,
        })
    rows.sort(key=lambda r: -r["overtime_hours"])
    return rows


def schedule_vs_actual_rows(conn, org, period_start, period_end):
    """Scheduled shift hours vs actual worked hours, by employee."""
    org_id = org["id"]
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())

    detail = get_period_entries(conn, org, period_start, period_end)
    actual_by_code = {d["employee_code"]: d["total_hours"] for d in detail}

    employees = conn.execute(
        "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (org_id,)
    ).fetchall()

    rows = []
    for emp in employees:
        shifts = conn.execute(
            "SELECT * FROM shifts WHERE employee_id=%s AND shift_start>=%s AND shift_start<=%s",
            (emp["id"], period_start_dt, period_end_dt),
        ).fetchall()
        scheduled_hours = sum((s["shift_end"] - s["shift_start"]).total_seconds() / 3600 for s in shifts)
        actual_hours = actual_by_code.get(emp["employee_code"], 0.0)
        rows.append({
            "employee_code": emp["employee_code"],
            "name": emp["name"],
            "scheduled_hours": round(scheduled_hours, 2),
            "actual_hours": round(actual_hours, 2),
            "variance_hours": round(actual_hours - scheduled_hours, 2),
        })
    return rows


def time_off_rows(conn, org, period_start, period_end):
    """PTO requests overlapping the period, with each employee's current balance."""
    requests = conn.execute(
        "SELECT r.*, e.name, e.employee_code, e.pto_balance_hours FROM pto_requests r "
        "JOIN employees e ON r.employee_id=e.id "
        "WHERE r.org_id=%s AND r.start_date<=%s AND r.end_date>=%s "
        "ORDER BY r.start_date",
        (org["id"], period_end, period_start),
    ).fetchall()
    return [
        {
            "employee_code": r["employee_code"],
            "name": r["name"],
            "start_date": r["start_date"],
            "end_date": r["end_date"],
            "hours": r["hours"],
            "reason": r["reason"] or "",
            "status": r["status"],
            "balance_hours": r["pto_balance_hours"],
        }
        for r in requests
    ]


def approval_status_rows(conn, org, period_start, period_end):
    """Each active employee's timesheet-approval status for the period."""
    org_id = org["id"]
    employees = conn.execute(
        "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (org_id,)
    ).fetchall()
    approvals = conn.execute(
        "SELECT ta.*, a.username AS approved_by_username FROM timesheet_approvals ta "
        "LEFT JOIN admin_users a ON ta.approved_by_admin_id=a.id "
        "WHERE ta.org_id=%s AND ta.period_start=%s AND ta.period_end=%s",
        (org_id, period_start, period_end),
    ).fetchall()
    by_employee = {a["employee_id"]: a for a in approvals}

    rows = []
    for emp in employees:
        a = by_employee.get(emp["id"])
        rows.append({
            "employee_id": emp["id"],
            "employee_code": emp["employee_code"],
            "name": emp["name"],
            "status": a["status"] if a else "pending",
            "approved_by": a["approved_by_username"] if a and a["status"] == "approved" else None,
            "approved_at": a["approved_at"] if a else None,
        })
    return rows


def set_timesheet_approval(conn, org_id, employee_id, period_start, period_end, status, admin_id):
    conn.execute(
        "INSERT INTO timesheet_approvals "
        "(org_id, employee_id, period_start, period_end, status, approved_by_admin_id, approved_at) "
        "VALUES (%s,%s,%s,%s,%s,%s, CASE WHEN %s='approved' THEN NOW() ELSE NULL END) "
        "ON CONFLICT (employee_id, period_start, period_end) DO UPDATE SET "
        "status=EXCLUDED.status, approved_by_admin_id=EXCLUDED.approved_by_admin_id, "
        "approved_at=CASE WHEN EXCLUDED.status='approved' THEN NOW() ELSE NULL END",
        (org_id, employee_id, period_start, period_end, status, admin_id, status),
    )


def labor_cost_rows(conn, org, period_start, period_end):
    """Regular/overtime/PTO labor cost, grouped by department."""
    detail = get_period_entries(conn, org, period_start, period_end)
    employees = _employees_by_code(conn, org["id"])
    pto_hours = _pto_hours_by_employee(conn, org["id"], period_start, period_end)
    dept_names = {
        d["id"]: d["name"]
        for d in conn.execute("SELECT id, name FROM departments WHERE org_id=%s", (org["id"],)).fetchall()
    }

    buckets = {}
    for d in detail:
        emp = employees.get(d["employee_code"])
        dept = dept_names.get(emp["department_id"]) if emp and emp["department_id"] else "Unassigned"
        b = buckets.setdefault(dept, {"department": dept, "regular_cost": 0.0, "overtime_cost": 0.0, "pto_cost": 0.0})
        rate = d["hourly_rate"]
        b["regular_cost"] += d["regular_hours"] * rate
        b["overtime_cost"] += d["overtime_hours"] * rate * 1.5
        pto = pto_hours.get(emp["id"], 0.0) if emp else 0.0
        b["pto_cost"] += pto * rate

    rows = []
    for b in buckets.values():
        rows.append({
            "department": b["department"],
            "regular_cost": round(b["regular_cost"], 2),
            "overtime_cost": round(b["overtime_cost"], 2),
            "pto_cost": round(b["pto_cost"], 2),
            "total_cost": round(b["regular_cost"] + b["overtime_cost"] + b["pto_cost"], 2),
        })
    rows.sort(key=lambda r: r["department"])
    return rows


def timecard_audit_rows(conn, org, period_start, period_end):
    """Manual time-entry additions/deletions from the audit log, for the period."""
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    logs = conn.execute(
        "SELECT al.*, a.username AS admin_username FROM audit_log al "
        "LEFT JOIN admin_users a ON al.actor_type='admin' AND al.actor_id=a.id "
        "WHERE al.org_id=%s AND al.action LIKE 'time_entry.%%' "
        "AND al.created_at>=%s AND al.created_at<=%s "
        "ORDER BY al.created_at DESC",
        (org["id"], period_start_dt, period_end_dt),
    ).fetchall()
    return [
        {
            "timestamp": l["created_at"],
            "action": l["action"].replace("time_entry.", "").replace("_", " ").title(),
            "actor": l["admin_username"] or "System",
            "detail": l["detail"] or "",
        }
        for l in logs
    ]


def payroll_export_rows(conn, org, period_start, period_end):
    """Hours and gross pay by employee, with approval status, ready for payroll."""
    summary = timesheet_summary_rows(conn, org, period_start, period_end)
    approvals = {r["employee_code"]: r for r in approval_status_rows(conn, org, period_start, period_end)}
    employees = _employees_by_code(conn, org["id"])

    rows = []
    for s in summary:
        emp = employees.get(s["employee_code"])
        approval = approvals.get(s["employee_code"])
        rate = emp["hourly_rate"] if emp else 0
        gross_pay = round(s["regular_hours"] * rate + s["overtime_hours"] * rate * 1.5, 2)
        rows.append({
            "employee_code": s["employee_code"],
            "name": s["name"],
            "regular_hours": s["regular_hours"],
            "overtime_hours": s["overtime_hours"],
            "pto_hours": s["pto_hours"],
            "rate": rate,
            "gross_pay": gross_pay,
            "approval_status": approval["status"] if approval else "pending",
        })
    return rows
