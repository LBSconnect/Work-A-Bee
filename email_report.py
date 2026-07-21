import requests

import config

TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
SEND_MAIL_URL = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


def _get_access_token():
    resp = requests.post(
        TOKEN_URL.format(tenant=config.MS_TENANT_ID),
        data={
            "grant_type": "client_credentials",
            "client_id": config.MS_CLIENT_ID,
            "client_secret": config.MS_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def send_report_email(org_name, recipients, period_start, period_end, rows):
    subject = (
        f"{org_name} weekly hours report: {period_start.strftime('%b %d, %Y')} - "
        f"{period_end.strftime('%b %d, %Y')}"
    )

    lines = [
        f"Weekly hours report for {org_name}",
        f"{period_start.strftime('%B %d, %Y')} - {period_end.strftime('%B %d, %Y')}",
        "",
        f"{'ID':<10}{'Name':<25}{'Type':<12}{'Hours':>8}{'Rate':>10}{'Pay':>10}",
    ]
    total_pay = 0.0
    for r in rows:
        flag = "  (still clocked in)" if r["incomplete"] else ""
        lines.append(
            f"{r['employee_code']:<10}{r['name']:<25}{r['worker_type'].capitalize():<12}"
            f"{r['total_hours']:>8.2f}"
            f"{'$' + format(r['hourly_rate'], '.2f'):>10}"
            f"{'$' + format(r['pay'], '.2f'):>10}{flag}"
        )
        total_pay += r["pay"]
    lines.append("")
    lines.append(f"Total: ${total_pay:,.2f}")

    body = "\n".join(lines)

    access_token = _get_access_token()
    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": addr}} for addr in recipients],
        },
        "saveToSentItems": "false",
    }
    resp = requests.post(
        SEND_MAIL_URL.format(sender=config.MS_SENDER_EMAIL),
        headers={"Authorization": f"Bearer {access_token}"},
        json=message,
        timeout=15,
    )
    resp.raise_for_status()
