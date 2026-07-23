import os
import traceback
import zlib
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, g, Response, make_response, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import stripe

import audit
import billing
import choices
import config
import devices as devices_mod
import notifications
import performance
import plans
import recognition
import schedule
from models import init_db, get_db
from orgs import get_active_org, normalize_company_code
from payroll import get_period_bounds, calculate_payroll, get_period_entries, get_prior_periods
from email_report import send_report_email
from signup_wizard import wizard as wizard_blueprint
from tz import now_in, today_in

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

if config.ON_RENDER:
    # Render terminates TLS at its edge and forwards plain HTTP to gunicorn, so
    # without this, url_for(..., _external=True) builds http:// URLs - which
    # Stripe's live-mode Checkout API rejects for success_url/cancel_url.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_for=1, x_host=1)

app.config.update(
    SESSION_COOKIE_SECURE=config.ON_RENDER,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

limiter = Limiter(get_remote_address, app=app, default_limits=[])

init_db()

app.register_blueprint(wizard_blueprint)

AVATAR_COLORS = ["#4f46e5", "#059669", "#dc2626", "#d97706", "#7c3aed", "#0ea5e9", "#db2777", "#65a30d"]


def avatar_initials(name):
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def avatar_color(key):
    return AVATAR_COLORS[zlib.crc32((key or "").encode()) % len(AVATAR_COLORS)]


app.jinja_env.filters["initials"] = avatar_initials
app.jinja_env.filters["avatar_color"] = avatar_color


@app.context_processor
def inject_unread_message_counts():
    ctx = {
        "unread_messages_count": 0, "unread_admin_messages_count": 0,
        "unread_notifications_count": 0, "unread_admin_notifications_count": 0,
    }
    org_id = session.get("org_id")
    if not org_id:
        return ctx
    emp_id = session.get("employee_id")
    admin_id = session.get("admin_id")
    if not emp_id and not admin_id:
        return ctx
    try:
        with get_db() as conn:
            if emp_id:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM messages m JOIN employees e ON m.employee_id = e.id "
                    "WHERE m.employee_id=%s AND m.sender_type='admin' "
                    "AND (e.messages_read_by_employee_at IS NULL OR m.created_at > e.messages_read_by_employee_at)",
                    (emp_id,),
                ).fetchone()
                ctx["unread_messages_count"] = row["c"] if row else 0
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM notifications WHERE employee_id=%s AND read_at IS NULL",
                    (emp_id,),
                ).fetchone()
                ctx["unread_notifications_count"] = row["c"] if row else 0
            if admin_id:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM messages m JOIN employees e ON m.employee_id = e.id "
                    "WHERE e.org_id=%s AND m.sender_type='employee' "
                    "AND (e.messages_read_by_admin_at IS NULL OR m.created_at > e.messages_read_by_admin_at)",
                    (org_id,),
                ).fetchone()
                ctx["unread_admin_messages_count"] = row["c"] if row else 0
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM notifications WHERE admin_id=%s AND read_at IS NULL",
                    (admin_id,),
                ).fetchone()
                ctx["unread_admin_notifications_count"] = row["c"] if row else 0
    except Exception:
        pass
    return ctx


def _active_companies():
    with get_db() as conn:
        return conn.execute(
            "SELECT company_code, name FROM organizations WHERE status='active' ORDER BY name"
        ).fetchall()


@app.route("/")
def clock_home():
    return render_template("index.html")


