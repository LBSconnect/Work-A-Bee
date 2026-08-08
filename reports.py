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
            "employee_id": e["employee_id"],
            "employee_code": e["employee_code"],
            "name": e["name"],
            "date": e["clock_in"].date(),
            "issue": "Missing Clock-Out",
            "issue_type": "missing_clock_out",
            "time_entry_id": e["id"],
            "suggested_clock_in": e["clock_in"],
            "suggested_clock_out": None,
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
                "employee_id": s["employee_id"],
                "employee_code": s["employee_code"],
                "name": s["name"],
                "date": s["shift_start"].date(),
                "issue": "Missing Clock-In (No-Show)",
                "issue_type": "missing_clock_in",
                "time_entry_id": None,
                "suggested_clock_in": s["shift_start"],
                "suggested_clock_out": s["shift_end"],
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
    """Each active employee's timesheet-approval status for the period.

    Status is one of: not_submitted, submitted, returned, approved.
    "returned" means a manager sent it back for correction (either after
    review, or by reopening a previously-approved timesheet).
    """
    org_id = org["id"]
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    employees = conn.execute(
        "SELECT e.*, d.name AS department_name FROM employees e "
        "LEFT JOIN departments d ON e.department_id = d.id "
        "WHERE e.org_id=%s AND (e.active=1 "
        "OR EXISTS (SELECT 1 FROM timesheet_approvals ta WHERE ta.employee_id=e.id AND ta.org_id=%s "
        "AND ta.period_start=%s AND ta.period_end=%s) "
        "OR EXISTS (SELECT 1 FROM time_entries te WHERE te.employee_id=e.id "
        "AND te.clock_in>=%s AND te.clock_in<=%s)) "
        "ORDER BY e.name",
        (org_id, org_id, period_start, period_end, period_start_dt, period_end_dt),
    ).fetchall()
    approvals = conn.execute(
        "SELECT ta.*, a.username AS approved_by_username FROM timesheet_approvals ta "
        "LEFT JOIN admin_users a ON ta.approved_by_admin_id=a.id "
        "WHERE ta.org_id=%s AND ta.period_start=%s AND ta.period_end=%s",
        (org_id, period_start, period_end),
    ).fetchall()
    by_employee = {a["employee_id"]: a for a in approvals}
    summary_by_code = {r["employee_code"]: r for r in timesheet_summary_rows(conn, org, period_start, period_end)}

    rows = []
    for emp in employees:
        a = by_employee.get(emp["id"])
        s = summary_by_code.get(emp["employee_code"])
        regular_hours = s["regular_hours"] if s else 0.0
        overtime_hours = s["overtime_hours"] if s else 0.0
        total_hours = s["total_hours"] if s else 0.0
        gross_pay = round(regular_hours * emp["hourly_rate"] + overtime_hours * emp["hourly_rate"] * 1.5, 2)
        rows.append({
            "employee_id": emp["id"],
            "employee_code": emp["employee_code"],
            "name": emp["name"],
            "department_name": emp["department_name"] or "Unassigned",
            "status": a["status"] if a else "not_submitted",
            "submitted_at": a["submitted_at"] if a else None,
            "employee_notes": a["employee_notes"] if a else None,
            "manager_comment": a["manager_comment"] if a else None,
            "approved_by": a["approved_by_username"] if a and a["status"] == "approved" else None,
            "approved_at": a["approved_at"] if a else None,
            "total_hours": total_hours,
            "gross_pay": gross_pay,
        })
    return rows


def flagged_employee_codes(conn, org, period_start, period_end):
    """Employee codes with an attendance flag, overtime, or a missing punch this period."""
    flagged = set()
    for r in daily_attendance_rows(conn, org, period_start, period_end):
        if r["flags"] != "OK":
            flagged.add(r["employee_code"])
    for r in overtime_rows(conn, org, period_start, period_end):
        if r["status"] != "OK":
            flagged.add(r["employee_code"])
    for r in missing_punches_rows(conn, org, period_start, period_end):
        flagged.add(r["employee_code"])
    return flagged


