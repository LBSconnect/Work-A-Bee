import base64
import csv
import io
import traceback

from flask import Blueprint, request, redirect, url_for, render_template, flash, session, make_response, jsonify
from werkzeug.security import generate_password_hash

import stripe

import billing
import choices
import devices as devices_mod
from drafts import get_or_create_draft, save_step, attach_cookie, COOKIE_NAME
from models import get_db

wizard = Blueprint("wizard", __name__)

PASSWORD_RULES = [
    ("length", "At least 12 characters", lambda p: len(p) >= 12),
    ("upper", "An uppercase letter", lambda p: any(c.isupper() for c in p)),
    ("lower", "A lowercase letter", lambda p: any(c.islower() for c in p)),
    ("number", "A number", lambda p: any(c.isdigit() for c in p)),
    ("symbol", "A special character", lambda p: any(not c.isalnum() for c in p)),
]

CSV_MAX_BYTES = 1_000_000
CSV_MAX_ROWS = 500

CSV_HEADER_ALIASES = {
    "first_name": "first_name", "first name": "first_name", "firstname": "first_name",
    "last_name": "last_name", "last name": "last_name", "lastname": "last_name",
    "employee_id": "employee_code", "employee id": "employee_code", "employee_code": "employee_code",
    "email": "email", "phone": "phone",
    "department": "department", "job_title": "job_title", "job title": "job_title", "title": "job_title",
    "hourly_rate": "hourly_rate", "hourly rate": "hourly_rate", "rate": "hourly_rate",
    "manager": "manager", "status": "status", "role": "role", "pin": "pin",
}


def _password_check(password):
    return {key: rule(password or "") for key, _, rule in PASSWORD_RULES}


def _ensure_draft():
    token, row, _ = get_or_create_draft(request)
    return token, row


def _wrap(token, body):
    resp = make_response(body)
    return attach_cookie(resp, token)


@wizard.route("/signup", methods=["GET"])
def signup_entry():
    token, draft = _ensure_draft()
    plan = request.args.get("plan")
    if plan in ("starter", "growth", "business"):
        save_step(token, {"plan": plan})
    return _wrap(token, redirect(url_for("wizard.step_company")))


@wizard.route("/signup/restart")
def signup_restart():
    resp = make_response(redirect(url_for("wizard.step_company")))
    resp.delete_cookie(COOKIE_NAME)
    return resp


@wizard.route("/signup/company", methods=["GET", "POST"])
def step_company():
    token, draft = _ensure_draft()
    data = dict(draft["data"].get("company", {}))
    errors = {}

    if request.method == "POST":
        fields = {
            "name": request.form.get("company_name", "").strip(),
            "dba_name": request.form.get("dba_name", "").strip(),
            "business_type": request.form.get("business_type", "").strip(),
            "industry": request.form.get("industry", "").strip(),
            "address_line1": request.form.get("address_line1", "").strip(),
            "city": request.form.get("city", "").strip(),
            "state": request.form.get("state", "").strip(),
            "zip": request.form.get("zip", "").strip(),
            "country": request.form.get("country", "United States").strip() or "United States",
            "phone": request.form.get("phone", "").strip(),
            "website": request.form.get("website", "").strip(),
        }
        if not fields["name"]:
            errors["company_name"] = "Company name is required."
        if not fields["address_line1"]:
            errors["address_line1"] = "Address is required."
        if not fields["phone"]:
            errors["phone"] = "Phone number is required."

        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            raw = logo_file.read()
            if len(raw) > 500 * 1024:
                errors["logo"] = "Logo must be 500KB or smaller."
            elif logo_file.mimetype not in ("image/png", "image/jpeg", "image/svg+xml"):
                errors["logo"] = "Logo must be a PNG, JPEG, or SVG file."
            else:
                fields["logo_b64"] = base64.b64encode(raw).decode("ascii")
                fields["logo_mime"] = logo_file.mimetype
        elif data.get("logo_b64"):
            fields["logo_b64"] = data["logo_b64"]
            fields["logo_mime"] = data.get("logo_mime")

        if errors:
            return _wrap(token, render_template(
                "wizard/step1_company.html", data={**data, **fields}, errors=errors, choices=choices, step_num=1,
            ))

        save_step(token, {"company": fields}, next_step=2)
        return _wrap(token, redirect(url_for("wizard.step_admin")))

    return _wrap(token, render_template("wizard/step1_company.html", data=data, errors=errors, choices=choices, step_num=1))


