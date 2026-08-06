#!/usr/bin/env python3
"""Applies ONLY the narrow class of fix this workflow is allowed to make
unattended: bumping a vulnerable dependency to the minimum version that
resolves a known CVE, and only when that's a patch or minor version bump
(never a major version, which is far more likely to break behavior a
static scan can't detect).

`pip-audit --fix --dry-run` writes a JSON "fix plan" describing what it
WOULD change; this script decides whether to actually apply it, then
rewrites requirements.txt by hand (never runs pip-audit --fix for real,
so there's one deterministic place that decides "is this safe").
"""
import argparse
import json
import re
import sys


def _version_tuple(v):
    return tuple(int(p) for p in re.findall(r"\d+", v)[:3]) or (0,)


def is_safe_bump(old_version, new_version):
    old = _version_tuple(old_version)
    new = _version_tuple(new_version)
    if not old or not new:
        return False
    # Never auto-apply a major version bump.
    return old[0] == new[0] and new > old


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix-plan", required=True)
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--out-flag", required=True)
    args = parser.parse_args()

    try:
        with open(args.fix_plan) as f:
            plan = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("No usable fix plan found - nothing to do.")
        _emit(args.out_flag, applied=False)
        return

    with open(args.requirements) as f:
        req_lines = f.readlines()

    applied = []
    skipped = []

    for dep in plan.get("dependencies", []):
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        name = dep["name"]
        current = dep["version"]

        # fix_versions lives per-vulnerability, not on the dependency itself -
        # a package can have several CVEs, each with its own minimum fix
        # version. If ANY of them has no fix_versions at all, pip-audit is
        # telling us that CVE has no patched release to bump to - a version
        # bump would leave the package labeled "fixed" while still carrying
        # that vulnerability, so the whole dependency is not eligible for
        # unattended auto-fix and needs a human to decide (mitigate, accept
        # risk, or replace the package).
        unfixable = [v["id"] for v in vulns if not v.get("fix_versions")]
        if unfixable:
            skipped.append(f"{name} {current}: no fix available for {', '.join(unfixable)} - needs human review")
            continue

        all_fix_versions = [fv for v in vulns for fv in v["fix_versions"]]
        target = max(all_fix_versions, key=_version_tuple)

        if not is_safe_bump(current, target):
            skipped.append(f"{name} {current} -> {target} (major version bump, needs human review)")
            continue

        pattern = re.compile(rf"^({re.escape(name)})==([^\s#]+)", re.IGNORECASE)
        changed_this_dep = False
        for i, line in enumerate(req_lines):
            m = pattern.match(line.strip())
            if m:
                req_lines[i] = re.sub(r"==[^\s#]+", f"=={target}", line)
                changed_this_dep = True
        if changed_this_dep:
            applied.append(f"{name} {current} -> {target}")
        else:
            skipped.append(f"{name} {current} -> {target} (pin not found in requirements.txt as a plain ==, needs manual check)")

    if applied:
        with open(args.requirements, "w") as f:
            f.writelines(req_lines)

    print(f"Applied {len(applied)} safe dependency patch(es):")
    for a in applied:
        print(f"  - {a}")
    print(f"Skipped {len(skipped)} (needs human review):")
    for s in skipped:
        print(f"  - {s}")

    _emit(args.out_flag, applied=bool(applied))


def _emit(path, applied):
    with open(path, "w") as f:
        f.write("true" if applied else "false")
    # Also surface to GitHub Actions step output.
    import os
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as f:
            f.write(f"applied={'true' if applied else 'false'}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
