# Time Keeper

A web app for employee clock in/out, with an hours &amp; pay report
(hours x rate per person, $16.00/hr by default) emailed automatically
every Friday at 5:00 PM Central to `antonette.Linton@lbsconnect.net`.

Deployed on **Render** (free tier to start) with a **Postgres** database,
so it's reachable from a browser on any office computer - no local
install required.

---

## Cost (free tier, as chosen)

- **Web service:** free. Sleeps after 15 minutes idle; wakes on the next
  request within about a minute. Fine for occasional admin/clock-in use.
- **Database:** free Postgres, but **it expires after 90 days** on the
  free plan. Put a reminder on your calendar for ~day 80 to either
  upgrade the database to a paid plan ($7/mo) or export/re-import your
  data before it's deleted.
- **Scheduled email:** $0 - handled by a free GitHub Actions workflow
  instead of Render's paid Cron Jobs, described below.

If reliability becomes more important than cost later, upgrading the web
service to Starter ($7/mo) removes the sleep delay, and upgrading the
database removes the 90-day expiration.

## 1. This project on GitHub

This code already lives in a private GitHub repository
(`LBSconnect/Time-Keeper`) - nothing to do here unless you're starting a
brand-new copy, in which case create a private repo at
https://github.com/new and push/upload this folder's contents to it.

## 2. Deploy to Render

**Recommended - Blueprint (sets everything up automatically):**

1. Go to https://dashboard.render.com and sign up/log in (you can sign in
   with your GitHub account).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub account if prompted, then select this repo.
4. Render reads `render.yaml` in this project and sets up two things
   automatically: the web app, and a free Postgres database connected
   to it.
5. Click **Apply** to deploy. First deploy takes a few minutes.

**If you already created the web service manually** (e.g. via **New +**
-> **Web Service** instead of Blueprint, like `time-keeper-tnb8.onrender.com`),
Render won't have wired up the database or env vars for you. You'll need to:

1. **New +** -> **PostgreSQL** to create a free database, then in your web
   service's **Environment** tab set `DATABASE_URL` to that database's
   "Internal Connection String" (from the database's Info page).
2. In the same **Environment** tab, add the rest of the variables listed
   under `envVars` in `render.yaml` (`SECRET_KEY` and `REPORT_TOKEN` can be
   any long random strings).

## 3. Fill in email settings

1. In the Render dashboard, open your web service.
2. Go to the **Environment** tab.
3. Fill in:
   - `SMTP_USERNAME` - your Outlook/Microsoft 365 email address
   - `SMTP_PASSWORD` - see note below
   - `REPORT_RECIPIENT` - already defaults to `antonette.Linton@lbsconnect.net`;
     only set this if you want it sent somewhere else.
4. Save changes (this triggers a quick redeploy).

**About the password:** if your Microsoft 365/Outlook account has
multi-factor authentication on (most business accounts do), your normal
password won't work for SMTP. Generate an **app password** instead at
https://account.microsoft.com/security under "App passwords," and use
that as `SMTP_PASSWORD`. If your organization has SMTP AUTH disabled
entirely, a Microsoft 365 admin needs to enable it for your mailbox, or
you can point `SMTP_SERVER`/`SMTP_PORT`/credentials at a different
provider like Gmail instead.

## 4. Set up the free scheduled email trigger

Render's free web service sleeps when idle, so instead of relying on it
to wake itself up at 5pm, a free GitHub Actions workflow
(`.github/workflows/send-report.yml`, already included) pings the app
at the right time to trigger the report.

1. In Render, copy your app's URL (top of the service page) - e.g.
   `https://time-keeper-tnb8.onrender.com`.
2. In Render's Environment tab, copy the value of `REPORT_TOKEN`
   (auto-generated when you deployed).
3. In GitHub, go to your repo -> **Settings** -> **Secrets and variables**
   -> **Actions** -> **New repository secret**, and add two secrets:
   - `APP_URL` = your Render app URL from step 1
   - `REPORT_TOKEN` = the value from step 2
4. That's it - the workflow will ping the app every Friday and it'll
   send the report automatically at 5pm Central.

You can test it immediately: in GitHub, go to **Actions** -> "Send
weekly hours report" -> **Run workflow** to trigger it by hand.

## 5. Create your admin account

Visit your Render app URL. The first visit sends you to a setup page to
create your own admin username and password - there's no default
password to change later.

## 6. Add employees

1. Go to `<your-app-url>/admin/login` and log in.
2. Click **Employees -> + Add employee**.
3. Enter an Employee ID (e.g. `EMP001`), name, hourly rate (defaults to
   $16.00, editable per employee), and a PIN they'll use to clock in.

## 7. Daily use

Employees open `<your-app-url>` on any office computer (or bookmark it),
enter their Employee ID and PIN, then click the big CLOCK IN / CLOCK OUT
button.

## 8. Weekly hours reports

- **Automatic:** every Friday around 5:00 PM Central, a report (hours x
  rate per person, plus a total) covering that Monday-Friday is emailed
  to `REPORT_RECIPIENT` (`antonette.Linton@lbsconnect.net` by default).
- **Manual:** log in as admin and click **Send report now** any time.

## Security notes

- Employee PINs and the admin password are stored as one-way hashes,
  never in plain text.
- Render provides HTTPS automatically; the app marks its session cookie
  HTTPS-only.
- The clock-in and admin login forms are rate-limited to slow down
  anyone trying to guess a PIN or password.
- The `/cron/send-report` endpoint requires a secret token - without it,
  requests are rejected.
- Because this app is now reachable from the internet (not just your
  office), keep PINs private the same way you would a debit card PIN,
  and don't share the admin password.
- Nothing in this app or its setup process will ever ask you to disable
  antivirus, unblock a script, or run anything as administrator.

## Local development (optional)

You don't need this for normal use - it's only for testing changes
before deploying. See `run.bat`; you'll need your own local Postgres
database and a `.env` file (copy `env.example`).