def _upsert_approval(conn, org_id, employee_id, period_start, period_end, **fields):
    columns = ["org_id", "employee_id", "period_start", "period_end"] + list(fields.keys())
    values = [org_id, employee_id, period_start, period_end] + list(fields.values())
    placeholders = ",".join(["%s"] * len(values))
    update_clause = ", ".join(f"{k}=EXCLUDED.{k}" for k in fields.keys())
    conn.execute(
        f"INSERT INTO timesheet_approvals ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (employee_id, period_start, period_end) DO UPDATE SET {update_clause}",
        values,
    )


def submit_timesheet(conn, org_id, employee_id, period_start, period_end, notes):
    """Employee certifies and submits their timesheet for the period."""
    _upsert_approval(
        conn, org_id, employee_id, period_start, period_end,
        status="submitted", submitted_at=datetime.utcnow(), employee_notes=notes,
        manager_comment=None, approved_by_admin_id=None, approved_at=None,
    )


def withdraw_timesheet(conn, employee_id, period_start, period_end):
    """Employee pulls back a submission that hasn't been reviewed yet."""
    conn.execute(
        "DELETE FROM timesheet_approvals WHERE employee_id=%s AND period_start=%s AND period_end=%s "
        "AND status='submitted'",
        (employee_id, period_start, period_end),
    )


def approve_timesheet(conn, org_id, employee_id, period_start, period_end, admin_id):
    """Manager approves a timesheet, locking it from further employee edits."""
    _upsert_approval(
        conn, org_id, employee_id, period_start, period_end,
        status="approved", approved_by_admin_id=admin_id, approved_at=datetime.utcnow(),
        manager_comment=None,
    )


def return_timesheet(conn, org_id, employee_id, period_start, period_end, admin_id, comment):
    """Manager sends a timesheet back for correction (or reopens an approved one), with a required comment/reason."""
    _upsert_approval(
        conn, org_id, employee_id, period_start, period_end,
        status="returned", manager_comment=comment, approved_by_admin_id=admin_id, approved_at=None,
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
            "approval_status": (approval["status"] if approval else "not_submitted").replace("_", " ").title(),
        })
    return rows


def my_timesheet(conn, org, employee, period_start, period_end):
    """A single employee's own timesheet: hours breakdown, missing punches, and approval state."""
    summary = next(
        (r for r in timesheet_summary_rows(conn, org, period_start, period_end)
         if r["employee_code"] == employee["employee_code"]),
        {"regular_hours": 0.0, "overtime_hours": 0.0, "pto_hours": 0.0, "total_hours": 0.0, "incomplete": False},
    )
    missing = [
        r for r in missing_punches_rows(conn, org, period_start, period_end)
        if r["employee_code"] == employee["employee_code"]
    ]
    approval = next(
        (r for r in approval_status_rows(conn, org, period_start, period_end)
         if r["employee_code"] == employee["employee_code"]),
        None,
    )
    return {"summary": summary, "missing_punches": missing, "approval": approval}


def corrections_by_issue(conn, org_id, employee_id=None):
    """Map (employee_id, issue_type, issue_date) -> most recent punch_corrections row for that issue."""
    query = "SELECT * FROM punch_corrections WHERE org_id=%s"
    params = [org_id]
    if employee_id is not None:
        query += " AND employee_id=%s"
        params.append(employee_id)
    query += " ORDER BY created_at"
    result = {}
    for r in conn.execute(query, params).fetchall():
        result[(r["employee_id"], r["issue_type"], r["issue_date"])] = r
    return result


def employee_corrections(conn, employee_id, limit=20):
    """An employee's own correction requests, most recent first."""
    return conn.execute(
        "SELECT * FROM punch_corrections WHERE employee_id=%s ORDER BY created_at DESC LIMIT %s",
        (employee_id, limit),
    ).fetchall()