@app.route("/favicon.ico")
def favicon_ico():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route("/robots.txt")
def robots_txt():
    return send_from_directory(app.static_folder, "robots.txt", mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    return send_from_directory(app.static_folder, "sitemap.xml", mimetype="application/xml")


@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html", updated=datetime.now().date())


@app.route("/terms")
def terms_of_service():
    return render_template("terms.html", updated=datetime.now().date())


@app.route("/dpa")
def dpa_policy():
    return render_template("dpa.html", updated=datetime.now().date())


@app.route("/aup")
def aup_policy():
    return render_template("aup.html", updated=datetime.now().date())


@app.route("/security-policy")
def security_policy():
    return render_template("security_policy.html", updated=datetime.now().date())


@app.route("/sla")
def sla_policy():
    return render_template("sla.html", updated=datetime.now().date())


@app.route("/pricing")
def pricing_page():
    return render_template("pricing.html", plans=plans)


@app.route("/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, config.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        abort(400)

    try:
        billing.process_webhook_event(event)
    except Exception:
        traceback.print_exc()
        abort(500)
    return "", 200


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
                flash("Company not found, or Employee ID/PIN not recognized.")
                return render_template("staff_login.html", org=None, companies=_active_companies())

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
        flash("Company not found, or Employee ID/PIN not recognized.")
        return render_template("staff_login.html", org=org, companies=_active_companies())

    return render_template("staff_login.html", org=org, companies=_active_companies())


@app.route("/clock/exit")
def clock_exit():
    session.pop("employee_id", None)
    return redirect(url_for("staff_login"))


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

        if not devices_mod.is_trusted_device(request, org["id"], conn):
            session.pop("employee_id", None)
            flash("This computer isn't authorized to clock in/out for this company. Ask your administrator to register it under Admin > Devices.")
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

        today = today_in(org["timezone"])
        period_start, period_end = get_period_bounds(today)

        current_period_detail = get_period_entries(conn, org, period_start, period_end)
        my_current = next(
            (d for d in current_period_detail if d["employee_code"] == emp["employee_code"]), None
        )
        current_week_hours = my_current["total_hours"] if my_current else 0.0
        current_week_pay = my_current["total_due"] if my_current else 0.0

        day_totals = {period_start + timedelta(days=i): 0.0 for i in range(7)}
        if my_current:
            for e in my_current["entries"]:
                day = e["clock_in"].date()
                if day in day_totals:
                    day_totals[day] += e["hours"]
        max_day_hours = max(day_totals.values()) if day_totals else 0
        chart_days = [
            {
                "label": day.strftime("%a"),
                "hours": round(hours, 1),
                "pct": round(hours / max_day_hours * 100) if max_day_hours > 0 else 0,
            }
            for day, hours in sorted(day_totals.items())
        ]

        today_shift = conn.execute(
            "SELECT * FROM shifts WHERE employee_id=%s AND shift_start::date=%s ORDER BY shift_start LIMIT 1",
            (emp_id, today),
        ).fetchone()

    return render_template(
        "clock.html",
        employee=emp,
        is_clocked_in=bool(open_entry),
        today_shift=today_shift,
        current_week_hours=current_week_hours,
        current_week_pay=current_week_pay,
        chart_days=chart_days,
        now=now_in(org["timezone"]),
    )


@app.route("/pay-stubs")
def pay_stubs():
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

        period_start, period_end = get_period_bounds(today_in(org["timezone"]))
        periods = [(period_start, period_end)] + get_prior_periods(period_start, count=11)
        stubs = []
        for start, end in periods:
            rows = calculate_payroll(conn, org, start, end)
            mine = next((r for r in rows if r["employee_code"] == emp["employee_code"]), None)
            stubs.append({
                "period_start": start,
                "period_end": end,
                "hours": mine["total_hours"] if mine else 0.0,
                "regular_hours": mine["regular_hours"] if mine else 0.0,
                "overtime_hours": mine["overtime_hours"] if mine else 0.0,
                "pay": mine["pay"] if mine else 0.0,
            })

    return render_template("pay_stubs.html", employee=emp, stubs=stubs)


@app.route("/pay-stubs/<period_start>")
def pay_stub_detail(period_start):
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    try:
        start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
    except ValueError:
        abort(404)

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

        _, end_date = get_period_bounds(start_date)
        detail = get_period_entries(conn, org, start_date, end_date)
        mine = next((d for d in detail if d["employee_code"] == emp["employee_code"]), None)

    if mine is None:
        mine = {
            "entries": [], "total_hours": 0.0, "regular_hours": 0.0,
            "overtime_hours": 0.0, "total_due": 0.0, "hourly_rate": emp["hourly_rate"],
        }

    return render_template(
        "pay_stub_detail.html", employee=emp, org=org,
        period_start=start_date, period_end=end_date, stub=mine,
    )


@app.route("/pto", methods=["GET", "POST"])
def pto_requests_page():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        if request.method == "POST":
            start_raw = request.form.get("start_date", "").strip()
            end_raw = request.form.get("end_date", "").strip()
            hours_raw = request.form.get("hours", "").strip()
            reason = request.form.get("reason", "").strip()

            try:
                start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
                hours = float(hours_raw)
            except ValueError:
                flash("Enter a valid date range and number of hours.")
                return redirect(url_for("pto_requests_page"))

            if end_date < start_date:
                flash("End date must be on or after the start date.")
                return redirect(url_for("pto_requests_page"))
            if hours <= 0:
                flash("Hours requested must be greater than zero.")
                return redirect(url_for("pto_requests_page"))

            conn.execute(
                "INSERT INTO pto_requests (org_id, employee_id, start_date, end_date, hours, reason) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (org_id, emp_id, start_date, end_date, hours, reason or None),
            )
            audit.log(conn, org_id, "employee", emp_id, "pto.requested", f"{start_date} - {end_date} ({hours}h)")
            conn.commit()
            flash("Time off request submitted.")
            return redirect(url_for("pto_requests_page"))

        my_requests = conn.execute(
            "SELECT * FROM pto_requests WHERE employee_id=%s ORDER BY requested_at DESC", (emp_id,)
        ).fetchall()

    return render_template("pto_requests.html", employee=emp, requests=my_requests)


@app.route("/schedule")
def my_schedule_page():
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

        upcoming_shifts = conn.execute(
            "SELECT * FROM shifts WHERE employee_id=%s AND shift_end >= %s ORDER BY shift_start LIMIT 25",
            (emp_id, now_in(org["timezone"])),
        ).fetchall()

        offered_shift_ids = {
            row["shift_id"] for row in conn.execute(
                "SELECT shift_id FROM shift_swap_requests WHERE requested_by_employee_id=%s AND status='open'",
                (emp_id,),
            ).fetchall()
        }

    return render_template(
        "my_schedule.html", employee=emp, upcoming_shifts=upcoming_shifts, offered_shift_ids=offered_shift_ids,
    )


@app.route("/time-history")
def time_history_page():
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

        recent_entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s ORDER BY clock_in DESC LIMIT 25",
            (emp_id,),
        ).fetchall()

        period_start, _ = get_period_bounds(today_in(org["timezone"]))
        weekly_history = []
        for start, end in [(period_start, period_start + timedelta(days=6))] + get_prior_periods(period_start, count=8):
            rows = calculate_payroll(conn, org, start, end)
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

    return render_template("time_history.html", employee=emp, history=history, weekly_history=weekly_history)


@app.route("/profile")
def profile_page():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        department = None
        if emp.get("department_id"):
            department = conn.execute(
                "SELECT name FROM departments WHERE id=%s", (emp["department_id"],)
            ).fetchone()

    return render_template("profile.html", employee=emp, department=department["name"] if department else None)


@app.route("/announcements")
def employee_announcements_page():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        announcements = conn.execute(
            "SELECT * FROM announcements WHERE org_id=%s ORDER BY created_at DESC LIMIT 25", (org_id,)
        ).fetchall()

    return render_template("employee_announcements.html", employee=emp, announcements=announcements)


@app.route("/messages", methods=["GET", "POST"])
def messages_page():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if not body:
                flash("Enter a message before sending.")
                return redirect(url_for("messages_page"))
            conn.execute(
                "INSERT INTO messages (org_id, employee_id, sender_type, body) VALUES (%s,%s,'employee',%s)",
                (org_id, emp_id, body),
            )
            notifications.notify_admins(
                conn, org_id, "message_from_employee", f"New message from {emp['name']}",
                body=body[:200], link=url_for("admin_message_thread", employee_id=emp_id),
            )
            conn.commit()
            return redirect(url_for("messages_page"))

        thread = conn.execute(
            "SELECT m.*, a.username AS admin_username FROM messages m "
            "LEFT JOIN admin_users a ON m.sender_admin_id = a.id "
            "WHERE m.employee_id=%s ORDER BY m.created_at",
            (emp_id,),
        ).fetchall()
        conn.execute(
            "UPDATE employees SET messages_read_by_employee_at=NOW() WHERE id=%s", (emp_id,)
        )
        conn.commit()

    return render_template("messages.html", employee=emp, thread=thread)


@app.route("/performance")
def performance_page():
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

        rows = performance.shift_attendance(conn, org_id, now_in(org["timezone"]), weeks=8, employee_id=emp_id)
        summary = performance.summarize_attendance(rows)

    return render_template("performance.html", employee=emp, summary=summary, rows=rows)


@app.route("/recognition")
def recognition_page():
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

        rows = performance.shift_attendance(conn, org_id, now_in(org["timezone"]), weeks=8, employee_id=emp_id)
        summary = performance.summarize_attendance(rows)
        earned = recognition.automated_badges(summary)

        kudos = conn.execute(
            "SELECT r.*, a.username AS admin_username FROM recognitions r "
            "LEFT JOIN admin_users a ON r.given_by_admin_id = a.id "
            "WHERE r.employee_id=%s ORDER BY r.created_at DESC",
            (emp_id,),
        ).fetchall()

    return render_template(
        "recognition.html", employee=emp, earned_badges=earned, kudos=kudos,
        badge_types=recognition.BADGE_TYPES,
    )


@app.route("/notifications")
def notifications_page():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        items = conn.execute(
            "SELECT * FROM notifications WHERE employee_id=%s ORDER BY created_at DESC LIMIT 50",
            (emp_id,),
        ).fetchall()
        conn.execute(
            "UPDATE notifications SET read_at=NOW() WHERE employee_id=%s AND read_at IS NULL", (emp_id,)
        )
        conn.commit()

    return render_template("notifications.html", employee=emp, items=items)


@app.route("/shifts/<int:shift_id>/offer-swap", methods=["POST"])
def shift_offer_swap(shift_id):
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        shift = conn.execute(
            "SELECT * FROM shifts WHERE id=%s AND employee_id=%s AND org_id=%s", (shift_id, emp_id, org_id)
        ).fetchone()
        if shift is None:
            flash("Shift not found.")
            return redirect(url_for("clock_action"))

        existing = conn.execute(
            "SELECT 1 FROM shift_swap_requests WHERE shift_id=%s AND status='open'", (shift_id,)
        ).fetchone()
        if existing:
            flash("This shift is already offered for swap.")
            return redirect(url_for("clock_action"))

        conn.execute(
            "INSERT INTO shift_swap_requests (org_id, shift_id, requested_by_employee_id) VALUES (%s,%s,%s)",
            (org_id, shift_id, emp_id),
        )
        audit.log(conn, org_id, "employee", emp_id, "shift.swap_offered", f"shift {shift_id}")
        conn.commit()
    flash("Shift offered for swap. Anyone on your team can now claim it.")
    return redirect(url_for("clock_action"))


@app.route("/shifts/marketplace")
def shift_marketplace():
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, org_id)
        ).fetchone()
        if emp is None:
            session.pop("employee_id", None)
            return redirect(url_for("staff_login"))

        open_swaps = conn.execute(
            "SELECT sw.*, s.shift_start, s.shift_end, s.notes, e.name AS offered_by_name "
            "FROM shift_swap_requests sw "
            "JOIN shifts s ON sw.shift_id = s.id "
            "JOIN employees e ON sw.requested_by_employee_id = e.id "
            "WHERE sw.org_id=%s AND sw.status='open' ORDER BY s.shift_start",
            (org_id,),
        ).fetchall()

    return render_template("shift_marketplace.html", employee=emp, open_swaps=open_swaps)


