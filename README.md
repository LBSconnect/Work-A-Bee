# Linton Timekeeping

A web app for employee/contractor clock in-out, with a payroll report
(hours x rate per person) emailed to you automatically every other
Friday at 2:00 PM Central.

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

## 1. Push this project to GitHub

1. Go to https://github.com/new and create a new **private** repository
   (e.g. `linton-timekeeping`).
2. Upload this entire folder's contents to that repository (drag-and-drop
   on GitHub's web UI works fine, or use `git push` if you're comfortable
   with Git).

## 2. Deploy to Render

1. Go to https://dashboard.render.com and sign up/log in (you can sign in
   with your GitHub account).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub account if prompted, then select the
   `linton-timekeeping` repo you just created.
4. Render reads `render.yaml` in this project and sets up two things
   automatically: the web app, and a free Postgres database connected
   to it.
5. Click **Apply** to deploy. First deploy takes a few minutes.

## 3. Fill in email settings

1. In the Render dashboard, open your **linton-timekeeping** web service.
2. Go to the **Environment** tab.
3. Fill in:
   - `SMTP_USERNAME` - your Outlook/Microsoft 365 email address
   - `SMTP_PASSWORD` - see note below
   - `REPORT_RECIPIENT` - where the report should be emailed
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
to wake itself up at 2pm, a free GitHub Actions workflow
(`.github/workflows/send-report.yml`, already included) pings the app
at the right time to trigger the report.

1. In Render, copy your app's URL (top of the service page, looks like
   `https://linton-timekeeping-xxxx.onrender.com`).
2. In Render's Environment tab, copy the value of `REPORT_TOKEN`
   (auto-generated when you deployed).
3. In GitHub, go to your repo -> **Settings** -> **Secrets and variables**
   -> **Actions** -> **New repository secret**, and add two secrets:
   - `APP_URL` = your Render app URL from step 1
   - `REPORT_TOKEN` = the value from step 2
4. That's it - the workflow will ping the app every Friday and it'll
   send the report automatically when it's actually a report Friday.

You can test it immediately: in GitHub, go to **Actions** -> "Send
biweekly payroll report" -> **Run workflow** to trigger it by hand.

## 5. Create your admin account

Visit your Render app URL. The first visit sends you to a setup page to
create your own admin username and password - there's no default
password to change later.

## 6. Add employees and contractors

1. Go to `<your-app-url>/admin/login` and log in.
2. Click **Employees -> + Add employee**.
3. Enter an Employee ID (e.g. `EMP001`), name, type (employee or
   contractor), hourly rate, and a PIN they'll use to clock in.

## 7. Daily use

Employees open `<your-app-url>` on any office computer (or bookmark it),
enter their Employee ID and PIN, then click the big CLOCK IN / CLOCK OUT
button.

## 8. Payroll reports

- **Automatic:** every other Friday around 2:00 PM Central, the report
  (hours x rate per person, plus a total) is emailed to
  `REPORT_RECIPIENT`.
- **Manual:** log in as admin and click **Send report now** any time.
- Pay periods run Monday through the second Friday, anchored to your
  July 3, 2026 pay date (`PAY_PERIOD_ANCHOR` in Render's Environment
  tab). You shouldn't need to change this unless your pay schedule
  itself shifts.

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
database and a `.env` file (copy `.env.example`).