@wizard.route("/signup/admin", methods=["GET", "POST"])
def step_admin():
    token, draft = _ensure_draft()
    data = dict(draft["data"].get("admin", {}))
    errors = {}
    checks = {key: False for key, _, _ in PASSWORD_RULES}

    if request.method == "POST":
        fields = {
            "first_name": request.form.get("first_name", "").strip(),
            "last_name": request.form.get("last_name", "").strip(),
            "job_title": request.form.get("job_title", "").strip(),
            "email": request.form.get("email", "").strip().lower(),
            "mobile_phone": request.form.get("mobile_phone", "").strip(),
        }
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        terms = request.form.get("terms") == "on"
        privacy = request.form.get("privacy") == "on"
        checks = _password_check(password)

        if not fields["first_name"]:
            errors["first_name"] = "First name is required."
        if not fields["last_name"]:
            errors["last_name"] = "Last name is required."
        if "@" not in fields["email"]:
            errors["email"] = "Enter a valid email address."
        else:
            with get_db() as conn:
                existing = conn.execute(
                    "SELECT 1 FROM admin_users WHERE email=%s", (fields["email"],)
                ).fetchone()
            if existing:
                errors["email"] = "That email is already registered to an account."
        if not all(checks.values()):
            errors["password"] = "Password doesn't meet all requirements below."
        elif password != confirm:
            errors["confirm_password"] = "Passwords don't match."
        if not (terms and privacy):
            errors["terms"] = "You must agree to the Terms of Service and Privacy Policy."

        if errors:
            return _wrap(token, render_template(
                "wizard/step2_admin.html", data={**data, **fields}, errors=errors,
                checks=checks, rules=PASSWORD_RULES, step_num=2,
            ))

        fields["password_hash"] = generate_password_hash(password)
        save_step(token, {"admin": fields}, next_step=3)
        return _wrap(token, redirect(url_for("wizard.step_settings")))

    return _wrap(token, render_template(
        "wizard/step2_admin.html", data=data, errors=errors, checks=checks, rules=PASSWORD_RULES, step_num=2,
    ))


@wizard.route("/signup/settings", methods=["GET", "POST"])
def step_settings():
    token, draft = _ensure_draft()
    data = dict(draft["data"].get("settings", {}))
    errors = {}

    if request.method == "POST":
        shift_raw = request.form.get("default_shift_minutes", "480")
        if shift_raw == "custom":
            try:
                shift_minutes = int(float(request.form.get("custom_shift_hours", "8")) * 60)
            except ValueError:
                shift_minutes = 480
        else:
            try:
                shift_minutes = int(shift_raw)
            except ValueError:
                shift_minutes = 480

        overtime_rule = request.form.get("overtime_rule", "none")
        overtime_threshold = None
        if overtime_rule == "custom":
            try:
                overtime_threshold = float(request.form.get("overtime_custom_hours", "40"))
            except ValueError:
                overtime_threshold = 40.0

        fields = {
            "timezone": request.form.get("timezone", "America/Chicago"),
            "currency": request.form.get("currency", "USD"),
            "week_starts_on": request.form.get("week_starts_on", "monday"),
            "payroll_frequency": request.form.get("payroll_frequency", "weekly"),
            "default_shift_minutes": shift_minutes,
            "overtime_rule": overtime_rule,
            "overtime_threshold_hours": overtime_threshold,
        }
        if fields["timezone"] not in dict(choices.TIMEZONE_CHOICES):
            fields["timezone"] = "America/Chicago"

        save_step(token, {"settings": fields}, next_step=4)
        return _wrap(token, redirect(url_for("wizard.step_payroll")))

    return _wrap(token, render_template("wizard/step3_settings.html", data=data, errors=errors, choices=choices, step_num=3))