def submit_correction_request(conn, org_id, employee_id, issue_type, issue_date, time_entry_id,
                               requested_clock_in, requested_clock_out, reason):
    conn.execute(
        "INSERT INTO punch_corrections "
        "(org_id, employee_id, time_entry_id, issue_type, issue_date, requested_clock_in, requested_clock_out, reason) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
        (org_id, employee_id, time_entry_id, issue_type, issue_date, requested_clock_in, requested_clock_out, reason),
    )


def corrections_queue(conn, org):
    """All correction requests for the org, pending first, then most recently created."""
    return conn.execute(
        "SELECT pc.*, e.name, e.employee_code FROM punch_corrections pc "
        "JOIN employees e ON pc.employee_id = e.id "
        "WHERE pc.org_id=%s ORDER BY (pc.status='pending') DESC, pc.created_at DESC",
        (org["id"],),
    ).fetchall()


def _pending_correction(conn, org_id, correction_id):
    return conn.execute(
        "SELECT pc.*, e.name, e.employee_code FROM punch_corrections pc "
        "JOIN employees e ON pc.employee_id = e.id "
        "WHERE pc.id=%s AND pc.org_id=%s AND pc.status='pending'",
        (correction_id, org_id),
    ).fetchone()


def approve_correction(conn, org_id, correction_id, admin_id):
    """Applies the requested correction to time_entries and marks the request approved.
    Returns the correction row (with employee name/code) for notification/audit, or None if not pending."""
    c = _pending_correction(conn, org_id, correction_id)
    if c is None:
        return None

    if c["issue_type"] == "missing_clock_out":
        conn.execute(
            "UPDATE time_entries SET clock_out=%s, is_manual=TRUE, created_by_admin_id=%s WHERE id=%s",
            (c["requested_clock_out"], admin_id, c["time_entry_id"]),
        )
    else:
        conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in, clock_out, is_manual, created_by_admin_id) "
            "VALUES (%s,%s,%s,TRUE,%s)",
            (c["employee_id"], c["requested_clock_in"], c["requested_clock_out"], admin_id),
        )
    conn.execute(
        "UPDATE punch_corrections SET status='approved', reviewed_by_admin_id=%s, reviewed_at=NOW() WHERE id=%s",
        (admin_id, correction_id),
    )
    c["status"] = "approved"
    return c


def deny_correction(conn, org_id, correction_id, admin_id, comment):
    c = _pending_correction(conn, org_id, correction_id)
    if c is None:
        return None
    conn.execute(
        "UPDATE punch_corrections SET status='denied', reviewed_by_admin_id=%s, reviewed_at=NOW(), manager_comment=%s "
        "WHERE id=%s",
        (admin_id, comment, correction_id),
    )
    c["status"] = "denied"
    c["manager_comment"] = comment
    return c


def _pending_pto_request(conn, org_id, request_id):
    return conn.execute(
        "SELECT r.*, e.name AS employee_name, e.employee_code, e.pto_balance_hours FROM pto_requests r "
        "JOIN employees e ON r.employee_id = e.id "
        "WHERE r.id=%s AND r.org_id=%s AND r.status='pending'",
        (request_id, org_id),
    ).fetchone()


def approve_pto(conn, org_id, request_id, admin_id):
    """Marks a pending PTO request approved and deducts the hours from the employee's
    balance (allowed to go negative - callers should warn if it would). Returns the
    request row (with employee_name/pto_balance_hours, pre-deduction) for
    notification/audit, or None if not found/already reviewed."""
    req = _pending_pto_request(conn, org_id, request_id)
    if req is None:
        return None
    conn.execute(
        "UPDATE pto_requests SET status='approved', reviewed_by_admin_id=%s, reviewed_at=NOW() WHERE id=%s",
        (admin_id, request_id),
    )
    conn.execute(
        "UPDATE employees SET pto_balance_hours = pto_balance_hours - %s WHERE id=%s",
        (req["hours"], req["employee_id"]),
    )
    req["status"] = "approved"
    return req


