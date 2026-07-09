# For LOCAL DEVELOPMENT ONLY. On Render, these are set in the dashboard
# (most are wired up automatically by render.yaml) - you don't need this
# file there. Copy this to ".env" only if you want to run the app on your
# own machine against a local/test Postgres database.

SECRET_KEY=change-this-to-a-random-string

# A Postgres connection string. Render's Blueprint sets this for you in
# production; for local dev you'd need your own Postgres instance.
DATABASE_URL=postgresql://user:password@localhost:5432/linton_timekeeping

# --- Outlook / Microsoft 365 SMTP settings ---
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your-email@yourcompany.com
SMTP_PASSWORD=your-app-password-here
REPORT_RECIPIENT=sean006@gmail.com

# The last known report Friday - every 14 days from this date is another
# report Friday.
PAY_PERIOD_ANCHOR=2026-07-03

# Shared secret for the /cron/send-report endpoint - must match the
# REPORT_TOKEN secret in your GitHub Actions workflow.
REPORT_TOKEN=change-this-to-a-random-string-too