@app.route("/shifts/marketplace/<int:swap_id>/claim", methods=["POST"])
def shift_swap_claim(swap_id):
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        swap = conn.execute(
            "SELECT * FROM shift_swap_requests WHERE id=%s AND org_id=%s AND status='open'",
            (swap_id, org_id),
        ).fetchone()
        if swap is None:
            flash("That shift is no longer available to claim.")
            return redirect(url_for("shift_marketplace"))
        if swap["requested_by_employee_id"] == emp_id:
            flash("You can't claim your own shift offer.")
            return redirect(url_for("shift_marketplace"))

        claimer = conn.execute("SELECT name FROM employees WHERE id=%s", (emp_id,)).fetchone()
        shift = conn.execute("SELECT * FROM shifts WHERE id=%s", (swap["shift_id"],)).fetchone()

        conn.execute("UPDATE shifts SET employee_id=%s WHERE id=%s", (emp_id, swap["shift_id"]))
        conn.execute(
            "UPDATE shift_swap_requests SET status='claimed', claimed_by_employee_id=%s, claimed_at=NOW() "
            "WHERE id=%s",
            (emp_id, swap_id),
        )
        audit.log(conn, org_id, "employee", emp_id, "shift.swap_claimed", f"shift {swap['shift_id']}")
        notifications.notify_employee(
            conn, org_id, swap["requested_by_employee_id"], "shift_claimed",
            f"{claimer['name']} claimed your {shift['shift_start'].strftime('%a %b %d')} shift",
            body=f"{claimer['name']} picked up the shift you offered for swap "
                 f"({shift['shift_start'].strftime('%I:%M %p')} - {shift['shift_end'].strftime('%I:%M %p')}).",
            link=url_for("clock_action"),
        )
        conn.commit()
    flash("Shift claimed! It's now on your schedule.")
    return redirect(url_for("shift_marketplace"))


@app.route("/shifts/marketplace/<int:swap_id>/cancel", methods=["POST"])
def shift_swap_cancel(swap_id):
    emp_id = session.get("employee_id")
    org_id = session.get("org_id")
    if not emp_id or not org_id:
        return redirect(url_for("staff_login"))

    with get_db() as conn:
        swap = conn.execute(
            "SELECT * FROM shift_swap_requests WHERE id=%s AND org_id=%s AND requested_by_employee_id=%s "
            "AND status='open'",
            (swap_id, org_id, emp_id),
        ).fetchone()
        if swap is None:
            flash("That offer can't be canceled.")
            return redirect(url_for("shift_marketplace"))

        conn.execute("UPDATE shift_swap_requests SET status='canceled' WHERE id=%s", (swap_id,))
        audit.log(conn, org_id, "employee", emp_id, "shift.swap_canceled", f"shift {swap['shift_id']}")
        conn.commit()
    flash("Swap offer canceled.")
    return redirect(url_for("shift_marketplace"))


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
            flash("Company not found, or username/password not recognized.")
            return render_template("admin_login.html", companies=_active_companies())

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
        flash("Company not found, or username/password not recognized.")
    return render_template("admin_login.html", companies=_active_companies())


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
        detail = get_period_entries(conn, g.org, period_start, period_end)
        history = [
            {
                "period_start": start,
                "period_end": end,
                "rows": calculate_payroll(conn, g.org, start, end),
            }
            for start, end in get_prior_periods(period_start, count=4)
        ]
        employee_count = conn.execute(
            "SELECT COUNT(*) AS c FROM employees WHERE org_id=%s AND active=1", (g.org["id"],)
        ).fetchone()["c"]
        has_clocked_in_ever = conn.execute(
            "SELECT 1 FROM time_entries te JOIN employees e ON te.employee_id=e.id "
            "WHERE e.org_id=%s LIMIT 1", (g.org["id"],)
        ).fetchone() is not None
        has_sent_report = conn.execute(
            "SELECT 1 FROM report_log WHERE org_id=%s LIMIT 1", (g.org["id"],)
        ).fetchone() is not None

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
    active_today = [d for d in detail if any(e["clock_in"].date() == today for e in d["entries"])]
    clocked_in_now = [d for d in detail if d["incomplete"]]
    stats = {
        "employees": employee_count,
        "active_today": len(active_today),
        "active_today_pct": round(len(active_today) / employee_count * 100) if employee_count else 0,
        "clocked_in_now": clocked_in_now,
        "hours_this_week": round(sum(d["total_hours"] for d in detail), 2),
        "weekly_payroll": round(sum(d["total_due"] for d in detail), 2),
    }

    day_totals = {period_start + timedelta(days=i): 0.0 for i in range(7)}
    for d in detail:
        for e in d["entries"]:
            day = e["clock_in"].date()
            if day in day_totals:
                day_totals[day] += e["hours"]
    max_day_hours = max(day_totals.values()) if day_totals else 0
    chart_days = [
        {
            "label": day.strftime("%a"),
            "hours": round(hours, 1),
            "pct": round(hours / max_day_hours * 100) if max_day_hours > 0 else 0,
        }
        for day, hours in sorted(day_totals.items())
    ]

    checklist = None
    if g.org.get("onboarding_completed_at"):
        checklist = [
            {"label": "Company Created", "done": True, "url": None},
            {"label": "Payroll Configured", "done": True, "url": None},
            {"label": "Add More Employees", "done": employee_count > 0, "url": url_for("admin_employees")},
            {"label": "Test Clock In", "done": has_clocked_in_ever, "url": url_for("staff_login")},
            {"label": "Configure Reports", "done": True, "url": url_for("admin_dashboard")},
            {"label": "Generate First Payroll Report", "done": has_sent_report, "url": url_for("admin_send_report_now")},
        ]
        if all(item["done"] for item in checklist):
            checklist = None

    welcome_company_code = session.pop("welcome_company_code", None)
    welcome_admin_creds = session.pop("welcome_admin_creds", None)

    return render_template(
        "admin_dashboard.html",
        rows=rows,
        detail=detail,
        history=history,
        period_start=period_start,
        period_end=period_end,
        stats=stats,
        chart_days=chart_days,
        checklist=checklist,
        welcome_company_code=welcome_company_code,
        welcome_admin_creds=welcome_admin_creds,
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
        limit = plans.employee_limit(g.org)
        if limit is not None:
            with get_db() as conn:
                active_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM employees WHERE org_id=%s AND active=1", (g.org["id"],)
                ).fetchone()["c"]
            if active_count >= limit:
                flash(
                    f"Your {plans.get_plan(g.org)['label']} plan is limited to {limit} active employees. "
                    f"Upgrade your plan on the Company Settings page to add more."
                )
                return redirect(url_for("admin_employees"))

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
            try:
                pto_balance = float(request.form.get("pto_balance_hours", emp["pto_balance_hours"]))
            except ValueError:
                flash("PTO balance must be a number.")
                return render_template("admin_employee_form.html", employee=emp)

            if pin:
                conn.execute(
                    "UPDATE employees SET name=%s, hourly_rate=%s, worker_type=%s, active=%s, pin_hash=%s, "
                    "pto_balance_hours=%s WHERE id=%s AND org_id=%s",
                    (name, rate, worker_type, active, generate_password_hash(pin), pto_balance, emp_id, g.org["id"]),
                )
            else:
                conn.execute(
                    "UPDATE employees SET name=%s, hourly_rate=%s, worker_type=%s, active=%s, pto_balance_hours=%s "
                    "WHERE id=%s AND org_id=%s",
                    (name, rate, worker_type, active, pto_balance, emp_id, g.org["id"]),
                )
            conn.commit()
            flash("Updated.")
            return redirect(url_for("admin_employees"))

    return render_template("admin_employee_form.html", employee=emp)