def deny_pto(conn, org_id, request_id, admin_id):
    req = _pending_pto_request(conn, org_id, request_id)
    if req is None:
        return None
    conn.execute(
        "UPDATE pto_requests SET status='denied', reviewed_by_admin_id=%s, reviewed_at=NOW() WHERE id=%s",
        (admin_id, request_id),
    )
    req["status"] = "denied"
    return req


def overlapping_shifts_rows(conn, org, period_start, period_end):
    """Pairs of shifts for the same employee whose time ranges intersect."""
    org_id = org["id"]
    period_start_dt = datetime.combine(period_start, datetime.min.time())
    period_end_dt = datetime.combine(period_end, datetime.max.time())
    shifts = conn.execute(
        "SELECT s.*, e.name, e.employee_code FROM shifts s JOIN employees e ON s.employee_id = e.id "
        "WHERE s.org_id=%s AND s.shift_start<=%s AND s.shift_end>=%s "
        "ORDER BY s.employee_id, s.shift_start",
        (org_id, period_end_dt, period_start_dt),
    ).fetchall()

    by_employee = {}
    for s in shifts:
        by_employee.setdefault(s["employee_id"], []).append(s)

    rows = []
    for emp_id, emp_shifts in by_employee.items():
        emp_shifts.sort(key=lambda s: s["shift_start"])
        for i in range(len(emp_shifts) - 1):
            a, b = emp_shifts[i], emp_shifts[i + 1]
            if b["shift_start"] < a["shift_end"]:
                rows.append({
                    "employee_id": emp_id,
                    "employee_code": a["employee_code"],
                    "name": a["name"],
                    "date": a["shift_start"].date(),
                    "detail": f'{a["shift_start"].strftime("%I:%M %p").lstrip("0")}–'
                              f'{a["shift_end"].strftime("%I:%M %p").lstrip("0")} overlaps '
                              f'{b["shift_start"].strftime("%I:%M %p").lstrip("0")}–'
                              f'{b["shift_end"].strftime("%I:%M %p").lstrip("0")}',
                })
    return rows


