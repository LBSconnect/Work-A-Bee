import secrets

from werkzeug.security import generate_password_hash, check_password_hash

import config


def _cookie_name(org_id):
    return f"device_{org_id}"


def register_device(conn, org_id, device_name, admin_id=None):
    """Creates a device row and returns (device_id, raw_token). Only the hash is stored."""
    raw_token = secrets.token_urlsafe(32)
    row = conn.execute(
        "INSERT INTO devices (org_id, device_name, token_hash, registered_by_admin_id) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (org_id, device_name, generate_password_hash(raw_token), admin_id),
    ).fetchone()
    return row["id"], raw_token


def issue_device_cookie(resp, org_id, raw_token):
    resp.set_cookie(
        _cookie_name(org_id), raw_token, httponly=True, samesite="Lax",
        max_age=60 * 60 * 24 * 365 * 5, secure=config.ON_RENDER,
    )
    return resp


def is_trusted_device(request, org_id, conn):
    """An org with zero registered devices is unrestricted (opt-in lock-down)."""
    active = conn.execute(
        "SELECT * FROM devices WHERE org_id=%s AND status='active'", (org_id,)
    ).fetchall()
    if not active:
        return True

    raw_token = request.cookies.get(_cookie_name(org_id))
    if not raw_token:
        return False

    for d in active:
        if check_password_hash(d["token_hash"], raw_token):
            conn.execute(
                "UPDATE devices SET last_seen_at=NOW(), last_seen_ip=%s WHERE id=%s",
                (request.remote_addr, d["id"]),
            )
            return True
    return False
