#!/usr/bin/env python3
"""Read-only crawl of the public, unauthenticated pages of the production
site for the weekly site-health workflow. Never submits a form, never logs
in, never mutates anything - GET/HEAD requests only.

Usage: site_health_crawl.py --base-url https://www.workabeez.net --out crawl.json
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# Public, unauthenticated routes worth checking every week. Kept in code
# (not discovered dynamically) so a compromised/misbehaving production
# server can't expand its own attack surface by injecting new "pages" for
# this script to crawl.
PUBLIC_ROUTES = [
    "/",
    "/pricing",
    "/privacy",
    "/terms",
    "/dpa",
    "/aup",
    "/security-policy",
    "/sla",
    "/faq",
    "/docs",
    "/staff/login",
    "/admin/login",
    "/signup",
    "/robots.txt",
    "/sitemap.xml",
    "/favicon.ico",
    "/static/style.css",
    "/static/logo-workabee.svg",
]


def check_url(url, timeout=15):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "workabeez-site-health-bot/1.0"})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed_ms = round((time.time() - start) * 1000)
            return {
                "url": url,
                "status": resp.status,
                "elapsed_ms": elapsed_ms,
                "ok": 200 <= resp.status < 400,
                "final_url": resp.geturl(),
            }
    except urllib.error.HTTPError as e:
        return {"url": url, "status": e.code, "elapsed_ms": round((time.time() - start) * 1000), "ok": False, "final_url": url}
    except Exception as e:
        return {"url": url, "status": None, "elapsed_ms": None, "ok": False, "error": str(e), "final_url": url}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    results = [check_url(base + path) for path in PUBLIC_ROUTES]

    broken = [r for r in results if not r["ok"]]
    summary = {
        "base_url": base,
        "checked": len(results),
        "broken": len(broken),
        "results": results,
    }

    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Crawled {len(results)} public routes on {base}: {len(broken)} broken.")
    for r in broken:
        print(f"  BROKEN: {r['url']} -> {r.get('status')} {r.get('error', '')}")

    sys.exit(1 if broken else 0)


if __name__ == "__main__":
    main()
