from flask import Blueprint, g, jsonify, request

from api.auth import api_admin_required, api_employee_required
from api.errors import ApiError
from models import get_db

# No url_prefix: this registers under both /api/v1/employee and /api/v1/admin,
# mirroring how each role already gets its own endpoint namespace elsewhere
# (see api/employee/*.py and api/admin/*.py).
api_push_tokens_bp = Blueprint("api_push_tokens", __name__)


def _token_from_body():
    data = request.get_json(silent=True) or {}
    token = (data.get("token") or "").strip()
    # Expo push tokens ("ExponentPushToken[...]", or the legacy
    # "ExpoPushToken[...]") don't have a fixed length - they wrap an opaque,
    # variable-length device identifier - so there's no meaningful length
    # check here, only a shape check.
    if not token or "[" not in token or not token.endswith("]"):
        raise ApiError("validation_error", "A valid Expo push token is required.", 422)
    return token


def _upsert(conn, org_id, subject_type, subject_id, token):
    # ON CONFLICT reassigns the row rather than erroring, since the same
    # physical device's token can end up registered to a different
    # subject (e.g. a shared device where one employee signs out and
    # another signs in) - see the push_tokens table comment in models.py.
    conn.execute(
        """
        INSERT INTO push_tokens (org_id, subject_type, subject_id, token)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (token) DO UPDATE SET
            org_id = EXCLUDED.org_id,
            subject_type = EXCLUDED.subject_type,
            subject_id = EXCLUDED.subject_id,
            last_used_at = NOW()
        """,
        (org_id, subject_type, subject_id, token),
    )


def _delete(conn, subject_type, subject_id, token):
    conn.execute(
        "DELETE FROM push_tokens WHERE subject_type=%s AND subject_id=%s AND token=%s",
        (subject_type, subject_id, token),
    )


@api_push_tokens_bp.route("/api/v1/employee/push-token", methods=["POST"])
@api_employee_required
def register_employee_push_token():
    token = _token_from_body()
    with get_db() as conn:
        _upsert(conn, g.api_org["id"], "employee", g.api_employee["id"], token)
    return jsonify({"ok": True})


@api_push_tokens_bp.route("/api/v1/employee/push-token", methods=["DELETE"])
@api_employee_required
def unregister_employee_push_token():
    token = _token_from_body()
    with get_db() as conn:
        _delete(conn, "employee", g.api_employee["id"], token)
    return jsonify({"ok": True})


@api_push_tokens_bp.route("/api/v1/admin/push-token", methods=["POST"])
@api_admin_required
def register_admin_push_token():
    token = _token_from_body()
    with get_db() as conn:
        _upsert(conn, g.api_org["id"], "admin", g.api_admin["id"], token)
    return jsonify({"ok": True})


@api_push_tokens_bp.route("/api/v1/admin/push-token", methods=["DELETE"])
@api_admin_required
def unregister_admin_push_token():
    token = _token_from_body()
    with get_db() as conn:
        _delete(conn, "admin", g.api_admin["id"], token)
    return jsonify({"ok": True})
