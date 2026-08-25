#!/usr/bin/env python3
"""Post-deploy validation of the live recipe site (recipe.geekway.dev).

Fetches the LIVE site and verifies:
  1. index.html responds 200 and (if EXPECTED is set) lists exactly the
     expected recipe URLs (recipes/<slug>/<slug>.html)
  2. every recipe page responds 200, has a <title>, the canonical .page
     block and a print media rule
  3. every photo referenced in a recipe gallery responds 200
  4. the pages are real content, not 404s or error pages

Usage:
    python3 scripts/verify_live_site.py                  # recipe.geekway.dev
    python3 scripts/verify_live_site.py --summary /tmp/verify-summary.md  # markdown report
    LIVE_SITE=https://example.com python3 scripts/verify_live_site.py
    EXPECTED="recipes/a/a.html recipes/b/b.html" python3 ...   # strict index compare
    RETRIES=6 RETRY_DELAY=30 python3 ...                 # tolerate Pages deploy lag

Exit 0 = all good, 1 = failures. Prints a per-URL report.
"""

import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

BASE = os.environ.get("LIVE_SITE", "https://recipe.geekway.dev").rstrip("/")
RETRIES = int(os.environ.get("RETRIES", "6"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "30"))
EXPECTED = [u for u in os.environ.get("EXPECTED", "").split() if u.strip()]
UA = {"User-Agent": "family-recipes-verify/1.0"}

SUMMARY_FILE = None
if "--summary" in sys.argv:
    _idx = sys.argv.index("--summary")
    if _idx + 1 < len(sys.argv):
        SUMMARY_FILE = sys.argv[_idx + 1]


def fetch(url, timeout=30):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def check_page(url, min_content=None):
    """Returns (ok, detail). Verifies the URL serves real recipe content."""
    try:
        status, html = fetch(url)
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, f"unreachable ({e})"
    if status != 200:
        return False, f"HTTP {status}"
    if min_content is None:
        return True, "200 OK"
    missing = [m for m in min_content if m not in html]
    if missing:
        return False, f"200 but missing markers: {', '.join(missing)}"
    return True, "200 OK, content markers present"


def validate_once():
    """Returns (errors, rows) where rows = [(label, ok, detail)] for the summary."""
    errors = []
    rows = []
    # ---- index ----
    ok, detail = check_page(f"{BASE}/index.html")
    rows.append(("index.html", ok, detail))
    print(f"  index.html          : {detail}")
    if not ok:
        return [f"{BASE}/index.html — {detail}"], rows
    try:
        _, index_html = fetch(f"{BASE}/index.html")
    except Exception as e:
        return [f"{BASE}/index.html — cannot re-read ({e})"], rows
    live_links = re.findall(r'href="(recipes/[^"]+\.html)"', index_html)
    live_links = sorted(set(live_links))
    if EXPECTED:
        exp = sorted(set(EXPECTED))
        if live_links != exp:
            errors.append(f"index lists {len(live_links)} recipes, expected {len(exp)}: "
                          f"missing={sorted(set(exp) - set(live_links)) or 'none'} "
                          f"extra={sorted(set(live_links) - set(exp)) or 'none'}")
    elif not live_links:
        errors.append("index.html lists no recipe links")
    # ---- recipe pages + photos ----
    for link in live_links:
        url = f"{BASE}/{link}"
        ok, detail = check_page(url, min_content=["<title>", 'class="page"', "@media print"])
        rows.append((link, ok, detail))
        print(f"  {link:46s}: {detail}")
        if not ok:
            errors.append(f"{url} — {detail}")
            continue
        try:
            _, html = fetch(url)
        except Exception as e:
            errors.append(f"{url} — cannot re-read ({e})")
            continue
        for src in re.findall(r'src="(photos/[^"]+)"', html):
            # stdlib urljoin resolves relative to the page URL directory,
            # e.g. .../recipes/a/a.html + photos/p.jpg -> .../recipes/a/photos/p.jpg
            photo_url = urljoin(url, src)
            ok, detail = check_page(photo_url)
            rows.append((f"{link} → {src}", ok, detail))
            print(f"    {src:40s}: {detail}")
            if not ok:
                errors.append(f"{photo_url} — {detail}")
    return errors, rows


def write_summary(rows, errors, passed, attempt):
    if not SUMMARY_FILE:
        return
    verdict = "✅ PASS" if passed else "❌ FAIL"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"## 🌐 Live Site Post-Deploy Check — {verdict}", ""]
    lines.append(f"**Site:** {BASE} · **Checked at:** {now} · "
                 f"**Attempts used:** {attempt}/{RETRIES}")
    lines.append("")
    lines.append("| Check | Result |")
    lines.append("|---|---|")
    for label, ok, detail in rows:
        mark = "✅" if ok else "❌"
        safe = (detail or "").replace("|", "\\|")
        lines.append(f"| {label} | {mark} {safe} |")
    if errors:
        lines.append("")
        lines.append(f"**Issues ({len(errors)}):**")
        lines.extend(f"- {e}" for e in errors)
        lines.append("")
        lines.append("Fix goes back via a patch PR → quality gate → merge → re-validate.")
    try:
        Path(SUMMARY_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"summary written: {SUMMARY_FILE}")
    except OSError as e:
        print(f"cannot write summary: {e}")


def main():
    print(f"Live site validation — {BASE}")
    print("=" * 56)
    errors = []
    rows = []
    attempt = 1
    for attempt in range(1, RETRIES + 1):
        print(f"Attempt {attempt}/{RETRIES}")
        errors, rows = validate_once()
        if not errors:
            break
        print("=" * 56)
        print(f"{len(errors)} issue(s) on attempt {attempt}:")
        for e in errors:
            print(f"  \u2717 {e}")
        if attempt < RETRIES:
            print(f"Retrying in {RETRY_DELAY}s (Pages deploys can lag ~3 min)...")
            time.sleep(RETRY_DELAY)
    print("=" * 56)
    passed = not errors
    if passed:
        print("LIVE SITE OK")
    else:
        print(f"FAIL — validation still failing after {RETRIES} attempts")
    write_summary(rows, errors, passed, attempt)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
