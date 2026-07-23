import notify_email


def notify_employee(conn, org_id, employee_id, kind, title, body=None, link=None):
    conn.execute(
        "INSERT INTO notifications (org_id, employee_id, kind, title, body, link) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (org_id, employee_id, kind, title, body, link),
    )
    emp = conn.execute("SELECT email FROM employees WHERE id=%s", (employee_id,)).fetchone()
    if emp and emp["email"]:
        notify_email.send_email(emp["email"], title, body or title)


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
