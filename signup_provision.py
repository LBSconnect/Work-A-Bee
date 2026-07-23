import base64
import secrets

from werkzeug.security import generate_password_hash

import audit
import devices as devices_mod
from orgs import next_company_code


def create_org_from_draft_data(conn, data):
    """Creates the organization, admin, departments, employees, and (optionally) a
    trusted device from a completed signup draft's data.

    Runs inside the caller's open transaction - does not commit and does not touch
    the signup_drafts row. Returns a dict with the ids/details callers need to log
    the new admin in and show them their credentials.
    """
    company = data.get("company", {})
    admin = data.get("admin", {})
    settings_ = data.get("settings", {})
    payroll = data.get("payroll", {})
    employees = data.get("employees", [])
    device = data.get("device") or {}
    plan = data.get("plan") if data.get("plan") in ("starter", "growth", "business") else "starter"

    next_id, code = next_company_code(conn)
    print(f"[signup] checkpoint: got company code {code}")
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
         payroll.get("allow_paid_breaks", False), admin.get("email"), plan, "active"),
    )
    org_id = next_id
    print(f"[signup] checkpoint: organizations insert OK, org_id={org_id}")
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
    print(f"[signup] checkpoint: admin_users insert OK, admin_id={admin_id}")
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
    print(f"[signup] checkpoint: departments OK, count={len(dept_ids)}")

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
    print(f"[signup] checkpoint: employees insert OK, count={len(emp_ids)}")

    for idx, e in enumerate(employees):
        mgr_idx = e.get("manager_index")
        if mgr_idx is not None and 0 <= mgr_idx < len(emp_ids) and mgr_idx != idx:
            conn.execute(
                "UPDATE employees SET manager_id=%s WHERE id=%s",
                (emp_ids[mgr_idx], emp_ids[idx]),
            )
    print("[signup] checkpoint: manager_id backfill OK")

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
    print(f"[signup] checkpoint: secondary admins OK, count={len(secondary_admin_creds)}")

    raw_device_token = None
    if device.get("register"):
        _, raw_device_token = devices_mod.register_device(
            conn, org_id, device.get("name") or "Office Computer", admin_id
        )
        audit.log(conn, org_id, "admin", admin_id, "device.registered", device.get("name"))
    print(f"[signup] checkpoint: device registration OK, registered={bool(raw_device_token)}")

    return {
        "org_id": org_id,
        "admin_id": admin_id,
        "company_code": code,
        "secondary_admin_creds": secondary_admin_creds,
        "raw_device_token": raw_device_token,
        "plan": plan,
    }
