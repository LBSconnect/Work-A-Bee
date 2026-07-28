DEFAULT_TASKS = [
    ("Confirm pay rate, worker type, and department", "admin"),
    ("Add them to the work schedule", "admin"),
    ("Share their Employee ID and PIN for the time clock", "admin"),
    ("Complete your profile (photo, email, phone)", "employee"),
    ("Review the employee handbook and company policies", "employee"),
    ("Check your first schedule and confirm your availability", "employee"),
]


def ensure_default_tasks(conn, org_id):
    """Seeds a starter checklist the first time an org touches onboarding, so
    admins aren't looking at an empty template. No-ops once any task exists,
    including if every default was later deleted."""
    existing = conn.execute(
        "SELECT COUNT(*) AS c FROM onboarding_tasks WHERE org_id=%s", (org_id,)
    ).fetchone()["c"]
    if existing:
        return
    for i, (title, assigned_to) in enumerate(DEFAULT_TASKS):
        conn.execute(
            "INSERT INTO onboarding_tasks (org_id, title, assigned_to, sort_order) VALUES (%s,%s,%s,%s)",
            (org_id, title, assigned_to, i),
        )
    conn.commit()


def list_tasks(conn, org_id, include_inactive=True):
    query = "SELECT * FROM onboarding_tasks WHERE org_id=%s"
    if not include_inactive:
        query += " AND active=1"
    query += " ORDER BY sort_order, id"
    return conn.execute(query, (org_id,)).fetchall()


def create_task(conn, org_id, title, assigned_to):
    next_order = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM onboarding_tasks WHERE org_id=%s", (org_id,)
    ).fetchone()["n"]
    conn.execute(
        "INSERT INTO onboarding_tasks (org_id, title, assigned_to, sort_order) VALUES (%s,%s,%s,%s)",
        (org_id, title, assigned_to, next_order),
    )
    conn.commit()


def update_task(conn, org_id, task_id, title, assigned_to):
    conn.execute(
        "UPDATE onboarding_tasks SET title=%s, assigned_to=%s WHERE id=%s AND org_id=%s",
        (title, assigned_to, task_id, org_id),
    )
    conn.commit()


def set_task_active(conn, org_id, task_id, active):
    conn.execute(
        "UPDATE onboarding_tasks SET active=%s WHERE id=%s AND org_id=%s",
        (1 if active else 0, task_id, org_id),
    )
    conn.commit()


def progress_for_employee(conn, org_id, employee_id):
    """Active tasks for the org, each annotated with this employee's completion
    status. Returns (rows, completed_count, total_count)."""
    tasks = conn.execute(
        "SELECT * FROM onboarding_tasks WHERE org_id=%s AND active=1 ORDER BY sort_order, id", (org_id,)
    ).fetchall()
    completions = conn.execute(
        "SELECT task_id, completed_at, completed_by FROM onboarding_task_completions WHERE employee_id=%s",
        (employee_id,),
    ).fetchall()
    completed_by_task = {c["task_id"]: c for c in completions}

    rows = []
    for t in tasks:
        c = completed_by_task.get(t["id"])
        row = dict(t)
        row["completed"] = c is not None
        row["completed_at"] = c["completed_at"] if c else None
        row["completed_by"] = c["completed_by"] if c else None
        rows.append(row)
    completed_count = sum(1 for r in rows if r["completed"])
    return rows, completed_count, len(rows)


def onboarding_summary(conn, org_id):
    """Employees currently going through onboarding: active, hired since this
    feature existed (hire_date is set), and not yet marked complete."""
    employees = conn.execute(
        "SELECT * FROM employees WHERE org_id=%s AND active=1 AND hire_date IS NOT NULL "
        "AND onboarding_completed_at IS NULL ORDER BY hire_date DESC, name",
        (org_id,),
    ).fetchall()
    rows = []
    for emp in employees:
        _, completed_count, total_count = progress_for_employee(conn, org_id, emp["id"])
        rows.append({
            "employee": emp,
            "completed_count": completed_count,
            "total_count": total_count,
        })
    return rows


def _recompute_completion_flag(conn, org_id, employee_id):
    _, completed_count, total_count = progress_for_employee(conn, org_id, employee_id)
    emp = conn.execute("SELECT onboarding_completed_at FROM employees WHERE id=%s", (employee_id,)).fetchone()
    is_complete = total_count > 0 and completed_count == total_count
    if is_complete and emp["onboarding_completed_at"] is None:
        conn.execute("UPDATE employees SET onboarding_completed_at=NOW() WHERE id=%s", (employee_id,))
    elif not is_complete and emp["onboarding_completed_at"] is not None:
        conn.execute("UPDATE employees SET onboarding_completed_at=NULL WHERE id=%s", (employee_id,))


def toggle_completion(conn, org_id, employee_id, task_id, completed_by):
    """Flips one task's completion for one employee, then re-derives whether
    the employee's whole checklist is now complete (or no longer is)."""
    existing = conn.execute(
        "SELECT 1 FROM onboarding_task_completions WHERE employee_id=%s AND task_id=%s",
        (employee_id, task_id),
    ).fetchone()
    if existing:
        conn.execute(
            "DELETE FROM onboarding_task_completions WHERE employee_id=%s AND task_id=%s",
            (employee_id, task_id),
        )
    else:
        conn.execute(
            "INSERT INTO onboarding_task_completions (employee_id, task_id, completed_by) VALUES (%s,%s,%s)",
            (employee_id, task_id, completed_by),
        )
    _recompute_completion_flag(conn, org_id, employee_id)
    conn.commit()


def set_complete(conn, org_id, employee_id, complete):
    if complete:
        conn.execute(
            "UPDATE employees SET onboarding_completed_at=NOW() WHERE id=%s AND org_id=%s",
            (employee_id, org_id),
        )
    else:
        conn.execute(
            "UPDATE employees SET onboarding_completed_at=NULL WHERE id=%s AND org_id=%s",
            (employee_id, org_id),
        )
    conn.commit()
