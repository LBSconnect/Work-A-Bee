import os
from dotenv import load_dotenv

load_dotenv()

_DEV_SECRET_KEY = "dev-only-change-me"
SECRET_KEY = os.environ.get("SECRET_KEY", _DEV_SECRET_KEY)

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

# Optional. Expo's push API (notify_push.py) works with zero server-side
# credentials by default - this only opts the project into Expo's "Enhanced
# Security" push mode, which requires every send request to carry it. Get one
# from https://expo.dev/accounts/[account]/settings/access-tokens. Unrelated
# to the EXPO_TOKEN secret used by .github/workflows/eas-build.yml, which
# authenticates the `eas` CLI (builds), not push sends - the two are
# different Expo credentials for different purposes.
EXPO_ACCESS_TOKEN = os.environ.get("EXPO_ACCESS_TOKEN", "")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER = os.environ.get("STRIPE_PRICE_STARTER", "")
STRIPE_PRICE_GROWTH = os.environ.get("STRIPE_PRICE_GROWTH", "")
STRIPE_PRICE_BUSINESS = os.environ.get("STRIPE_PRICE_BUSINESS", "")

ON_RENDER = os.environ.get("RENDER", "") != ""

# SECRET_KEY signs both Flask session cookies and the mobile API's JWT access
# tokens (see api/auth.py). Falling back to a well-known default is fine for
# local dev, but would be a critical vulnerability if it ever happened on a
# real deployment (Render already auto-generates a real value via render.yaml's
# `generateValue: true` - this is a fail-loud backstop in case that ever
# regresses, rather than silently running insecurely).
if ON_RENDER and SECRET_KEY == _DEV_SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not set (or still the dev default) in a deployed environment. "
        "Refusing to start - set a real SECRET_KEY in Render's environment."
    )

# One-time bootstrap for the first platform-wide system admin account (cross-tenant
# access, gates /system and /internal). Only takes effect if the system_admins table
# is still empty - see models.ensure_system_admin_bootstrap(). Set these in Render's
# environment (sync: false, like the Stripe keys below), never commit real values here.
SYSTEM_ADMIN_BOOTSTRAP_USERNAME = os.environ.get("SYSTEM_ADMIN_BOOTSTRAP_USERNAME", "")
SYSTEM_ADMIN_BOOTSTRAP_PASSWORD = os.environ.get("SYSTEM_ADMIN_BOOTSTRAP_PASSWORD", "")

# Emergency setup token for /system/setup - a browser-based alternative to running
# create_system_admin.py from a shell. The route is a 404 unless this is set, and
# should be unset again in Render once it's no longer needed. See app.py.
SYSTEM_SETUP_TOKEN = os.environ.get("SYSTEM_SETUP_TOKEN", "")

# Set to disable the in-process weekly-report scheduler (see scheduled_reports.py
# and app.py) - useful for local scripts/tests that import app.py repeatedly and
# don't want a background thread left running.
DISABLE_BACKGROUND_SCHEDULER = os.environ.get("DISABLE_BACKGROUND_SCHEDULER", "") != ""
