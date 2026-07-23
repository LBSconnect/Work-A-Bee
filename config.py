import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

MS_TENANT_ID = os.environ.get("MS_TENANT_ID", "")
MS_CLIENT_ID = os.environ.get("MS_CLIENT_ID", "")
MS_CLIENT_SECRET = os.environ.get("MS_CLIENT_SECRET", "")
MS_SENDER_EMAIL = os.environ.get("MS_SENDER_EMAIL", "")

# Platform-wide transactional email (Postmark) for per-org notification emails -
# one shared sending account, not per-customer credentials like the MS Graph report above.
POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN", "")
NOTIFICATION_FROM_EMAIL = os.environ.get("NOTIFICATION_FROM_EMAIL", "")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER = os.environ.get("STRIPE_PRICE_STARTER", "")
STRIPE_PRICE_GROWTH = os.environ.get("STRIPE_PRICE_GROWTH", "")
STRIPE_PRICE_BUSINESS = os.environ.get("STRIPE_PRICE_BUSINESS", "")

ON_RENDER = os.environ.get("RENDER", "") != ""
