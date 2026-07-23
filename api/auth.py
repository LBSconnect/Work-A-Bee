import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, request

import config
from api.errors import ApiError
from models import get_db

ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)
JWT_ALGORITHM = "HS256"


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _issue_access_token(org_id, subject_type, subject_id):
    now = datetime.now(timezone.utc)
    claims = {
        "sub": subject_id,
        "org_id": org_id,
        "role": subject_type,
        "iat": now,
        "exp": now + ACCESS_TOKEN_TTL,
    }
    return jwt.encode(claims, config.SECRET_KEY, algorithm=JWT_ALGORITHM)


def issue_tokens(conn, org_id, subject_type, subject_id, device_label=None):
    """Issues a short-lived JWT access token plus a long-lived opaque refresh
    token. Only the refresh token's hash is stored - refresh tokens are high
    entropy (32 random bytes), so a fast SHA-256 lookup hash is appropriate
    here (unlike passwords/PINs, which need slow hashing because they're
    low-entropy and guessable)."""
    access_token = _issue_access_token(org_id, subject_type, subject_id)
    raw_refresh = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO api_refresh_tokens (org_id, subject_type, subject_id, token_hash, "
        "device_label, expires_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (org_id, subject_type, subject_id, _hash_token(raw_refresh), device_label,
         datetime.now(timezone.utc) + REFRESH_TOKEN_TTL),
    )
    conn.commit()
    return access_token, raw_refresh


def verify_access_token(raw_token):
    try:
        return jwt.decode(raw_token, config.SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def rotate_refresh_token(conn, raw_refresh_token, device_label=None):
    """Verifies and revokes the given refresh token, then issues a new
    access/refresh pair. Returns None if the token is unknown, expired, or
    already revoked."""
    row = conn.execute(
        "SELECT * FROM api_refresh_tokens WHERE token_hash=%s", (_hash_token(raw_refresh_token),)
    ).fetchone()
    if row is None or row["revoked_at"] is not None:
        return None
    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    conn.execute(
        "UPDATE api_refresh_tokens SET revoked_at=NOW(), last_used_at=NOW() WHERE id=%s",
        (row["id"],),
    )
    conn.commit()
    return issue_tokens(conn, row["org_id"], row["subject_type"], row["subject_id"], device_label)


def revoke_refresh_token(conn, raw_refresh_token):
    conn.execute(
        "UPDATE api_refresh_tokens SET revoked_at=NOW() WHERE token_hash=%s AND revoked_at IS NULL",
        (_hash_token(raw_refresh_token),),
    )
    conn.commit()


def _bearer_token():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()


def api_employee_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        claims = verify_access_token(token) if token else None
        if not claims or claims.get("role") != "employee":
            raise ApiError("unauthorized", "Missing or invalid access token.", 401)

        with get_db() as conn:
            emp = conn.execute(
                "SELECT * FROM employees WHERE id=%s AND org_id=%s AND active=1",
                (claims["sub"], claims["org_id"]),
            ).fetchone()
            org = conn.execute(
                "SELECT * FROM organizations WHERE id=%s AND status='active'", (claims["org_id"],)
            ).fetchone()
        if emp is None or org is None:
            raise ApiError("unauthorized", "This account is no longer active.", 401)

        g.api_employee = emp
        g.api_org = org
        return f(*args, **kwargs)
    return wrapper


def api_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        claims = verify_access_token(token) if token else None
        if not claims or claims.get("role") != "admin":
            raise ApiError("unauthorized", "Missing or invalid access token.", 401)

        with get_db() as conn:
            admin = conn.execute(
                "SELECT * FROM admin_users WHERE id=%s AND org_id=%s",
                (claims["sub"], claims["org_id"]),
            ).fetchone()
            org = conn.execute(
                "SELECT * FROM organizations WHERE id=%s AND status='active'", (claims["org_id"],)
            ).fetchone()
        if admin is None or org is None:
            raise ApiError("unauthorized", "This account is no longer active.", 401)

        g.api_admin = admin
        g.api_org = org
        return f(*args, **kwargs)
    return wrapper