@wizard.route("/signup/payroll", methods=["GET", "POST"])
def step_payroll():
    token, draft = _ensure_draft()
    data = dict(draft["data"].get("payroll", {}))
    errors = {}

    if request.method == "POST":
        try:
            default_rate = float(request.form.get("default_hourly_rate", "16.00"))
        except ValueError:
            default_rate = 16.00
            errors["default_hourly_rate"] = "Enter a valid hourly rate."

        try:
            lunch_minutes = int(request.form.get("lunch_duration_minutes", "30"))
        except ValueError:
            lunch_minutes = 30

        fields = {
            "default_hourly_rate": default_rate,
            "allow_employee_specific_rates": request.form.get("allow_employee_specific_rates") == "yes",
            "round_clock_minutes": int(request.form.get("round_clock_minutes", "0") or 0),
            "auto_lunch_deduction": request.form.get("auto_lunch_deduction") == "yes",
            "lunch_duration_minutes": lunch_minutes,
            "allow_paid_breaks": request.form.get("allow_paid_breaks") == "yes",
        }

        if errors:
            return _wrap(token, render_template(
                "wizard/step4_payroll.html", data={**data, **fields}, errors=errors, choices=choices, step_num=4,
            ))

        save_step(token, {"payroll": fields}, next_step=5)
        return _wrap(token, redirect(url_for("wizard.step_employees")))

    return _wrap(token, render_template("wizard/step4_payroll.html", data=data, errors=errors, choices=choices, step_num=4))


def _next_auto_code(employees):
    used = {e.get("employee_code", "").upper() for e in employees}
    n = len(employees) + 1
    while f"EMP{n:03d}" in used:
        n += 1
    return f"EMP{n:03d}"


def _validate_employee_fields(first_name, last_name, pin, employee_code, employees, hourly_rate_raw):
    errors = []
    if not first_name:
        errors.append("First name is required.")
    if not last_name:
        errors.append("Last name is required.")
    if not pin:
        errors.append("PIN is required.")
    if employee_code and employee_code.upper() in {e.get("employee_code", "").upper() for e in employees}:
        errors.append(f"Employee ID '{employee_code}' is already used in this list.")
    hourly_rate = None
    if hourly_rate_raw:
        try:
            hourly_rate = float(hourly_rate_raw)
        except ValueError:
            errors.append("Hourly rate must be a number.")
    return errors, hourly_rate


