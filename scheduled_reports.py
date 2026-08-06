"""Automatic weekly pay-period report, sent once per org per week per its own
report_weekday/report_hour/report_minute settings (all organization-local
time; see models.py's organizations table). Meant to be driven by a
background scheduler that calls run_due_reports() roughly once a minute
(see app.py) - this module contains no scheduling itself, just the "is
anything due right now, and if so send it" logic.
"""
import traceback

from email_report import send_report_email
from models import get_db
from payroll import calculate_payroll, get_period_bounds
from tz import now_in


def _claim_report_log(conn, org_id, report_date):
    """Atomically claims org_id+report_date in report_log. Returns True only
    for the caller that actually inserts the row, so this is safe to call
    from multiple worker processes (or an overlapping scheduler tick)
    without sending duplicate reports - and also means an org that already
    got a manual "Send Report Now" today won't get an automatic one too."""
    claimed = conn.execute(
        "INSERT INTO report_log (org_id, report_date) VALUES (%s, %s) "
        "ON CONFLICT (org_id, report_date) DO NOTHING RETURNING id",
        (org_id, report_date),
    ).fetchone()
    conn.commit()
    return claimed is not None


def _release_report_log(conn, org_id, report_date):
    conn.execute("DELETE FROM report_log WHERE org_id=%s AND report_date=%s", (org_id, report_date))
    conn.commit()


def _is_due(org, local_now):
    if local_now.weekday() != org["report_weekday"]:
        return False
    # Due at or any time after the scheduled minute, same day - not just in
    # the exact matching minute. Combined with the report_log claim below,
    # this means a transient failure (e.g. the email provider is briefly
    # down) gets retried on the next scheduler tick instead of silently
    # skipping that org until next week.
    scheduled = org["report_hour"] * 60 + org["report_minute"]
    now_minutes = local_now.hour * 60 + local_now.minute
    return now_minutes >= scheduled


def _send_for_org(org, today):
    recipients = [r.strip() for r in (org["report_recipients"] or "").split(",") if r.strip()]
    if not recipients:
        print(f"[scheduled-report] org {org['id']} ({org['name']}) has no report_recipients configured; skipping.")
        return

    with get_db() as conn:
        if not _claim_report_log(conn, org["id"], today):
            return  # already sent for this org today (manual send, or a previous tick)

    try:
        period_start, period_end = get_period_bounds(today)
        with get_db() as conn:
            rows = calculate_payroll(conn, org, period_start, period_end)
        send_report_email(org["name"], recipients, period_start, period_end, rows)
        print(f"[scheduled-report] sent weekly report for org {org['id']} ({org['name']}) covering {period_start}..{period_end}")
    except Exception:
        # Release the claim so the next scheduler tick (a minute later)
        # retries, rather than silently marking this week's report as sent
        # when it never actually went out.
        with get_db() as conn:
            _release_report_log(conn, org["id"], today)
        raise


def run_due_reports():
    with get_db() as conn:
        orgs = conn.execute("SELECT * FROM organizations WHERE status='active'").fetchall()

    for org in orgs:
        try:
            local_now = now_in(org["timezone"])
        except Exception:
            continue  # invalid/unknown timezone string; skip rather than crash the whole run

        if not _is_due(org, local_now):
            continue

        try:
            _send_for_org(org, local_now.date())
        except Exception:
            print(f"[scheduled-report] FAILED for org {org['id']} ({org['name']}):")
            traceback.print_exc()
