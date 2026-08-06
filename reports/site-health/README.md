# Weekly Site Health Reports

Generated automatically by `.github/workflows/weekly-site-health.yml`, which
runs every Friday at 12:00 AM `America/Chicago` (DST-adjusted - see the
comment at the top of that workflow file for how).

Each run creates a dated folder here: `YYYY-MM-DD/`, containing:

- `report.md` - human-readable summary (also used as the pull request body)
- `summary.json` - machine-readable baseline the *next* week's run reads to
  classify defects as new / recurring / fixed
- `crawl.json` - raw read-only production crawl results
- `pip-audit-before.json` - dependency vulnerability scan before any fix
- `bandit.json` - static security lint findings

No secrets, credentials, or customer data are ever written here - if you
add checks to the workflow, keep it that way.
