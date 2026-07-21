# Time Keeper

A web app for employee clock in/out, with an hours &amp; pay report
(hours x rate per person) an admin can email to themselves any time
from the dashboard.

Deployed on **Render** with a **Postgres** database, so it's reachable
from a browser on any office computer - no local install required.

---

## Hosting plan

- **Web service:** Starter plan - always on, no sleep/cold-start delay.
- **Database:** Basic-256mb Postgres - persistent, no expiration.

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
   under `envVars` in `render.yaml` (`SECRET_KEY` can be any long random
   string).

## 3. Fill in email settings

Email is sent via the Microsoft Graph API using an app registration
(OAuth), not SMTP/basic auth - this avoids Microsoft 365's Security
Defaults policy, which blocks basic auth entirely regardless of
per-mailbox settings.

1. In Microsoft Entra admin center, register an app, grant it
   **Microsoft Graph -> Application permission -> Mail.Send**, and
   grant admin consent. See the app registration steps documented
   separately (ask whoever set this up if you need to redo it).
2. In the Render dashboard, open your web service -> **Environment** tab.
3. Fill in:
   - `MS_TENANT_ID` - the app registration's Directory (tenant) ID
   - `MS_CLIENT_ID` - the app registration's Application (client) ID
   - `MS_CLIENT_SECRET` - a client secret value from that app registration
   - `MS_SENDER_EMAIL` - the mailbox address to send from
   - `REPORT_RECIPIENT` - already defaults to `info@lbsconnect.net`;
     only set this if you want it sent somewhere else.
4. Save changes (this triggers a quick redeploy).

## 4. Create your admin account

Visit your Render app URL. The first visit sends you to a setup page to
create your own admin username and password - there's no default
password to change later.

## 5. Add employees

1. Go to `<your-app-url>/admin/login` and log in.
2. Click **Employees -> + Add employee**.
3. Enter an Employee ID (e.g. `EMP001`), name, hourly rate (defaults to
   $16.00, editable per employee), and a PIN they'll use to clock in.

## 6. Daily use

Employees open `<your-app-url>` on any office computer (or bookmark it),
enter their Employee ID and PIN, then click the big CLOCK IN / CLOCK OUT
button.

## 7. Weekly hours reports

Log in as admin and click **Send report now** any time to email the
current week's hours to your configured report recipient.

## Security notes

- Employee PINs and the admin password are stored as one-way hashes,
  never in plain text.
- Render provides HTTPS automatically; the app marks its session cookie
  HTTPS-only.
- The clock-in and admin login forms are rate-limited to slow down
  anyone trying to guess a PIN or password.
- Because this app is now reachable from the internet (not just your
  office), keep PINs private the same way you would a debit card PIN,
  and don't share the admin password.
- Nothing in this app or its setup process will ever ask you to disable
  antivirus, unblock a script, or run anything as administrator.

## Local development (optional)

You don't need this for normal use - it's only for testing changes
before deploying. See `run.bat`; you'll need your own local Postgres
database and a `.env` file (copy `env.example`).
