import os
from functools import wraps
from datetime import datetime, date

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import config
from models import init_db, get_db
from payroll import get_period_bounds, calculate_payroll
from email_report import send_report_email

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

app.config.update(
    SESSION_COOKIE_SECURE=config.ON_RENDER,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

limiter = Limiter(get_remote_address, app=app, default_limits=[])

init_db()


@app.route("/", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def clock_home():
    if request.method == "POST":
        code = request.form.get("employee_code", "").strip()
        pin = request.form.get("pin", "").strip()
        with get_db() as conn:
            emp = conn.execute(
                "SELECT * FROM employees WHERE employee_code=%s AND active=1", (code,)
            ).fetchone()
        if emp and check_password_hash(emp["pin_hash"], pin):
            session["employee_id"] = emp["id"]
            return redirect(url_for("clock_action"))
        flash("Employee ID or PIN not recognized.")
    return render_template("login.html")


@app.route("/clock", methods=["GET", "POST"])
def clock_action():
    emp_id = session.get("employee_id")
    if not emp_id:
        return redirect(url_for("clock_home"))

    with get_db() as conn:
        emp = conn.execute("SELECT * FROM employees WHERE id=%s", (emp_id,)).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("clock_home"))

        open_entry = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s AND clock_out IS NULL",
            (emp_id,),
        ).fetchone()

        if request.method == "POST":
            now = datetime.now()
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
            return redirect(url_for("clock_home"))

    return render_template("clock.html", employee=emp, is_clocked_in=bool(open_entry))


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/admin/setup", methods=["GET", "POST"])
def admin_setup():
    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()["c"]
    if existing > 0:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        if not username or not password:
            flash("Username and password are required.")
        elif password != confirm:
            flash("Passwords don't match.")
        elif len(password) < 8:
            flash("Password should be at least 8 characters.")
        else:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO admin_users (username, password_hash) VALUES (%s, %s)",
                    (username, generate_password_hash(password)),
                )
                conn.commit()
            flash("Admin account created. Please log in.")
            return redirect(url_for("admin_login"))
    return render_template("admin_setup.html")


@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def admin_login():
    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()["c"]
    if existing == 0:
        return redirect(url_for("admin_setup"))

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        with get_db() as conn:
            admin = conn.execute(
                "SELECT * FROM admin_users WHERE username=%s", (username,)
            ).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            return redirect(url_for("admin_dashboard"))
        flash("Invalid username or password.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    today = date.today()
    period_start, period_end = get_period_bounds(today)
    with get_db() as conn:
        rows = calculate_payroll(conn, period_start, period_end)
    next_report_note = (
        f"Next automatic email: {period_end.strftime('%A, %B %d, %Y')} at "
        f"{config.REPORT_HOUR % 12 or 12}:{config.REPORT_MINUTE:02d} "
        f"{'PM' if config.REPORT_HOUR >= 12 else 'AM'} Central"
    )
    return render_template(
        "admin_dashboard.html",
        rows=rows,
        period_start=period_start,
        period_end=period_end,
        next_report_note=next_report_note,
    )


@app.route("/admin/employees")
@admin_required
def admin_employees():
    with get_db() as conn:
        employees = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
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
            return render_template("admin_employee_form.html", employee=None, default_rate=config.DEFAULT_HOURLY_RATE)

        if not code or not name or not pin:
            flash("Employee ID, name, and PIN are all required.")
            return render_template("admin_employee_form.html", employee=None, default_rate=config.DEFAULT_HOURLY_RATE)

        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO employees (employee_code, name, pin_hash, hourly_rate, worker_type) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (code, name, generate_password_hash(pin), rate, worker_type),
                )
                conn.commit()
        except Exception:
            flash(f"Employee ID '{code}' is already in use.")
            return render_template("admin_employee_form.html", employee=None, default_rate=config.DEFAULT_HOURLY_RATE)

        flash(f"Added {name}.")
        return redirect(url_for("admin_employees"))
    return render_template("admin_employee_form.html", employee=None)


@app.route("/admin/employees/<int:emp_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_employee_edit(emp_id):
    with get_db() as conn:
        emp = conn.execute("SELECT * FROM employees WHERE id=%s", (emp_id,)).fetchone()
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
                    "UPDATE employees SET name=%s, hourly_rate=%s, worker_type=%s, active=%s, pin_hash=%s WHERE id=%s",
                    (name, rate, worker_type, active, generate_password_hash(pin), emp_id),
                )
            else:
                conn.execute(
                    "UPDATE employees SET name=%s, hourly_rate=%s, worker_type=%s, active=%s WHERE id=%s",
                    (name, rate, worker_type, active, emp_id),
                )
            conn.commit()
            flash("Updated.")
            return redirect(url_for("admin_employees"))

    return render_template("admin_employee_form.html", employee=emp)


def _send_current_period_report():
    today = date.today()
    period_start, period_end = get_period_bounds(today)
    with get_db() as conn:
        rows = calculate_payroll(conn, period_start, period_end)
    send_report_email(period_start, period_end, rows)
    return period_start, period_end


@app.route("/admin/report/send-now")
@admin_required
def admin_send_report_now():
    try:
        _send_current_period_report()
        flash("Report emailed successfully.")
    except Exception as e:
        flash(f"Failed to send report: {e}")
    return redirect(url_for("admin_dashboard"))


@app.route("/cron/send-report")
def cron_send_report():
    token = request.args.get("token", "")
    if not config.REPORT_TOKEN or token != config.REPORT_TOKEN:
        abort(403)

    from scheduler import is_report_day
    today = date.today()
    if not is_report_day(today):
        return {"status": "skipped", "reason": "not a report day", "date": str(today)}, 200

    with get_db() as conn:
        already_sent = conn.execute(
            "SELECT 1 FROM report_log WHERE report_date=%s", (today,)
        ).fetchone()
        if already_sent:
            return {"status": "skipped", "reason": "already sent today", "date": str(today)}, 200

    try:
        period_start, period_end = _send_current_period_report()
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

    with get_db() as conn:
        conn.execute(
            "INSERT INTO report_log (report_date) VALUES (%s) ON CONFLICT DO NOTHING",
            (today,),
        )
        conn.commit()

    return {
        "status": "sent",
        "period_start": str(period_start),
        "period_end": str(period_end),
    }, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