def exceptions_inbox(conn, org, period_start, period_end):
    """Aggregated, actionable list of attendance/scheduling exceptions for the period.

    Covers what's detectable from existing data: late arrivals, early departures,
    missing punches, overtime, overlapping shifts, unsubmitted timesheets (for
    periods that have already ended), and pending punch-correction requests.
    Missed-break and location-mismatch exceptions aren't included - the app
    doesn't track breaks or clock-in location yet.
    """
    org_id = org["id"]
    now = now_in(org["timezone"])
    exceptions = []

    for r in daily_attendance_rows(conn, org, period_start, period_end):
        if "Late" in r["flags"]:
            exceptions.append({
                "employee_id": None, "employee_code": r["employee_code"], "name": r["name"],
                "date": r["date"], "exception_type": "late_arrival", "label": "Late Arrival",
                "detail": f'Scheduled {r["scheduled_start"].strftime("%I:%M %p").lstrip("0")}, '
                          f'clocked in {r["actual_in"].strftime("%I:%M %p").lstrip("0")}',
            })
        if "Early Departure" in r["flags"]:
            exceptions.append({
                "employee_id": None, "employee_code": r["employee_code"], "name": r["name"],
                "date": r["date"], "exception_type": "early_departure", "label": "Early Departure",
                "detail": f'Scheduled until {r["scheduled_end"].strftime("%I:%M %p").lstrip("0")}, '
                          f'clocked out {r["actual_out"].strftime("%I:%M %p").lstrip("0")}',
            })

    for r in missing_punches_rows(conn, org, period_start, period_end):
        exceptions.append({
            "employee_id": r.get("employee_id"), "employee_code": r["employee_code"], "name": r["name"],
            "date": r["date"], "exception_type": "missing_punch", "label": r["issue"],
            "detail": r["detail"],
        })

    for r in overtime_rows(conn, org, period_start, period_end):
        if r["status"] != "OK":
            exceptions.append({
                "employee_id": None, "employee_code": r["employee_code"], "name": r["name"],
                "date": period_end, "exception_type": "overtime", "label": f'Overtime: {r["status"]}',
                "detail": f'{r["total_hours"]} hrs vs {r["threshold_hours"]} hr threshold '
                          f'({r["pct_of_threshold"]}%)',
            })

    for r in overlapping_shifts_rows(conn, org, period_start, period_end):
        exceptions.append({
            "employee_id": r["employee_id"], "employee_code": r["employee_code"], "name": r["name"],
            "date": r["date"], "exception_type": "overlapping_shifts", "label": "Overlapping Shifts",
            "detail": r["detail"],
        })

    if period_end < now.date():
        for r in approval_status_rows(conn, org, period_start, period_end):
            if r["status"] == "not_submitted":
                exceptions.append({
                    "employee_id": r["employee_id"], "employee_code": r["employee_code"], "name": r["name"],
                    "date": period_end, "exception_type": "timesheet_not_submitted",
                    "label": "Timesheet Not Submitted",
                    "detail": f'No timesheet submitted for {period_start.strftime("%b %d")}'
                              f'–{period_end.strftime("%b %d, %Y")}',
                })

    for c in corrections_queue(conn, org):
        if c["status"] == "pending" and period_start <= c["issue_date"] <= period_end:
            exceptions.append({
                "employee_id": c["employee_id"], "employee_code": c["employee_code"], "name": c["name"],
                "date": c["issue_date"], "exception_type": "correction_pending", "label": "Correction Pending",
                "detail": f'{c["issue_type"].replace("_", " ").title()} – awaiting review',
            })

    employees_by_code = _employees_by_code(conn, org_id)
    for e in exceptions:
        if e["employee_id"] is None:
            emp = employees_by_code.get(e["employee_code"])
            e["employee_id"] = emp["id"] if emp else None

    dismissed = {
        (d["employee_id"], d["exception_type"], d["exception_date"]): d
        for d in conn.execute(
            "SELECT * FROM exception_dismissals WHERE org_id=%s AND exception_date BETWEEN %s AND %s",
            (org_id, period_start, period_end),
        ).fetchall()
    }
    for e in exceptions:
        e["dismissal"] = dismissed.get((e["employee_id"], e["exception_type"], e["date"]))

    exceptions.sort(key=lambda e: (e["dismissal"] is not None, e["date"]))
    return exceptions


def dismiss_exception(conn, org_id, employee_id, exception_type, exception_date, admin_id, note):
    conn.execute(
        "INSERT INTO exception_dismissals "
        "(org_id, employee_id, exception_type, exception_date, note, dismissed_by_admin_id) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT (employee_id, exception_type, exception_date) DO UPDATE SET "
        "note=EXCLUDED.note, dismissed_by_admin_id=EXCLUDED.dismissed_by_admin_id, dismissed_at=NOW()",
        (org_id, employee_id, exception_type, exception_date, note, admin_id),
    )


def payroll_readiness_summary(conn, org, period_start, period_end):
    """Rolls up everything blocking a clean payroll run for the period:
    timesheet approval status across the team and any open exceptions."""
    approval_rows = approval_status_rows(conn, org, period_start, period_end)
    status_counts = {"not_submitted": 0, "submitted": 0, "returned": 0, "approved": 0}
    for r in approval_rows:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    open_exceptions = [e for e in exceptions_inbox(conn, org, period_start, period_end) if e["dismissal"] is None]
    not_approved_rows = [r for r in approval_rows if r["status"] != "approved"]
    total_employees = len(approval_rows)

    return {
        "total_employees": total_employees,
        "status_counts": status_counts,
        "not_approved_rows": not_approved_rows,
        "open_exceptions": open_exceptions,
        "open_exceptions_count": len(open_exceptions),
        "total_gross_pay": round(sum(r["gross_pay"] for r in approval_rows), 2),
        "is_ready": total_employees > 0 and not not_approved_rows and not open_exceptions,
    }
