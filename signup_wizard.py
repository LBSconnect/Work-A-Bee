import base64
import csv
import io
import secrets
import traceback

import psycopg2
import psycopg2.errors
from flask import Blueprint, request, redirect, url_for, render_template, flash, session, make_response, jsonify
from werkzeug.security import generate_password_hash

import stripe

import audit
import billing
import choices
import devices as devices_mod
import plans
from drafts import get_or_create_draft, save_step, attach_cookie, delete_draft, COOKIE_NAME
from models import get_db
from orgs import next_company_code

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

        print(f"[wizard] launch attempt starting - token={token} employees={len(employees)} device_register={bool(device.get('register'))}")
        try:
            with get_db() as conn:
                next_id, code = next_company_code(conn)
                print(f"[wizard] checkpoint: got company code {code}")
                logo_bytes = base64.b64decode(company["logo_b64"]) if company.get("logo_b64") else None
                conn.execute(
                    "INSERT INTO organizations (id, company_code, name, dba_name, business_type, industry, "
                    "address_line1, city, state, zip, country, phone, website, logo_data, logo_mime, "
                    "timezone, currency, week_starts_on, payroll_frequency, default_shift_minutes, "
                    "overtime_rule, overtime_threshold_hours, default_hourly_rate, "
                    "allow_employee_specific_rates, round_clock_minutes, auto_lunch_deduction, "
                    "lunch_duration_minutes, allow_paid_breaks, report_recipients, plan, status, "
                    "onboarding_completed_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())",
                    (next_id, code, company["name"], company.get("dba_name") or None,
                     company.get("business_type") or None, company.get("industry") or None,
                     company.get("address_line1"), company.get("city") or None, company.get("state") or None,
                     company.get("zip") or None, company.get("country") or "United States",
                     company.get("phone"), company.get("website") or None, logo_bytes,
                     company.get("logo_mime") if logo_bytes else None,
                     settings_.get("timezone", "America/Chicago"), settings_.get("currency", "USD"),
                     settings_.get("week_starts_on", "monday"), settings_.get("payroll_frequency", "weekly"),
                     settings_.get("default_shift_minutes", 480), settings_.get("overtime_rule", "none"),
                     settings_.get("overtime_threshold_hours"), payroll.get("default_hourly_rate", 16.00),
                     payroll.get("allow_employee_specific_rates", True), payroll.get("round_clock_minutes", 0),
                     payroll.get("auto_lunch_deduction", False), payroll.get("lunch_duration_minutes", 30),
                     payroll.get("allow_paid_breaks", False), admin.get("email"), plan, "pending_payment"),
                )
                org_id = next_id
                print(f"[wizard] checkpoint: organizations insert OK, org_id={org_id}")
                audit.log(conn, org_id, "system", None, "org.created", company["name"])

                admin_row = conn.execute(
                    "INSERT INTO admin_users (org_id, username, password_hash, first_name, last_name, "
                    "job_title, email, mobile_phone, terms_accepted_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW()) RETURNING id",
                    (org_id, admin["email"], admin["password_hash"], admin.get("first_name") or None,
                     admin.get("last_name") or None, admin.get("job_title") or None, admin["email"],
                     admin.get("mobile_phone") or None),
                ).fetchone()
                admin_id = admin_row["id"]
                print(f"[wizard] checkpoint: admin_users insert OK, admin_id={admin_id}")
                audit.log(conn, org_id, "admin", admin_id, "admin.created", admin["email"])

                dept_ids = {}
                dept_names = sorted({e["department"].strip() for e in employees if e.get("department", "").strip()})
                for dname in dept_names:
                    d = conn.execute(
                        "INSERT INTO departments (org_id, name) VALUES (%s,%s) RETURNING id",
                        (org_id, dname),
                    ).fetchone()
                    dept_ids[dname] = d["id"]
                    audit.log(conn, org_id, "admin", admin_id, "department.created", dname)
                print(f"[wizard] checkpoint: departments OK, count={len(dept_ids)}")

                emp_ids = []
                for e in employees:
                    name = f"{e.get('first_name', '').strip()} {e.get('last_name', '').strip()}".strip()
                    rate = e.get("hourly_rate") or payroll.get("default_hourly_rate", 16.00)
                    dept_id = dept_ids.get(e.get("department", "").strip()) if e.get("department") else None
                    row = conn.execute(
                        "INSERT INTO employees (org_id, employee_code, name, first_name, last_name, "
                        "pin_hash, hourly_rate, worker_type, active, email, phone, department_id, "
                        "job_title, role) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                        (org_id, e["employee_code"], name, e.get("first_name") or None, e.get("last_name") or None,
                         e["pin_hash"], rate, "employee",
                         1 if e.get("status", "active") == "active" else 0,
                         e.get("email") or None, e.get("phone") or None, dept_id,
                         e.get("job_title") or None, e.get("role", "employee")),
                    ).fetchone()
                    emp_ids.append(row["id"])
                    audit.log(conn, org_id, "admin", admin_id, "employee.created", name)
                print(f"[wizard] checkpoint: employees insert OK, count={len(emp_ids)}")

                for idx, e in enumerate(employees):
                    mgr_idx = e.get("manager_index")
                    if mgr_idx is not None and 0 <= mgr_idx < len(emp_ids) and mgr_idx != idx:
                        conn.execute(
                            "UPDATE employees SET manager_id=%s WHERE id=%s",
                            (emp_ids[mgr_idx], emp_ids[idx]),
                        )
                print("[wizard] checkpoint: manager_id backfill OK")

                secondary_admin_creds = []
                for e in employees:
                    if e.get("role") == "administrator" and e.get("email"):
                        temp_password = secrets.token_urlsafe(9)
                        conn.execute(
                            "INSERT INTO admin_users (org_id, username, password_hash, first_name, "
                            "last_name, job_title, email) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                            (org_id, e["email"], generate_password_hash(temp_password),
                             e.get("first_name") or None, e.get("last_name") or None,
                             e.get("job_title") or None, e["email"]),
                        )
                        secondary_admin_creds.append({"email": e["email"], "temp_password": temp_password})
                        audit.log(conn, org_id, "admin", admin_id, "admin.created", f"{e['email']} (secondary)")
                print(f"[wizard] checkpoint: secondary admins OK, count={len(secondary_admin_creds)}")

                raw_device_token = None
                if device.get("register"):
                    _, raw_device_token = devices_mod.register_device(
                        conn, org_id, device.get("name") or "Office Computer", admin_id
                    )
                    audit.log(conn, org_id, "admin", admin_id, "device.registered", device.get("name"))
                print(f"[wizard] checkpoint: device registration OK, registered={bool(raw_device_token)}")

                delete_draft(conn, token)
                print("[wizard] checkpoint: draft deleted, about to commit")
                conn.commit()
                print(f"[wizard] SUCCESS: org_id={org_id} code={code} committed")
        except psycopg2.errors.UniqueViolation as e:
            print("[wizard] FAILED with UniqueViolation:")
            traceback.print_exc()
            constraint = getattr(e.diag, "constraint_name", "") or ""
            if "email" in constraint:
                flash("That administrator email is already registered — please go back to Step 2 and use a different one.")
            else:
                flash("Something in this signup conflicts with an existing account. Please review and try again.")
            return _wrap(token, render_template(
                "wizard/step7_review.html", company=company, admin=admin, settings=settings_,
                payroll=payroll, employees=employees, device=device, step_num=7,
            ))
        except Exception:
            print("[wizard] FAILED with generic Exception:")
            traceback.print_exc()
            flash("Something went wrong creating your company. Your progress is saved — please try again.")
            return _wrap(token, render_template(
                "wizard/step7_review.html", company=company, admin=admin, settings=settings_,
                payroll=payroll, employees=employees, device=device, step_num=7,
            ))

        session["admin_id"] = admin_id
        session["org_id"] = org_id
        session["welcome_company_code"] = code.upper()
        session["welcome_admin_creds"] = secondary_admin_creds
        if raw_device_token:
            session["pending_device_token"] = raw_device_token

        try:
            checkout_url = billing.create_checkout_session(
                org_id, plan, admin["email"],
                success_url=url_for("wizard.checkout_success", _external=True),
                cancel_url=url_for("wizard.checkout_cancelled", _external=True),
            )
        except stripe.error.StripeError:
            traceback.print_exc()
            resp = make_response(redirect(url_for("wizard.checkout_cancelled")))
            resp.delete_cookie(COOKIE_NAME)
            flash("Your company account was created, but we couldn't reach our payment processor. Please try completing payment setup again.")
            return resp

        resp = make_response(redirect(checkout_url))
        resp.delete_cookie(COOKIE_NAME)
        return resp

    return _wrap(token, render_template(
        "wizard/step7_review.html", company=company, admin=admin, settings=settings_,
        payroll=payroll, employees=employees, device=device, step_num=7,
    ))