@wizard.route("/signup/employees", methods=["GET", "POST"])
def step_employees():
    token, draft = _ensure_draft()
    employees = list(draft["data"].get("employees", []))
    errors = {}
    csv_summary = None

    if request.method == "POST":
        action = request.form.get("action", "add")

        if action == "add":
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            pin = request.form.get("pin", "").strip()
            employee_code = request.form.get("employee_code", "").strip()
            errs, hourly_rate = _validate_employee_fields(
                first_name, last_name, pin, employee_code, employees, request.form.get("hourly_rate", "")
            )
            if errs:
                errors["add"] = errs
            else:
                manager_index = request.form.get("manager_index", "")
                entry = {
                    "first_name": first_name, "last_name": last_name,
                    "employee_code": employee_code or _next_auto_code(employees),
                    "email": request.form.get("email", "").strip(),
                    "phone": request.form.get("phone", "").strip(),
                    "department": request.form.get("department", "").strip(),
                    "job_title": request.form.get("job_title", "").strip(),
                    "hourly_rate": hourly_rate,
                    "manager_index": int(manager_index) if manager_index.isdigit() else None,
                    "status": request.form.get("status", "active"),
                    "role": request.form.get("role", "employee"),
                    "pin_hash": generate_password_hash(pin),
                }
                employees.append(entry)
                save_step(token, {"employees": employees})

        elif action == "remove":
            idx = request.form.get("index", "")
            if idx.isdigit() and int(idx) < len(employees):
                employees.pop(int(idx))
                save_step(token, {"employees": employees})

        elif action == "import_csv":
            csv_file = request.files.get("csv_file")
            if not csv_file or not csv_file.filename:
                errors["csv"] = ["Choose a CSV file to import."]
            else:
                raw = csv_file.read()
                if len(raw) > CSV_MAX_BYTES:
                    errors["csv"] = ["CSV file is too large (max 1MB)."]
                else:
                    text = raw.decode("utf-8", errors="replace")
                    reader = csv.DictReader(io.StringIO(text))
                    imported, skipped = 0, []
                    for i, row in enumerate(reader, start=2):
                        if i - 1 > CSV_MAX_ROWS:
                            skipped.append(f"Row {i}: import capped at {CSV_MAX_ROWS} rows.")
                            break
                        norm = {}
                        for k, v in row.items():
                            key = CSV_HEADER_ALIASES.get((k or "").strip().lower())
                            if key:
                                norm[key] = (v or "").strip()
                        first_name = norm.get("first_name", "")
                        last_name = norm.get("last_name", "")
                        pin = norm.get("pin", "")
                        employee_code = norm.get("employee_code", "")
                        errs, hourly_rate = _validate_employee_fields(
                            first_name, last_name, pin, employee_code, employees, norm.get("hourly_rate", "")
                        )
                        if errs:
                            skipped.append(f"Row {i}: " + "; ".join(errs))
                            continue
                        manager_index = None
                        manager_ref = norm.get("manager", "")
                        if manager_ref:
                            for mi, existing in enumerate(employees):
                                full = f"{existing['first_name']} {existing['last_name']}".strip()
                                if manager_ref.upper() in (existing.get("employee_code", "").upper(), full.upper()):
                                    manager_index = mi
                                    break
                        employees.append({
                            "first_name": first_name, "last_name": last_name,
                            "employee_code": employee_code or _next_auto_code(employees),
                            "email": norm.get("email", ""), "phone": norm.get("phone", ""),
                            "department": norm.get("department", ""), "job_title": norm.get("job_title", ""),
                            "hourly_rate": hourly_rate, "manager_index": manager_index,
                            "status": norm.get("status", "active") or "active",
                            "role": norm.get("role", "employee") or "employee",
                            "pin_hash": generate_password_hash(pin),
                        })
                        imported += 1
                    save_step(token, {"employees": employees})
                    csv_summary = {"imported": imported, "skipped": skipped}

        elif action == "continue":
            save_step(token, {"employees": employees}, next_step=6)
            return _wrap(token, redirect(url_for("wizard.step_devices")))

    return _wrap(token, render_template(
        "wizard/step5_employees.html", employees=employees, errors=errors,
        csv_summary=csv_summary, choices=choices, step_num=5,
    ))


@wizard.route("/signup/devices", methods=["GET", "POST"])
def step_devices():
    token, draft = _ensure_draft()
    device = dict(draft["data"].get("device") or {})
    user_agent = request.headers.get("User-Agent", "Unknown device")
    remote_addr = request.remote_addr

    if request.method == "POST":
        action = request.form.get("action")
        if action == "register":
            device = {
                "register": True,
                "name": request.form.get("device_name", "").strip() or "Office Computer",
                "reported_os": user_agent,
                "reported_ip": remote_addr,
            }
        elif action == "skip":
            device = {}
        save_step(token, {"device": device}, next_step=7)
        return _wrap(token, redirect(url_for("wizard.step_review")))

    return _wrap(token, render_template(
        "wizard/step6_devices.html", device=device, user_agent=user_agent,
        remote_addr=remote_addr, step_num=6,
    ))