@app.route("/admin/employees/<int:emp_id>/time-entries/new", methods=["GET", "POST"])
@admin_required
def admin_time_entry_new(emp_id):
    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, g.org["id"])
        ).fetchone()
    if emp is None:
        flash("Employee not found.")
        return redirect(url_for("admin_employees"))

    if request.method == "POST":
        clock_in_raw = request.form.get("clock_in", "").strip()
        clock_out_raw = request.form.get("clock_out", "").strip()

        try:
            clock_in = datetime.strptime(clock_in_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Enter a valid clock-in date and time.")
            return render_template("admin_time_entry_form.html", employee=emp)

        clock_out = None
        if clock_out_raw:
            try:
                clock_out = datetime.strptime(clock_out_raw, "%Y-%m-%dT%H:%M")
            except ValueError:
                flash("Enter a valid clock-out date and time, or leave it blank.")
                return render_template("admin_time_entry_form.html", employee=emp)
            if clock_out <= clock_in:
                flash("Clock-out must be after clock-in.")
                return render_template("admin_time_entry_form.html", employee=emp)

        with get_db() as conn:
            conn.execute(
                "INSERT INTO time_entries (employee_id, clock_in, clock_out, is_manual, created_by_admin_id) "
                "VALUES (%s, %s, %s, TRUE, %s)",
                (emp_id, clock_in, clock_out, g.admin["id"]),
            )
            audit.log(
                conn, g.org["id"], "admin", g.admin["id"], "time_entry.manual_added",
                f"{emp['name']} ({emp['employee_code']}): {clock_in} - {clock_out or 'open'}",
            )
            conn.commit()
        flash(f"Manual time entry added for {emp['name']}.")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_time_entry_form.html", employee=emp)


@app.route("/admin/time-entries/<int:entry_id>/delete", methods=["POST"])
@admin_required
def admin_time_entry_delete(entry_id):
    with get_db() as conn:
        entry = conn.execute(
            "SELECT te.*, e.name AS employee_name, e.employee_code FROM time_entries te "
            "JOIN employees e ON te.employee_id = e.id "
            "WHERE te.id=%s AND e.org_id=%s",
            (entry_id, g.org["id"]),
        ).fetchone()
        if entry is None:
            flash("Time entry not found.")
            return redirect(url_for("admin_dashboard"))

        conn.execute("DELETE FROM time_entries WHERE id=%s", (entry_id,))
        audit.log(
            conn, g.org["id"], "admin", g.admin["id"], "time_entry.deleted",
            f"{entry['employee_name']} ({entry['employee_code']}): {entry['clock_in']} - {entry['clock_out'] or 'open'}",
        )
        conn.commit()
    flash("Time entry deleted.")
    return redirect(url_for("admin_dashboard") + "#timesheets")


@app.route("/admin/schedule")
@admin_required
def admin_schedule():
    week_param = request.args.get("week", "")
    try:
        reference_date = datetime.strptime(week_param, "%Y-%m-%d").date()
    except ValueError:
        reference_date = today_in(g.org["timezone"])

    week_start, week_end = schedule.week_bounds(reference_date)
    days = schedule.week_days(week_start)

    with get_db() as conn:
        active_series = conn.execute(
            "SELECT * FROM shift_series WHERE org_id=%s AND active=TRUE", (g.org["id"],)
        ).fetchall()
        horizon = max(today_in(g.org["timezone"]) + timedelta(weeks=schedule.SERIES_GENERATE_WEEKS_AHEAD), week_end)
        for series in active_series:
            schedule.generate_series_occurrences(conn, series, horizon)
        conn.commit()

        shifts = conn.execute(
            "SELECT s.*, e.name AS employee_name FROM shifts s "
            "JOIN employees e ON s.employee_id = e.id "
            "WHERE s.org_id=%s AND s.shift_start >= %s AND s.shift_start < %s "
            "ORDER BY s.shift_start",
            (g.org["id"], datetime.combine(week_start, datetime.min.time()),
             datetime.combine(week_end + timedelta(days=1), datetime.min.time())),
        ).fetchall()

    shifts_by_day = {d: [] for d in days}
    for s in shifts:
        day = s["shift_start"].date()
        if day in shifts_by_day:
            shifts_by_day[day].append(s)

    return render_template(
        "admin_schedule.html",
        week_start=week_start, week_end=week_end,
        prev_week=(week_start - timedelta(days=7)).isoformat(),
        next_week=(week_start + timedelta(days=7)).isoformat(),
        shifts_by_day=shifts_by_day,
    )


@app.route("/admin/schedule/new", methods=["GET", "POST"])
@admin_required
def admin_shift_new():
    with get_db() as conn:
        employees = conn.execute(
            "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (g.org["id"],)
        ).fetchall()

    default_date = request.args.get("date", "")

    if request.method == "POST":
        emp_id = request.form.get("employee_id", "")
        start_raw = request.form.get("shift_start", "").strip()
        end_raw = request.form.get("shift_end", "").strip()
        notes = request.form.get("notes", "").strip()
        repeat_weekly = request.form.get("repeat_weekly") == "on"

        with get_db() as conn:
            emp = conn.execute(
                "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, g.org["id"])
            ).fetchone()

        if emp is None:
            flash("Choose a valid employee.")
            return render_template("admin_shift_form.html", employees=employees, shift=None, default_date=default_date)

        try:
            shift_start = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
            shift_end = datetime.strptime(end_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Enter valid start and end times.")
            return render_template("admin_shift_form.html", employees=employees, shift=None, default_date=default_date)

        if shift_end <= shift_start:
            flash("Shift end must be after shift start.")
            return render_template("admin_shift_form.html", employees=employees, shift=None, default_date=default_date)

        with get_db() as conn:
            if repeat_weekly:
                conn.execute(
                    "INSERT INTO shift_series (org_id, employee_id, anchor_date, start_time, end_time, notes, "
                    "created_by_admin_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (g.org["id"], emp_id, shift_start.date(), shift_start.time(), shift_end.time(),
                     notes or None, g.admin["id"]),
                )
                series = conn.execute(
                    "SELECT * FROM shift_series WHERE org_id=%s AND employee_id=%s AND anchor_date=%s "
                    "ORDER BY id DESC LIMIT 1",
                    (g.org["id"], emp_id, shift_start.date()),
                ).fetchone()
                horizon = shift_start.date() + timedelta(weeks=schedule.SERIES_GENERATE_WEEKS_AHEAD)
                schedule.generate_series_occurrences(conn, series, horizon)
                audit.log(
                    conn, g.org["id"], "admin", g.admin["id"], "shift.series_created",
                    f"{emp['name']}: weekly from {shift_start.date()} {shift_start.time()}-{shift_end.time()}",
                )
                flash(f"Repeating weekly shift created for {emp['name']} - it'll keep going until you end the series.")
            else:
                conn.execute(
                    "INSERT INTO shifts (org_id, employee_id, shift_start, shift_end, notes, created_by_admin_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (g.org["id"], emp_id, shift_start, shift_end, notes or None, g.admin["id"]),
                )
                audit.log(
                    conn, g.org["id"], "admin", g.admin["id"], "shift.created",
                    f"{emp['name']}: {shift_start} - {shift_end}",
                )
                flash(f"Shift added for {emp['name']}.")
            conn.commit()
        return redirect(url_for("admin_schedule", week=schedule.week_bounds(shift_start.date())[0].isoformat()))

    return render_template("admin_shift_form.html", employees=employees, shift=None, default_date=default_date)


@app.route("/admin/schedule/<int:shift_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_shift_edit(shift_id):
    with get_db() as conn:
        shift = conn.execute(
            "SELECT * FROM shifts WHERE id=%s AND org_id=%s", (shift_id, g.org["id"])
        ).fetchone()
        employees = conn.execute(
            "SELECT * FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (g.org["id"],)
        ).fetchall()

    if shift is None:
        flash("Shift not found.")
        return redirect(url_for("admin_schedule"))

    if request.method == "POST":
        emp_id = request.form.get("employee_id", "")
        start_raw = request.form.get("shift_start", "").strip()
        end_raw = request.form.get("shift_end", "").strip()
        notes = request.form.get("notes", "").strip()

        with get_db() as conn:
            emp = conn.execute(
                "SELECT * FROM employees WHERE id=%s AND org_id=%s", (emp_id, g.org["id"])
            ).fetchone()

        if emp is None:
            flash("Choose a valid employee.")
            return render_template("admin_shift_form.html", employees=employees, shift=shift, default_date="")

        try:
            shift_start = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
            shift_end = datetime.strptime(end_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Enter valid start and end times.")
            return render_template("admin_shift_form.html", employees=employees, shift=shift, default_date="")

        if shift_end <= shift_start:
            flash("Shift end must be after shift start.")
            return render_template("admin_shift_form.html", employees=employees, shift=shift, default_date="")

        with get_db() as conn:
            conn.execute(
                "UPDATE shifts SET employee_id=%s, shift_start=%s, shift_end=%s, notes=%s "
                "WHERE id=%s AND org_id=%s",
                (emp_id, shift_start, shift_end, notes or None, shift_id, g.org["id"]),
            )
            audit.log(
                conn, g.org["id"], "admin", g.admin["id"], "shift.updated",
                f"{emp['name']}: {shift_start} - {shift_end}",
            )
            conn.commit()
        flash(f"Shift updated for {emp['name']}.")
        return redirect(url_for("admin_schedule", week=schedule.week_bounds(shift_start.date())[0].isoformat()))

    return render_template("admin_shift_form.html", employees=employees, shift=shift, default_date="")


@app.route("/admin/schedule/<int:shift_id>/delete", methods=["POST"])
@admin_required
def admin_shift_delete(shift_id):
    with get_db() as conn:
        shift = conn.execute(
            "SELECT s.*, e.name AS employee_name FROM shifts s JOIN employees e ON s.employee_id = e.id "
            "WHERE s.id=%s AND s.org_id=%s",
            (shift_id, g.org["id"]),
        ).fetchone()
        if shift is None:
            flash("Shift not found.")
            return redirect(url_for("admin_schedule"))

        conn.execute("DELETE FROM shifts WHERE id=%s AND org_id=%s", (shift_id, g.org["id"]))
        audit.log(
            conn, g.org["id"], "admin", g.admin["id"], "shift.deleted",
            f"{shift['employee_name']}: {shift['shift_start']} - {shift['shift_end']}",
        )
        conn.commit()
    flash("Shift deleted.")
    return redirect(url_for("admin_schedule", week=schedule.week_bounds(shift["shift_start"].date())[0].isoformat()))


@app.route("/admin/schedule/<int:shift_id>/copy-4-weeks", methods=["POST"])
@admin_required
def admin_shift_copy_4_weeks(shift_id):
    with get_db() as conn:
        shift = conn.execute(
            "SELECT s.*, e.name AS employee_name FROM shifts s JOIN employees e ON s.employee_id = e.id "
            "WHERE s.id=%s AND s.org_id=%s",
            (shift_id, g.org["id"]),
        ).fetchone()
        if shift is None:
            flash("Shift not found.")
            return redirect(url_for("admin_schedule"))

        created = 0
        for weeks_out in (1, 2, 3, 4):
            new_start = shift["shift_start"] + timedelta(weeks=weeks_out)
            new_end = shift["shift_end"] + timedelta(weeks=weeks_out)
            exists = conn.execute(
                "SELECT 1 FROM shifts WHERE employee_id=%s AND shift_start=%s",
                (shift["employee_id"], new_start),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                "INSERT INTO shifts (org_id, employee_id, shift_start, shift_end, notes, created_by_admin_id) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (g.org["id"], shift["employee_id"], new_start, new_end, shift["notes"], g.admin["id"]),
            )
            created += 1
        audit.log(
            conn, g.org["id"], "admin", g.admin["id"], "shift.copied_4_weeks",
            f"{shift['employee_name']}: {shift['shift_start']} x{created}",
        )
        conn.commit()
    flash(f"Copied this shift to the next 4 weeks ({created} new shift{'s' if created != 1 else ''} added).")
    return redirect(url_for("admin_schedule", week=schedule.week_bounds(shift["shift_start"].date())[0].isoformat()))


@app.route("/admin/schedule/series/<int:series_id>/end", methods=["POST"])
@admin_required
def admin_shift_series_end(series_id):
    with get_db() as conn:
        series = conn.execute(
            "SELECT s.*, e.name AS employee_name FROM shift_series s JOIN employees e ON s.employee_id = e.id "
            "WHERE s.id=%s AND s.org_id=%s",
            (series_id, g.org["id"]),
        ).fetchone()
        if series is None:
            flash("Series not found.")
            return redirect(url_for("admin_schedule"))

        conn.execute("UPDATE shift_series SET active=FALSE WHERE id=%s", (series_id,))
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "shift.series_ended", series["employee_name"])
        conn.commit()
    flash(f"Ended the repeating series for {series['employee_name']}. Already-scheduled shifts are untouched.")
    return redirect(url_for("admin_schedule"))


def _send_current_period_report(org):
    recipients = [r.strip() for r in (org["report_recipients"] or "").split(",") if r.strip()]
    if not recipients:
        raise RuntimeError("No report recipients configured for this organization.")
    today = today_in(org["timezone"])
    period_start, period_end = get_period_bounds(today)
    with get_db() as conn:
        rows = calculate_payroll(conn, org, period_start, period_end)
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


@app.route("/admin/devices", methods=["GET", "POST"])
@admin_required
def admin_devices():
    if request.method == "POST":
        action = request.form.get("action")
        with get_db() as conn:
            if action == "register":
                limit = plans.device_limit(g.org)
                if limit is not None:
                    active_count = conn.execute(
                        "SELECT COUNT(*) AS c FROM devices WHERE org_id=%s AND status='active'", (g.org["id"],)
                    ).fetchone()["c"]
                    if active_count >= limit:
                        flash(
                            f"Your {plans.get_plan(g.org)['label']} plan is limited to {limit} authorized "
                            f"device{'s' if limit != 1 else ''}. Upgrade your plan on the Company Settings page to add more."
                        )
                        return redirect(url_for("admin_devices"))

                name = request.form.get("device_name", "").strip() or "Office Computer"
                dev_id, raw_token = devices_mod.register_device(conn, g.org["id"], name, g.admin["id"])
                audit.log(conn, g.org["id"], "admin", g.admin["id"], "device.registered", name)
                conn.commit()
                resp = make_response(redirect(url_for("admin_devices")))
                resp = devices_mod.issue_device_cookie(resp, g.org["id"], raw_token)
                flash(f"'{name}' registered as a trusted device for this browser.")
                return resp
            elif action in ("disable", "remove"):
                device_id = request.form.get("device_id", "")
                if device_id.isdigit():
                    if action == "disable":
                        conn.execute(
                            "UPDATE devices SET status='disabled' WHERE id=%s AND org_id=%s",
                            (device_id, g.org["id"]),
                        )
                        audit.log(conn, g.org["id"], "admin", g.admin["id"], "device.disabled", device_id)
                    else:
                        conn.execute(
                            "DELETE FROM devices WHERE id=%s AND org_id=%s", (device_id, g.org["id"])
                        )
                        audit.log(conn, g.org["id"], "admin", g.admin["id"], "device.removed", device_id)
                    conn.commit()
        return redirect(url_for("admin_devices"))

    with get_db() as conn:
        device_list = conn.execute(
            "SELECT * FROM devices WHERE org_id=%s ORDER BY created_at DESC", (g.org["id"],)
        ).fetchall()
    return render_template(
        "admin_devices.html", devices=device_list,
        user_agent=request.headers.get("User-Agent", "Unknown device"),
    )


@app.route("/admin/announcements", methods=["GET", "POST"])
@admin_required
def admin_announcements():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or not body:
            flash("Title and message are both required.")
        else:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO announcements (org_id, title, body, created_by_admin_id) VALUES (%s,%s,%s,%s)",
                    (g.org["id"], title, body, g.admin["id"]),
                )
                audit.log(conn, g.org["id"], "admin", g.admin["id"], "announcement.posted", title)
                conn.commit()
            flash("Announcement posted.")
        return redirect(url_for("admin_announcements"))

    with get_db() as conn:
        announcements = conn.execute(
            "SELECT * FROM announcements WHERE org_id=%s ORDER BY created_at DESC", (g.org["id"],)
        ).fetchall()
    return render_template("admin_announcements.html", announcements=announcements)


@app.route("/admin/announcements/<int:announcement_id>/delete", methods=["POST"])
@admin_required
def admin_announcement_delete(announcement_id):
    with get_db() as conn:
        announcement = conn.execute(
            "SELECT * FROM announcements WHERE id=%s AND org_id=%s", (announcement_id, g.org["id"])
        ).fetchone()
        if announcement is None:
            flash("Announcement not found.")
            return redirect(url_for("admin_announcements"))
        conn.execute("DELETE FROM announcements WHERE id=%s AND org_id=%s", (announcement_id, g.org["id"]))
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "announcement.deleted", announcement["title"])
        conn.commit()
    flash("Announcement deleted.")
    return redirect(url_for("admin_announcements"))


