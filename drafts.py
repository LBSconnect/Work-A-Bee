import secrets

from psycopg2.extras import Json

import config
from models import get_db

COOKIE_NAME = "wizard_token"
MAX_AGE = 60 * 60 * 24 * 3  # 3 days


def _new_token():
    return secrets.token_urlsafe(24)


def get_or_create_draft(request):
    """Returns (token, draft_row, is_new). Caller must attach_cookie() on the response if is_new."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        row = load_draft(token)
        if row:
            return token, row, False

    token = _new_token()
    with get_db() as conn:
        conn.execute("INSERT INTO signup_drafts (draft_token) VALUES (%s)", (token,))
        conn.commit()
    return token, load_draft(token), True


def attach_cookie(resp, token):
    resp.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="Lax",
        max_age=MAX_AGE, secure=config.ON_RENDER,
    )
    return resp


def load_draft(token):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM signup_drafts WHERE draft_token=%s", (token,)
        ).fetchone()


def save_step(token, fields, next_step=None):
    """Merge `fields` into the draft's JSON blob and optionally advance current_step."""
    row = load_draft(token)
    data = dict(row["data"] or {})
    data.update(fields)
    step = next_step if next_step is not None else row["current_step"]
    with get_db() as conn:
        conn.execute(
            "UPDATE signup_drafts SET data=%s::jsonb, current_step=%s, updated_at=NOW() WHERE draft_token=%s",
            (Json(data), step, token),
        )
        conn.commit()
    return data


def delete_draft(conn, token):
    conn.execute("DELETE FROM signup_drafts WHERE draft_token=%s", (token,))
