import os
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

# Shared cron-ingress secret authenticating "this is the scheduled report
# ping," not "which org" - per-org schedule/recipients live on the
# organizations table (see orgs.py / migrate_to_multitenant.py).
REPORT_TOKEN = os.environ.get("REPORT_TOKEN", "")

ON_RENDER = os.environ.get("RENDER", "") != ""