@app.route("/admin/pto")
@admin_required
def admin_pto():
    with get_db() as conn:
        requests_ = conn.execute(
            "SELECT r.*, e.name AS employee_name, e.employee_code, e.pto_balance_hours FROM pto_requests r "
            "JOIN employees e ON r.employee_id = e.id "
            "WHERE r.org_id=%s ORDER BY (r.status = 'pending') DESC, r.requested_at DESC",
            (g.org["id"],),
        ).fetchall()
    return render_template("admin_pto.html", requests=requests_)


@app.route("/admin/pto/<int:request_id>/approve", methods=["POST"])
@admin_required
def admin_pto_approve(request_id):
    with get_db() as conn:
        req = conn.execute(
            "SELECT r.*, e.name AS employee_name, e.pto_balance_hours FROM pto_requests r "
            "JOIN employees e ON r.employee_id = e.id "
            "WHERE r.id=%s AND r.org_id=%s AND r.status='pending'",
            (request_id, g.org["id"]),
        ).fetchone()
        if req is None:
            flash("Request not found or already reviewed.")
            return redirect(url_for("admin_pto"))

        if req["hours"] > req["pto_balance_hours"]:
            flash(f"{req['employee_name']} only has {req['pto_balance_hours']:.1f} PTO hours available; approve anyway from Employees if you want to allow a negative balance.")

        conn.execute(
            "UPDATE pto_requests SET status='approved', reviewed_by_admin_id=%s, reviewed_at=NOW() WHERE id=%s",
            (g.admin["id"], request_id),
        )
        conn.execute(
            "UPDATE employees SET pto_balance_hours = pto_balance_hours - %s WHERE id=%s",
            (req["hours"], req["employee_id"]),
        )
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "pto.approved", f"{req['employee_name']}: {req['hours']}h")
        notifications.notify_employee(
            conn, g.org["id"], req["employee_id"], "pto_approved",
            "Your time off request was approved",
            body=f"{req['start_date'].strftime('%b %d')} - {req['end_date'].strftime('%b %d')} ({req['hours']}h) approved.",
            link=url_for("pto_requests_page"),
        )
        conn.commit()
    flash(f"Approved {req['employee_name']}'s time off request.")
    return redirect(url_for("admin_pto"))


