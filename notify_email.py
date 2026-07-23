import traceback

import requests

import config

POSTMARK_API_URL = "https://api.postmarkapp.com/email"


def email_configured():
    return bool(config.POSTMARK_SERVER_TOKEN and config.NOTIFICATION_FROM_EMAIL)


def send_email(to_address, subject, text_body):
    """Best-effort transactional email for one recipient. Never raises -
    a missing Postmark configuration or a delivery failure must not break
    the in-app action (message sent, PTO decided, shift claimed, ...) that
    triggered it.
    """
    if not to_address or not email_configured():
        return False
    try:
        resp = requests.post(
            POSTMARK_API_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": config.POSTMARK_SERVER_TOKEN,
            },
            json={
                "From": config.NOTIFICATION_FROM_EMAIL,
                "To": to_address,
                "Subject": subject,
                "TextBody": text_body,
                "MessageStream": "outbound",
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception:
        print(f"WARNING: notification email to {to_address} failed to send. Traceback:")
        traceback.print_exc()
        return False
