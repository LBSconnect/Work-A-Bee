import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.office365.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
REPORT_RECIPIENT = os.environ.get("REPORT_RECIPIENT", "") or SMTP_USERNAME

_default_anchor = "2026-07-03"
_anchor_str = os.environ.get("PAY_PERIOD_ANCHOR", _default_anchor)
PAY_PERIOD_ANCHOR = date.fromisoformat(_anchor_str)

REPORT_HOUR = int(os.environ.get("REPORT_HOUR", "14"))
REPORT_MINUTE = int(os.environ.get("REPORT_MINUTE", "0"))

REPORT_TOKEN = os.environ.get("REPORT_TOKEN", "")

ON_RENDER = os.environ.get("RENDER", "") != ""