@app.route("/admin/pto/<int:request_id>/deny", methods=["POST"])
@admin_required
def admin_pto_deny(request_id):
    with get_db() as conn:
        req = conn.execute(
            "SELECT r.*, e.name AS employee_name FROM pto_requests r JOIN employees e ON r.employee_id = e.id "
            "WHERE r.id=%s AND r.org_id=%s AND r.status='pending'",
            (request_id, g.org["id"]),
        ).fetchone()
        if req is None:
            flash("Request not found or already reviewed.")
            return redirect(url_for("admin_pto"))

        conn.execute(
            "UPDATE pto_requests SET status='denied', reviewed_by_admin_id=%s, reviewed_at=NOW() WHERE id=%s",
            (g.admin["id"], request_id),
        )
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "pto.denied", f"{req['employee_name']}: {req['hours']}h")
        notifications.notify_employee(
            conn, g.org["id"], req["employee_id"], "pto_denied",
            "Your time off request was denied",
            body=f"{req['start_date'].strftime('%b %d')} - {req['end_date'].strftime('%b %d')} ({req['hours']}h) denied.",
            link=url_for("pto_requests_page"),
        )
        conn.commit()
    flash(f"Denied {req['employee_name']}'s time off request.")
    return redirect(url_for("admin_pto"))


