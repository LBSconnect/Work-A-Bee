#!/usr/bin/env python3
"""Builds the dated weekly site-health report (report.md + summary.json),
comparing against the most recent previous run under reports/site-health/
to classify defects as new / recurring / fixed.
"""
import argparse
import glob
import json
import os
from datetime import datetime, timezone


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def find_previous_summary(report_root, current_date):
    candidates = sorted(
        d for d in glob.glob(os.path.join(report_root, "*"))
        if os.path.isdir(d) and os.path.basename(d) < current_date
    )
    if not candidates:
        return None
    return _load_json(os.path.join(candidates[-1], "summary.json"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-date", required=True)
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--production-url", required=True)
    parser.add_argument("--flake8-exit", default="")
    parser.add_argument("--pytest-exit", default="")
    parser.add_argument("--crawl-exit", default="")
    parser.add_argument("--dep-fix-applied", default="false")
    parser.add_argument("--dep-fix-retest-exit", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)
    report_root = os.path.dirname(out_dir.rstrip("/"))

    crawl = _load_json(os.path.join(out_dir, "crawl.json"), {})
    pip_audit_before = _load_json(os.path.join(out_dir, "pip-audit-before.json"), {})
    bandit = _load_json(os.path.join(out_dir, "bandit.json"), {})

    broken_links = [r["url"] for r in crawl.get("results", []) if not r.get("ok")]
    vulnerable_deps = [d["name"] for d in pip_audit_before.get("dependencies", []) if d.get("vulns")]
    bandit_findings = len(bandit.get("results", []))

    previous = find_previous_summary(report_root, args.report_date) or {}
    prev_broken = set(previous.get("broken_links", []))
    prev_vulnerable = set(previous.get("vulnerable_deps", []))

    new_broken = sorted(set(broken_links) - prev_broken)
    fixed_broken = sorted(prev_broken - set(broken_links))
    new_vulnerable = sorted(set(vulnerable_deps) - prev_vulnerable)
    fixed_vulnerable = sorted(prev_vulnerable - set(vulnerable_deps))

    tests_ok = args.pytest_exit == "0"
    lint_ok = args.flake8_exit == "0"
    crawl_ok = args.crawl_exit == "0"
    dep_fix_applied = args.dep_fix_applied == "true"
    dep_fix_retest_ok = args.dep_fix_retest_exit == "0" if dep_fix_applied else None

    overall_status = "HEALTHY"
    if not tests_ok or not lint_ok:
        overall_status = "BUILD/TEST FAILURE"
    elif broken_links or vulnerable_deps:
        overall_status = "ISSUES FOUND"

    summary = {
        "report_date": args.report_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit_tested": args.baseline_commit,
        "production_url": args.production_url,
        "overall_status": overall_status,
        "tests_passed": tests_ok,
        "lint_passed": lint_ok,
        "crawl_passed": crawl_ok,
        "broken_links": broken_links,
        "vulnerable_deps": vulnerable_deps,
        "bandit_findings_count": bandit_findings,
        "dependency_fix_applied": dep_fix_applied,
        "dependency_fix_retest_passed": dep_fix_retest_ok,
    }
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    lines = [
        f"# Weekly Site Health Report - {args.report_date}",
        "",
        f"**Overall status:** {overall_status}",
        f"**Production URL tested:** {args.production_url}",
        f"**Commit tested:** `{args.baseline_commit}`",
        f"**Generated:** {summary['generated_at']}",
        "",
        "## Build & test",
        f"- Lint (flake8 E9/F): {'PASS' if lint_ok else 'FAIL'}",
        f"- Test suite: {'PASS' if tests_ok else 'FAIL'}",
        f"- Production crawl ({len(crawl.get('results', []))} public routes checked): "
        f"{'PASS' if crawl_ok else f'FAIL - {len(broken_links)} broken'}",
        "",
        "## Broken links",
    ]
    if broken_links:
        lines += [f"- {u}" for u in broken_links]
    else:
        lines.append("None found.")
    if new_broken:
        lines.append("")
        lines.append(f"**New this week:** {', '.join(new_broken)}")
    if fixed_broken:
        lines.append(f"**Fixed since last week:** {', '.join(fixed_broken)}")

    lines += [
        "",
        "## Dependency security",
        f"- Vulnerable packages found: {', '.join(vulnerable_deps) if vulnerable_deps else 'None'}",
    ]
    if dep_fix_applied:
        lines.append(
            f"- Auto-fix applied to `requirements.txt` and full test suite re-run: "
            f"{'PASSED - safe to auto-merge' if dep_fix_retest_ok else 'FAILED - reverted, needs human review'}"
        )
    if new_vulnerable:
        lines.append(f"- **New this week:** {', '.join(new_vulnerable)}")
    if fixed_vulnerable:
        lines.append(f"- **Resolved since last week:** {', '.join(fixed_vulnerable)}")

    lines += [
        "",
        "## Security lint (bandit, medium+ severity/confidence)",
        f"- {bandit_findings} finding(s) - see `bandit.json` artifact for detail. Not auto-fixed (needs judgment).",
        "",
        "## Recommended human actions",
    ]
    actions = []
    if not tests_ok or not lint_ok:
        actions.append("Investigate the build/test failure before anything else merges.")
    if new_broken:
        actions.append(f"Fix newly broken link(s): {', '.join(new_broken)}")
    if vulnerable_deps and not dep_fix_applied:
        actions.append("Review dependency vulnerabilities - no safe automatic patch was available this week.")
    if bandit_findings:
        actions.append("Review the bandit security findings artifact.")
    if not actions:
        actions.append("None - site is healthy.")
    lines += [f"- {a}" for a in actions]

    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Report written to {out_dir}/report.md (status: {overall_status})")


if __name__ == "__main__":
    main()
