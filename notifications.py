import notify_email
import notify_push


def notify_employee(conn, org_id, employee_id, kind, title, body=None, link=None):
    conn.execute(
        "INSERT INTO notifications (org_id, employee_id, kind, title, body, link) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (org_id, employee_id, kind, title, body, link),
    )
    emp = conn.execute("SELECT email FROM employees WHERE id=%s", (employee_id,)).fetchone()
    if emp and emp["email"]:
        notify_email.send_email(emp["email"], title, body or title)
    _push(conn, "employee", employee_id, title, body, link)


def notify_admins(conn, org_id, kind, title, body=None, link=None):
    admins = conn.execute("SELECT id, email FROM admin_users WHERE org_id=%s", (org_id,)).fetchall()
    for a in admins:
        conn.execute(
            "INSERT INTO notifications (org_id, admin_id, kind, title, body, link) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (org_id, a["id"], kind, title, body, link),
        )
        if a["email"]:
            notify_email.send_email(a["email"], title, body or title)
        _push(conn, "admin", a["id"], title, body, link)


def _push(conn, subject_type, subject_id, title, body, link):
    """Pushes to every device this subject has registered (see
    api/push_tokens.py), then prunes any token Expo reports as stale."""
    rows = conn.execute(
        "SELECT token FROM push_tokens WHERE subject_type=%s AND subject_id=%s",
        (subject_type, subject_id),
    ).fetchall()
    tokens = [r["token"] for r in rows]
    if not tokens:
        return
    stale = notify_push.send_push(tokens, title, body or title, {"link": link} if link else None)
    if stale:
        conn.execute("DELETE FROM push_tokens WHERE token = ANY(%s)", (stale,))