@app.route("/admin/messages")
@admin_required
def admin_messages():
    with get_db() as conn:
        threads = conn.execute(
            "SELECT e.id AS employee_id, e.name AS employee_name, e.employee_code, "
            "e.messages_read_by_admin_at, "
            "(SELECT body FROM messages m WHERE m.employee_id = e.id ORDER BY m.created_at DESC LIMIT 1) AS last_body, "
            "(SELECT created_at FROM messages m WHERE m.employee_id = e.id ORDER BY m.created_at DESC LIMIT 1) AS last_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.employee_id = e.id AND m.sender_type='employee' "
            " AND (e.messages_read_by_admin_at IS NULL OR m.created_at > e.messages_read_by_admin_at)) AS unread_count "
            "FROM employees e "
            "WHERE e.org_id=%s AND EXISTS (SELECT 1 FROM messages m WHERE m.employee_id = e.id) "
            "ORDER BY last_at DESC",
            (g.org["id"],),
        ).fetchall()
    return render_template("admin_messages.html", threads=threads)


@app.route("/admin/messages/<int:employee_id>", methods=["GET", "POST"])
@admin_required
def admin_message_thread(employee_id):
    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (employee_id, g.org["id"])
        ).fetchone()
        if emp is None:
            flash("Employee not found.")
            return redirect(url_for("admin_messages"))

        if request.method == "POST":
            body = request.form.get("body", "").strip()
            if not body:
                flash("Enter a message before sending.")
                return redirect(url_for("admin_message_thread", employee_id=employee_id))
            conn.execute(
                "INSERT INTO messages (org_id, employee_id, sender_type, sender_admin_id, body) "
                "VALUES (%s,%s,'admin',%s,%s)",
                (g.org["id"], employee_id, g.admin["id"], body),
            )
            notifications.notify_employee(
                conn, g.org["id"], employee_id, "message_from_admin", "New message from your manager",
                body=body[:200], link=url_for("messages_page"),
            )
            conn.commit()
            return redirect(url_for("admin_message_thread", employee_id=employee_id))

        thread = conn.execute(
            "SELECT m.*, a.username AS admin_username FROM messages m "
            "LEFT JOIN admin_users a ON m.sender_admin_id = a.id "
            "WHERE m.employee_id=%s ORDER BY m.created_at",
            (employee_id,),
        ).fetchall()
        conn.execute(
            "UPDATE employees SET messages_read_by_admin_at=NOW() WHERE id=%s", (employee_id,)
        )
        conn.commit()

    return render_template("admin_message_thread.html", employee=emp, thread=thread)


@app.route("/admin/performance")
@admin_required
def admin_performance():
    with get_db() as conn:
        leaderboard = performance.org_leaderboard(conn, g.org["id"], now_in(g.org["timezone"]), weeks=8)
    return render_template("admin_performance.html", leaderboard=leaderboard)


@app.route("/admin/performance/<int:employee_id>")
@admin_required
def admin_performance_employee(employee_id):
    with get_db() as conn:
        emp = conn.execute(
            "SELECT * FROM employees WHERE id=%s AND org_id=%s", (employee_id, g.org["id"])
        ).fetchone()
        if emp is None:
            flash("Employee not found.")
            return redirect(url_for("admin_performance"))
        rows = performance.shift_attendance(
            conn, g.org["id"], now_in(g.org["timezone"]), weeks=8, employee_id=employee_id
        )
        summary = performance.summarize_attendance(rows)
    return render_template("admin_performance_employee.html", employee=emp, summary=summary, rows=rows)


@app.route("/admin/recognition", methods=["GET", "POST"])
@admin_required
def admin_recognition():
    if request.method == "POST":
        try:
            employee_id = int(request.form.get("employee_id", ""))
        except ValueError:
            flash("Choose an employee.")
            return redirect(url_for("admin_recognition"))
        badge_type = request.form.get("badge_type", "")
        note = request.form.get("note", "").strip()
        if badge_type not in recognition.BADGE_TYPES:
            flash("Choose a valid badge.")
            return redirect(url_for("admin_recognition"))

        with get_db() as conn:
            emp = conn.execute(
                "SELECT * FROM employees WHERE id=%s AND org_id=%s", (employee_id, g.org["id"])
            ).fetchone()
            if emp is None:
                flash("Employee not found.")
                return redirect(url_for("admin_recognition"))
            conn.execute(
                "INSERT INTO recognitions (org_id, employee_id, given_by_admin_id, badge_type, note) "
                "VALUES (%s,%s,%s,%s,%s)",
                (g.org["id"], employee_id, g.admin["id"], badge_type, note or None),
            )
            audit.log(conn, g.org["id"], "admin", g.admin["id"], "recognition.given",
                       f"{emp['name']}: {recognition.BADGE_TYPES[badge_type]['label']}")
            badge_label = recognition.BADGE_TYPES[badge_type]["label"]
            notifications.notify_employee(
                conn, g.org["id"], employee_id, "recognition_given",
                f"You earned the {badge_label} badge!",
                body=note or None, link=url_for("recognition_page"),
            )
            conn.commit()
        flash(f"Gave {emp['name']} the {recognition.BADGE_TYPES[badge_type]['label']} badge.")
        return redirect(url_for("admin_recognition"))

    with get_db() as conn:
        employees = conn.execute(
            "SELECT id, name FROM employees WHERE org_id=%s AND active=1 ORDER BY name", (g.org["id"],)
        ).fetchall()
        feed = conn.execute(
            "SELECT r.*, e.name AS employee_name, a.username AS admin_username FROM recognitions r "
            "JOIN employees e ON r.employee_id = e.id "
            "LEFT JOIN admin_users a ON r.given_by_admin_id = a.id "
            "WHERE r.org_id=%s ORDER BY r.created_at DESC LIMIT 50",
            (g.org["id"],),
        ).fetchall()

    return render_template(
        "admin_recognition.html", employees=employees, feed=feed, badge_types=recognition.BADGE_TYPES,
    )


