def log(conn, org_id, actor_type, actor_id, action, detail=None):
    conn.execute(
        "INSERT INTO audit_log (org_id, actor_type, actor_id, action, detail) "
        "VALUES (%s, %s, %s, %s, %s)",
        (org_id, actor_type, actor_id, action, detail),
    )
