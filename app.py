import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
from models import init_db, get_db
from orgs import get_active_org, normalize_company_code
from payroll import get_period_bounds, calculate_payroll, get_period_entries, get_prior_periods
from email_report import send_report_email
from tz import now_in, today_in

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

app.config.update(
    SESSION_COOKIE_SECURE=config.ON_RENDER,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

limiter = Limiter(get_remote_address, app=app, default_limits=[])

init_db()


@app.route("/")
def clock_home():
    return render_template("login.html")


@app.route("/staff/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def staff_login():
    if request.args.get("switch"):
        session.pop("org_id", None)

    org = None
    org_id = session.get("org_id")
    if org_id:
        with get_db() as conn:
            org = conn.execute(
                "SELECT * FROM organizations WHERE id=%s AND status='active'", (org_id,)
            ).fetchone()

    if request.method == "POST":
        if org is None:
            with get_db() as conn:
                org = get_active_org(conn, request.form.get("company_code", ""))
            if org is None:
                flash("Company code, Employee ID, or PIN not recognized.")
                return render_template("staff_login.html", org=None)

        code = request.form.get("employee_code", "").strip()
        pin = request.form.get("pin", "").strip()
        with get_db() as conn:
            emp = conn.execute(
                "SELECT * FROM employees WHERE org_id=%s AND employee_code=%s AND active=1",
                (org["id"], code),
            ).fetchone()
        if emp and check_password_hash(emp["pin_hash"], pin):
            session["org_id"] = org["id"]
            session["employee_id"] = emp["id"]
            return redirect(url_for("clock_action"))
        flash("Company code, Employee ID, or PIN not recognized.")
        return render_template("staff_login.html", org=org)

    return render_template("staff_login.html", org=org)


@app.route("/clock", methods=["GET", "POST"])
def clock_action():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        org = conn.execute(
            "SELECT * FROM organizations WHERE id=%s AND status='active'", (org_id,)
        ).fetchone()
        if emp is None or org is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        open_entry = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s AND clock_out IS NULL",
            (emp_id,),
        ).fetchone()

        if request.method == "POST":
            now = now_in(org["timezone"])
            if open_entry:
                conn.execute(
                    "UPDATE time_entries SET clock_out=%s WHERE id=%s",
                    (now, open_entry["id"]),
                )
                flash(f"Clocked OUT at {now.strftime('%I:%M %p')}. Have a good one, {emp['name']}!")
            else:
                conn.execute(
                    "INSERT INTO time_entries (employee_id, clock_in) VALUES (%s, %s)",
                    (emp_id, now),
                )
                flash(f"Clocked IN at {now.strftime('%I:%M %p')}. Welcome, {emp['name']}!")
            conn.commit()
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        recent_entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s ORDER BY clock_in DESC LIMIT 10",
            (emp_id,),
        ).fetchall()

        period_start, _ = get_period_bounds(today_in(org["timezone"]))
        weekly_history = []
        for start, end in get_prior_periods(period_start, count=4):
            rows = calculate_payroll(conn, org["id"], org["timezone"], start, end)
            mine = next((r for r in rows if r["employee_code"] == emp["employee_code"]), None)
            weekly_history.append({
                "period_start": start,
                "period_end": end,
                "hours": mine["total_hours"] if mine else 0.0,
                "pay": mine["pay"] if mine else 0.0,
            })

    history = []
    for e in recent_entries:
        hours = None
        if e["clock_out"]:
            hours = round((e["clock_out"] - e["clock_in"]).total_seconds() / 3600, 2)
        history.append({"clock_in": e["clock_in"], "clock_out": e["clock_out"], "hours": hours})

    return render_template(
        "clock.html",
        employee=emp,
        is_clocked_in=bool(open_entry),
        history=history,
        weekly_history=weekly_history,
    )