@app.route("/admin/notifications")
@admin_required
def admin_notifications():
    with get_db() as conn:
        items = conn.execute(
            "SELECT * FROM notifications WHERE admin_id=%s ORDER BY created_at DESC LIMIT 50",
            (g.admin["id"],),
        ).fetchall()
        conn.execute(
            "UPDATE notifications SET read_at=NOW() WHERE admin_id=%s AND read_at IS NULL", (g.admin["id"],)
        )
        conn.commit()
    return render_template("admin_notifications.html", items=items)


@app.route("/admin/settings", methods=["GET", "POST"])
@admin_required
def admin_settings():
    org = dict(g.org)
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
            "report_recipients": request.form.get("report_recipients", "").strip(),
        }
        if not fields["name"]:
            errors["company_name"] = "Company name is required."
        if not fields["address_line1"]:
            errors["address_line1"] = "Address is required."
        if not fields["phone"]:
            errors["phone"] = "Phone number is required."
        if not fields["report_recipients"] or "@" not in fields["report_recipients"]:
            errors["report_recipients"] = "Enter a valid notification email address."

        logo_data, logo_mime = None, None
        logo_file = request.files.get("logo")
        if logo_file and logo_file.filename:
            raw = logo_file.read()
            if len(raw) > 500 * 1024:
                errors["logo"] = "Logo must be 500KB or smaller."
            elif logo_file.mimetype not in ("image/png", "image/jpeg", "image/svg+xml"):
                errors["logo"] = "Logo must be a PNG, JPEG, or SVG file."
            else:
                logo_data, logo_mime = raw, logo_file.mimetype

        if errors:
            return render_template(
                "admin_settings.html", org={**org, **fields}, errors=errors, choices=choices, plans=plans
            )

        with get_db() as conn:
            if logo_data is not None:
                conn.execute(
                    "UPDATE organizations SET name=%s, dba_name=%s, business_type=%s, industry=%s, "
                    "address_line1=%s, city=%s, state=%s, zip=%s, country=%s, phone=%s, website=%s, "
                    "report_recipients=%s, logo_data=%s, logo_mime=%s WHERE id=%s",
                    (fields["name"], fields["dba_name"] or None, fields["business_type"] or None,
                     fields["industry"] or None, fields["address_line1"], fields["city"] or None,
                     fields["state"] or None, fields["zip"] or None, fields["country"], fields["phone"],
                     fields["website"] or None, fields["report_recipients"], logo_data, logo_mime, org["id"]),
                )
            else:
                conn.execute(
                    "UPDATE organizations SET name=%s, dba_name=%s, business_type=%s, industry=%s, "
                    "address_line1=%s, city=%s, state=%s, zip=%s, country=%s, phone=%s, website=%s, "
                    "report_recipients=%s WHERE id=%s",
                    (fields["name"], fields["dba_name"] or None, fields["business_type"] or None,
                     fields["industry"] or None, fields["address_line1"], fields["city"] or None,
                     fields["state"] or None, fields["zip"] or None, fields["country"], fields["phone"],
                     fields["website"] or None, fields["report_recipients"], org["id"]),
                )
            audit.log(conn, org["id"], "admin", g.admin["id"], "org.settings_updated", fields["name"])
            conn.commit()
        flash("Company profile updated.")
        return redirect(url_for("admin_settings"))

    return render_template("admin_settings.html", org=org, errors=errors, choices=choices, plans=plans)


@app.route("/admin/plan", methods=["POST"])
@admin_required
def admin_plan_update():
    plan_key = request.form.get("plan", "")
    if plan_key not in plans.PLANS:
        flash("Unknown plan selected.")
        return redirect(url_for("admin_settings"))

    try:
        if g.org.get("stripe_subscription_id"):
            billing.change_plan(g.org["stripe_subscription_id"], plan_key)
        else:
            with get_db() as conn:
                conn.execute("UPDATE organizations SET plan=%s WHERE id=%s", (plan_key, g.org["id"]))
                conn.commit()
    except stripe.error.StripeError:
        flash("We couldn't update your plan with Stripe. Please try again or contact support.")
        return redirect(url_for("admin_settings"))

    with get_db() as conn:
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "org.plan_changed", plan_key)
        conn.commit()
    flash(f"Plan changed to {plans.PLANS[plan_key]['label']}.")
    return redirect(url_for("admin_settings"))


@app.route("/admin/plan/cancel", methods=["POST"])
@admin_required
def admin_plan_cancel():
    if not g.org.get("stripe_subscription_id"):
        flash("No active subscription to cancel.")
        return redirect(url_for("admin_settings"))
    try:
        billing.cancel_at_period_end(g.org["stripe_subscription_id"])
    except stripe.error.StripeError:
        flash("We couldn't cancel your subscription with Stripe. Please try again or contact support.")
        return redirect(url_for("admin_settings"))
    with get_db() as conn:
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "org.subscription_cancel_scheduled", None)
        conn.commit()
    flash("Your subscription will end at the close of your current billing period. You can resume anytime before then.")
    return redirect(url_for("admin_settings"))


@app.route("/admin/plan/resume", methods=["POST"])
@admin_required
def admin_plan_resume():
    if not g.org.get("stripe_subscription_id"):
        flash("No subscription to resume.")
        return redirect(url_for("admin_settings"))
    try:
        billing.resume_subscription(g.org["stripe_subscription_id"])
    except stripe.error.StripeError:
        flash("We couldn't resume your subscription with Stripe. Please try again or contact support.")
        return redirect(url_for("admin_settings"))
    with get_db() as conn:
        audit.log(conn, g.org["id"], "admin", g.admin["id"], "org.subscription_resumed", None)
        conn.commit()
    flash("Your subscription has been resumed.")
    return redirect(url_for("admin_settings"))


@app.route("/org/<int:org_id>/logo")
def org_logo(org_id):
    with get_db() as conn:
        org = conn.execute(
            "SELECT logo_data, logo_mime FROM organizations WHERE id=%s", (org_id,)
        ).fetchone()
    if org is None or not org["logo_data"]:
        abort(404)
    return Response(bytes(org["logo_data"]), mimetype=org["logo_mime"] or "image/png")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
