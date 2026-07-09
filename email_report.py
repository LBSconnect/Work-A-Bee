import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def send_report_email(period_start, period_end, rows):
    subject = (
        f"Payroll report: {period_start.strftime('%b %d, %Y')} - "
        f"{period_end.strftime('%b %d, %Y')}"
    )

    lines = [
        f"Payroll report for {period_start.strftime('%B %d, %Y')} - "
        f"{period_end.strftime('%B %d, %Y')}",
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
    lines.append(f"Total payroll: ${total_pay:,.2f}")

    body = "\n".join(lines)

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USERNAME
    msg["To"] = config.REPORT_RECIPIENT
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
        server.starttls()
        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.sendmail(config.SMTP_USERNAME, [config.REPORT_RECIPIENT], msg.as_string())