@app.route("/clock/submit-hours", methods=["POST"])
@limiter.limit("5 per hour")
def submit_hours():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        org = conn.execute(
            "SELECT * FROM organizations WHERE id=%s AND status='active'", (org_id,)
        ).fetchone()
    if emp is None or org is None:
        session.pop("employee_id", None)
        return redirect(url_for("staff_login"))

    try:
        _send_current_period_report(org)
        flash(f"Thanks, {emp['name']} - this week's hours report was emailed to the office.")
    except Exception as e:
        flash(f"Couldn't submit hours: {e}")

    session.pop("employee_id", None)
    return redirect(url_for("staff_login"))


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        admin_id = session.get("admin_id")
        org_id = session.get("org_id")
        if not admin_id or not org_id:
            return redirect(url_for("admin_login"))
        with get_db() as conn:
            admin = conn.execute(
                "SELECT * FROM admin_users WHERE id=%s AND org_id=%s", (admin_id, org_id)
            ).fetchone()
            org = conn.execute(
                "SELECT * FROM organizations WHERE id=%s AND status='active'", (org_id,)
            ).fetchone()
        if admin is None or org is None:
            session.pop("admin_id", None)
            session.pop("org_id", None)
            return redirect(url_for("admin_login"))
        g.admin = admin
        g.org = org
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    company_code = request.values.get("company_code", "")

    with get_db() as conn:
        org = get_active_org(conn, company_code)
    if org is not None:
        with get_db() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) AS c FROM admin_users WHERE org_id=%s", (org["id"],)
            ).fetchone()["c"]
        if existing > 0:
            return redirect(url_for("admin_login"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]

        if org is None:
            flash("Company code not recognized. Contact support to set up your organization.")
            return render_template("admin_setup.html", company_code=company_code)

        if not username or not password:
            flash("Username and password are required.")
        elif password != confirm:
            flash("Passwords don't match.")
        elif len(password) < 8:
            flash("Password should be at least 8 characters.")
        else:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO admin_users (org_id, username, password_hash) VALUES (%s, %s, %s)",
                    (org["id"], username, generate_password_hash(password)),
                )
                conn.commit()
            flash("Admin account created. Please log in.")
            return redirect(url_for("admin_login"))
        return render_template("admin_setup.html", company_code=company_code)

    return render_template("admin_setup.html", company_code=company_code)


@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def admin_login():
    if request.method == "POST":
        company_code = request.form.get("company_code", "")
        username = request.form["username"].strip()
        password = request.form["password"]

        with get_db() as conn:
            org = get_active_org(conn, company_code)
        if org is None:
            flash("Company code, username, or password not recognized.")
            return render_template("admin_login.html")

        with get_db() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) AS c FROM admin_users WHERE org_id=%s", (org["id"],)
            ).fetchone()["c"]
        if existing == 0:
            return redirect(url_for("admin_setup", company_code=normalize_company_code(company_code)))

        with get_db() as conn:
            admin = conn.execute(
                "SELECT * FROM admin_users WHERE org_id=%s AND username=%s", (org["id"], username)
            ).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["org_id"] = org["id"]
            return redirect(url_for("admin_dashboard"))
        flash("Company code, username, or password not recognized.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    today = today_in(g.org["timezone"])
    period_start, period_end = get_period_bounds(today)
    with get_db() as conn:
        detail = get_period_entries(conn, g.org["id"], g.org["timezone"], period_start, period_end)
        history = [
            {
                "period_start": start,
                "period_end": end,
                "rows": calculate_payroll(conn, g.org["id"], g.org["timezone"], start, end),
            }
            for start, end in get_prior_periods(period_start, count=4)
        ]
    rows = [
        {
            "employee_code": d["employee_code"],
            "name": d["name"],
            "worker_type": d["worker_type"],
            "hourly_rate": d["hourly_rate"],
            "total_hours": d["total_hours"],
            "pay": d["total_due"],
            "incomplete": d["incomplete"],
        }
        for d in detail
    ]
    next_report_note = (
        f"Next automatic email: {period_end.strftime('%A, %B %d, %Y')} at "
        f"{g.org['report_hour'] % 12 or 12}:{g.org['report_minute']:02d} "
        f"{'PM' if g.org['report_hour'] >= 12 else 'AM'} ({g.org['timezone']})"
    )
    return render_template(
        "admin_dashboard.html",
        rows=rows,
        detail=detail,
        history=history,
        period_start=period_start,
        period_end=period_end,
        next_report_note=next_report_note,
    )


@app.route("/admin/employees")
@admin_required
def admin_employees():
    with get_db() as conn:
        employees = conn.execute(
            "SELECT * FROM employees WHERE org_id=%s ORDER BY name", (g.org["id"],)
        ).fetchall()
    return render_template("admin_employees.html", employees=employees)


@app.route("/admin/employees/new", methods=["GET", "POST"])
@admin_required
def admin_employee_new():
    if request.method == "POST":
        code = request.form["employee_code"].strip()
        name = request.form["name"].strip()
        worker_type = request.form["worker_type"]
        pin = request.form["pin"].strip()
        try:
            rate = float(request.form["hourly_rate"])
        except ValueError:
            flash("Hourly rate must be a number.")
            return render_template(
                "admin_employee_form.html", employee=None, default_rate=g.org["default_hourly_rate"]
            )

        if not code or not name or not pin:
            flash("Employee ID, name, and PIN are all required.")
            return render_template(
                "admin_employee_form.html", employee=None, default_rate=g.org["default_hourly_rate"]
            )

        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (g.org["id"], code, name, generate_password_hash(pin), rate, worker_type),
                )
                conn.commit()
        except Exception:
            flash(f"Employee ID '{code}' is already in use.")
            return render_template(
                "admin_employee_form.html", employee=None, default_rate=g.org["default_hourly_rate"]
            )

        flash(f"Added {name}.")
        return redirect(url_for("admin_employees"))
    return render_template(
        "admin_employee_form.html", employee=None, default_rate=g.org["default_hourly_rate"]
    )