@wizard.route("/signup/review", methods=["GET", "POST"])
def step_review():
    token, draft = _ensure_draft()
    data = draft["data"]
    company = data.get("company", {})
    admin = data.get("admin", {})
    settings_ = data.get("settings", {})
    payroll = data.get("payroll", {})
    employees = data.get("employees", [])
    device = data.get("device") or {}
    plan = data.get("plan") if data.get("plan") in ("starter", "growth", "business") else "starter"

    if request.method == "POST":
        missing = []
        if not company.get("name"):
            missing.append("Company name is missing — go back to Step 1.")
        if not admin.get("email") or not admin.get("password_hash"):
            missing.append("Administrator account is incomplete — go back to Step 2.")
        if missing:
            for m in missing:
                flash(m)
            return _wrap(token, render_template(
                "wizard/step7_review.html", company=company, admin=admin, settings=settings_,
                payroll=payroll, employees=employees, device=device, step_num=7,
            ))

        print(f"[wizard] checkout attempt starting - token={token} plan={plan} employees={len(employees)}")
        try:
            checkout_url = billing.create_checkout_session(
                token, plan, admin["email"],
                success_url=url_for("wizard.checkout_success", _external=True),
                cancel_url=url_for("wizard.checkout_cancelled", _external=True),
            )
        except stripe.error.StripeError:
            print("[wizard] checkout session creation FAILED:")
            traceback.print_exc()
            flash("We couldn't reach our payment processor. Please try again in a moment.")
            return _wrap(token, render_template(
                "wizard/step7_review.html", company=company, admin=admin, settings=settings_,
                payroll=payroll, employees=employees, device=device, step_num=7,
            ))

        # Nothing is created yet - the organization, admin, and everything else only
        # get written to the database once Stripe confirms a payment method was
        # saved (see billing.finalize_signup_checkout, called from checkout_success
        # below and from the /stripe/webhook checkout.session.completed handler).
        return _wrap(token, redirect(checkout_url))

    return _wrap(token, render_template(
        "wizard/step7_review.html", company=company, admin=admin, settings=settings_,
        payroll=payroll, employees=employees, device=device, step_num=7,
    ))


@wizard.route("/signup/checkout/success")
def checkout_success():
    session_id = request.args.get("session_id", "")
    if not session_id:
        flash("We couldn't confirm your payment setup. Please try signing up again.")
        return redirect(url_for("wizard.step_company"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        print("[wizard] checkout_success: retrieving session FAILED:")
        traceback.print_exc()
        flash("We couldn't confirm your payment setup with Stripe. Please contact support.")
        return redirect(url_for("wizard.step_company"))

    if checkout_session.get("status") != "complete":
        flash("Payment setup isn't complete yet. Please try again or contact support.")
        return redirect(url_for("wizard.checkout_cancelled"))

    result = billing.finalize_signup_checkout(checkout_session)

    if result is None:
        # Someone else (almost always the /stripe/webhook handler, which can beat
        # this page back from Stripe) already claimed the draft and created the
        # org. Look it up by the Stripe customer id instead of creating it again.
        with get_db() as conn:
            org = conn.execute(
                "SELECT * FROM organizations WHERE stripe_customer_id=%s",
                (checkout_session.get("customer"),),
            ).fetchone()
            admin_row = conn.execute(
                "SELECT * FROM admin_users WHERE org_id=%s ORDER BY id LIMIT 1", (org["id"],)
            ).fetchone() if org else None
        if org is None or admin_row is None:
            flash("We couldn't find your signup details. Please contact support at info@lbsconnect.net.")
            return redirect(url_for("wizard.step_company"))
        session["admin_id"] = admin_row["id"]
        session["org_id"] = org["id"]
        session["welcome_company_code"] = org["company_code"].upper()
        resp = make_response(redirect(url_for("admin_dashboard")))
        resp.delete_cookie(COOKIE_NAME)
        return resp

    session["admin_id"] = result["admin_id"]
    session["org_id"] = result["org_id"]
    session["welcome_company_code"] = result["company_code"].upper()
    session["welcome_admin_creds"] = result["secondary_admin_creds"]
    resp = make_response(redirect(url_for("admin_dashboard")))
    resp.delete_cookie(COOKIE_NAME)
    if result.get("raw_device_token"):
        resp = devices_mod.issue_device_cookie(resp, result["org_id"], result["raw_device_token"])
    return resp


@wizard.route("/signup/checkout/cancelled")
def checkout_cancelled():
    return render_template("wizard/checkout_cancelled.html")
