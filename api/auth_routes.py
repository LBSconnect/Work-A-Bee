from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash

import plans
from api.auth import (
    api_admin_required,
    api_employee_required,
    issue_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from api.errors import ApiError
from models import get_db
from orgs import get_active_org

api_auth_bp = Blueprint("api_auth", __name__, url_prefix="/api/v1/auth")


def _org_features(org):
    return {key: plans.feature_available(org, key) for key in plans.FEATURE_TIERS}


@api_auth_bp.route("/employee/login", methods=["POST"])
def employee_login():
    data = request.get_json(silent=True) or {}
    company_code = data.get("company_code", "")
    employee_code = (data.get("employee_code") or "").strip()
    pin = (data.get("pin") or "").strip()
    device_label = data.get("device_label")

    with get_db() as conn:
        org = get_active_org(conn, company_code)
        emp = None
        if org is not None:
            emp = conn.execute(
                "SELECT * FROM employees WHERE org_id=%s AND employee_code=%s AND active=1",
                (org["id"], employee_code),
            ).fetchone()
        if org is None or emp is None or not check_password_hash(emp["pin_hash"], pin):
            raise ApiError("invalid_credentials", "Company code, Employee ID, or PIN not recognized.", 401)

        access_token, refresh_token = issue_tokens(conn, org["id"], "employee", emp["id"], device_label)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "employee": {"id": emp["id"], "name": emp["name"], "employee_code": emp["employee_code"]},
    })


@api_auth_bp.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    company_code = data.get("company_code", "")
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    device_label = data.get("device_label")

    with get_db() as conn:
        org = get_active_org(conn, company_code)
        admin = None
        if org is not None:
            admin = conn.execute(
                "SELECT * FROM admin_users WHERE org_id=%s AND username=%s", (org["id"], username)
            ).fetchone()
        if org is None or admin is None or not check_password_hash(admin["password_hash"], password):
            raise ApiError("invalid_credentials", "Company code, username, or password not recognized.", 401)

        access_token, refresh_token = issue_tokens(conn, org["id"], "admin", admin["id"], device_label)

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "admin": {"id": admin["id"], "username": admin["username"]},
    })


@api_auth_bp.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    raw_refresh = data.get("refresh_token", "")
    if not raw_refresh:
        raise ApiError("validation_error", "refresh_token is required.", 422)

    with get_db() as conn:
        result = rotate_refresh_token(conn, raw_refresh, data.get("device_label"))
    if result is None:
        raise ApiError("unauthorized", "Refresh token is invalid, expired, or already used.", 401)

    access_token, new_refresh = result
    return jsonify({"access_token": access_token, "refresh_token": new_refresh})


@api_auth_bp.route("/logout", methods=["POST"])
def logout():
    data = request.get_json(silent=True) or {}
    raw_refresh = data.get("refresh_token", "")
    if raw_refresh:
        with get_db() as conn:
            revoke_refresh_token(conn, raw_refresh)
    return jsonify({"ok": True})


@api_auth_bp.route("/me", methods=["GET"])
def me():
    token = request.headers.get("Authorization", "")
    if not token.startswith("Bearer "):
        raise ApiError("unauthorized", "Missing or invalid access token.", 401)

    from api.auth import verify_access_token
    claims = verify_access_token(token[len("Bearer "):].strip())
    if not claims:
        raise ApiError("unauthorized", "Missing or invalid access token.", 401)

    with get_db() as conn:
        org = conn.execute(
            "SELECT * FROM organizations WHERE id=%s AND status='active'", (claims["org_id"],)
        ).fetchone()
        if org is None:
            raise ApiError("unauthorized", "This account is no longer active.", 401)

        if claims["role"] == "employee":
            emp = conn.execute(
                "SELECT * FROM employees WHERE id=%s AND org_id=%s AND active=1",
                (claims["sub"], org["id"]),
            ).fetchone()
            if emp is None:
                raise ApiError("unauthorized", "This account is no longer active.", 401)
            identity = {"role": "employee", "id": emp["id"], "name": emp["name"], "employee_code": emp["employee_code"]}
        elif claims["role"] == "admin":
            admin = conn.execute(
                "SELECT * FROM admin_users WHERE id=%s AND org_id=%s", (claims["sub"], org["id"])
            ).fetchone()
            if admin is None:
                raise ApiError("unauthorized", "This account is no longer active.", 401)
            identity = {"role": "admin", "id": admin["id"], "username": admin["username"]}
        else:
            raise ApiError("unauthorized", "Missing or invalid access token.", 401)

    return jsonify({
        **identity,
        "org": {"id": org["id"], "name": org["name"], "timezone": org["timezone"]},
        "plan": plans.get_plan_key(org),
        "promo_active": plans.promo_active(org),
        "features": _org_features(org),
    })