@app.route("/admin/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_employee_edit(emp_id):
    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, g.org["id"])
        ).fetchone()
        if emp is None:
            flash("Employee not found.")
            return redirect(url_for("admin_employees"))

        if request.method == "POST":
            name = request.form["name"].strip()
            worker_type = request.form["worker_type"]
            active = 1 if request.form.get("active") == "on" else 0
            pin = request.form.get("pin", "").strip()
            try:
                rate = float(request.form["hourly_rate"])
            except ValueError:
                flash("Hourly rate must be a number.")
                return render_template("admin_employee_form.html", employee=emp)

            if pin:
                conn.execute(
                    "UPDATE employees SET name=%s, hourly_rate=%s, worker_type=%s, active=%s, pin_hash=%s "
                    "WHERE id=%s AND org_id=%s",
                    (name, rate, worker_type, active, generate_password_hash(pin), emp_id, g.org["id"]),
                )
            else:
                conn.execute(
                    "UPDATE employees SET name=%s, hourly_rate=%s, worker_type=%s, active=%s "
                    "WHERE id=%s AND org_id=%s",
                    (name, rate, worker_type, active, emp_id, g.org["id"]),
                )
            conn.commit()
            flash("Updated.")
            return redirect(url_for("admin_employees"))

    return render_template("admin_employee_form.html", employee=emp)


def _send_current_period_report(org):
    recipients = [r.strip() for r in (org["report_recipients"] or "").split(",") if r.strip()]
    if not recipients:
        raise RuntimeError("No report recipients configured for this organization.")
    today = today_in(org["timezone"])
    period_start, period_end = get_period_bounds(today)
    with get_db() as conn:
        rows = calculate_payroll(conn, org["id"], org["timezone"], period_start, period_end)
    send_report_email(org["name"], recipients, period_start, period_end, rows)
    return period_start, period_end


@app.route("/admin/report/send-now")
@admin_required
def admin_send_report_now():
    try:
        _send_current_period_report(g.org)
        flash("Report emailed successfully.")
    except Exception as e:
        flash(f"Failed to send report: {e}")
    return redirect(url_for("admin_dashboard"))


def _maybe_send_report_for_org(org):
    now = now_in(org["timezone"])
    if now.weekday() != org["report_weekday"] or now.hour != org["report_hour"]:
        return {"org_id": org["id"], "status": "skipped", "reason": "not report time"}

    today = now.date()
    with get_db() as conn:
        already_sent = conn.execute(
            "SELECT 1 FROM report_log WHERE org_id=%s AND report_date=%s",
            (org["id"], today),
        ).fetchone()
    if already_sent:
        return {"org_id": org["id"], "status": "skipped", "reason": "already sent today"}

    try:
        period_start, period_end = _send_current_period_report(org)
    except Exception as e:
        return {"org_id": org["id"], "status": "error", "message": str(e)}

    with get_db() as conn:
        conn.execute(
            "INSERT INTO report_log (org_id, report_date) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (org["id"], today),
        )
        conn.commit()

    return {
        "org_id": org["id"],
        "status": "sent",
        "period_start": str(period_start),
        "period_end": str(period_end),
    }


@app.route("/cron/send-report")
def cron_send_report():
    token = request.args.get("token", "")
    if not config.REPORT_TOKEN or token != config.REPORT_TOKEN:
        abort(403)

    with get_db() as conn:
        orgs = conn.execute("SELECT * FROM organizations WHERE status='active'").fetchall()

    return {"status": "ok", "orgs": [_maybe_send_report_for_org(org) for org in orgs]}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