@wizard.route("/signup/checkout/success")
def checkout_success():
    session_id = request.args.get("session_id", "")
    org_id = session.get("org_id")
    if not session_id or not org_id:
        flash("We couldn't confirm your payment setup. Please log in and check your plan status.")
        return redirect(url_for("admin_login"))

    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        flash("We couldn't confirm your payment setup with Stripe. Please contact support.")
        return redirect(url_for("admin_login"))

    if checkout_session.get("client_reference_id") != str(org_id) or checkout_session.get("payment_status") not in ("paid", "no_payment_required") and checkout_session.get("status") != "complete":
        flash("Payment setup isn't complete yet. Please try again or contact support.")
        return redirect(url_for("wizard.checkout_cancelled"))

    billing.handle_checkout_completed(checkout_session)

    raw_device_token = session.pop("pending_device_token", None)
    resp = make_response(redirect(url_for("admin_dashboard")))
    if raw_device_token:
        resp = devices_mod.issue_device_cookie(resp, org_id, raw_device_token)
    return resp


@wizard.route("/signup/checkout/cancelled")
def checkout_cancelled():
    if not session.get("org_id") or not session.get("admin_id"):
        flash("Your signup session has expired. Please contact support to finish setting up your account.")
        return redirect(url_for("admin_login"))
    return render_template("wizard/checkout_cancelled.html")


@wizard.route("/signup/checkout/retry")
def checkout_retry():
    org_id = session.get("org_id")
    admin_id = session.get("admin_id")
    if not org_id or not admin_id:
        flash("Your signup session has expired. Please contact support to finish setting up your account.")
        return redirect(url_for("admin_login"))

    with get_db() as conn:
        org = conn.execute("SELECT * FROM organizations WHERE id=%s", (org_id,)).fetchone()
        admin_row = conn.execute("SELECT * FROM admin_users WHERE id=%s", (admin_id,)).fetchone()

    if org is None or admin_row is None:
        flash("We couldn't find your account. Please contact support.")
        return redirect(url_for("admin_login"))

    try:
        checkout_url = billing.create_checkout_session(
            org_id, plans.get_plan_key(org), admin_row["email"],
            success_url=url_for("wizard.checkout_success", _external=True),
            cancel_url=url_for("wizard.checkout_cancelled", _external=True),
        )
    except stripe.error.StripeError:
        traceback.print_exc()
        flash("We couldn't reach our payment processor. Please try again shortly.")
        return redirect(url_for("wizard.checkout_cancelled"))

    return redirect(checkout_url)
