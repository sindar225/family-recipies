#!/usr/bin/env python3
"""Quality gate for the family-recipes repository.

Validates six things:
  1. Directory structure: recipes live under recipes/<slug>/<slug>.html,
     photos under recipes/<slug>/photos/photo-N.<ext>, nothing stray.
  2. Design system: every recipe follows the canonical template (CSS
     variables, A4 page, print rules, canonical blocks, no legacy layout).
  3. Gallery integrity: gallery block present iff photos exist, the print
     rule hides it, every photo is referenced, no <img> in the page flow.
  4. Index consistency: index.html lists every recipe exactly once, every
     link resolves, and link titles match the recipe <title>.
  5. Photo privacy: no EXIF/GPS metadata in photos (the repo is public).
  6. PR body format: PRs touching recipes/index.html must contain
     Motivation / Changes / Risks / Testing sections; a PR adding a new
     recipe must have a title starting with "Add recipe: ".

Exit code 0 = pass, 1 = fail. Run from the repository root:
    python3 scripts/quality_gate.py
    python3 scripts/quality_gate.py --summary /tmp/gate-summary.md   # write a markdown report
On a pull request, pass PR context via environment variables:
    PR_BODY        — the PR description
    PR_TITLE       — the PR title
    PR_NUMBER      — the PR number (optional, shown in the summary)
    CHANGED_STATUS — output of `git diff --name-status origin/main...HEAD`
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECIPES = ROOT / "recipes"
INDEX = ROOT / "index.html"

SUMMARY_FILE = None
if "--summary" in sys.argv:
    _idx = sys.argv.index("--summary")
    if _idx + 1 < len(sys.argv):
        SUMMARY_FILE = sys.argv[_idx + 1]

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PHOTO_RE = re.compile(r"^photo-\d+\.(jpe?g|png|webp)$")
REQUIRED_VARS = ("--paper", "--green", "--red", "--line")
CANONICAL_MARKERS = ('class="page"', 'class="kicker"', 'class="stats"')
LEGACY_MARKERS = ('class="hero"', 'class="badges"')
PRINT_HIDE_RULE = ".gallery-modal, .gallery-btn { display: none !important; }"
PR_SECTIONS = ("## Motivation", "## Changes", "## Risks", "## Testing")

CURRENT_AREA = "General"
errors = []      # (area, message)
warnings = []    # (area, message)


def set_area(name):
    global CURRENT_AREA
    CURRENT_AREA = name


def fail(msg):
    errors.append((CURRENT_AREA, msg))


def warn(msg):
    warnings.append((CURRENT_AREA, msg))


def rel(p):
    return p.relative_to(ROOT).as_posix()


# ---------------------------------------------------------------- structure

def check_root_layout():
    allowed = {"index.html", "README.md", "CONTRIBUTING.md", "CNAME",
               "recipes", "scripts", ".github", ".gitignore"}
    for p in sorted(ROOT.iterdir()):
        if p.name.startswith(".") or p.name in allowed or p.name.startswith("LICENSE"):
            continue
        fail(f"unexpected top-level entry: {p.name} (allowed: "
             f"{', '.join(sorted(allowed - {'.github', '.gitignore'}))})")
    for p in sorted(ROOT.glob("*.html")):
        if p.name != "index.html":
            fail(f"HTML file outside recipes/: {rel(p)} (only index.html lives at root)")


def check_recipe_dirs():
    if not RECIPES.is_dir():
        fail("missing required directory: recipes/")
        return []
    for p in sorted(RECIPES.iterdir()):
        if p.is_file() and not p.name.startswith("."):
            fail(f"stray file in recipes/: {rel(p)} (each recipe must be its own directory)")
    dirs = sorted(p for p in RECIPES.iterdir() if p.is_dir() and not p.name.startswith("."))
    for d in dirs:
        if not SLUG_RE.match(d.name):
            fail(f"recipe dir '{d.name}' violates slug convention "
                 f"(lowercase letters/digits, hyphens only, e.g. 'chicken-paprikash')")
    return dirs


def check_recipe_contents(d):
    """Returns the list of photo files in the recipe dir (may be empty)."""
    slug = d.name
    html = d / f"{slug}.html"
    if not html.is_file():
        fail(f"{rel(d)}: missing {slug}.html (file name must match directory slug)")
    for p in sorted(d.iterdir()):
        if p.name.startswith("."):
            continue
        if p.is_file() and p.name == f"{slug}.html":
            continue
        if p.is_dir() and p.name == "photos":
            continue
        fail(f"{rel(d)}: unexpected entry {p.name} (allowed: {slug}.html, photos/)")
    photos = d / "photos"
    if not photos.is_dir():
        return []
    for p in sorted(photos.iterdir()):
        if p.name.startswith("."):
            continue
        if not PHOTO_RE.match(p.name):
            fail(f"{rel(p)}: photo name must match photo-N.jpg/.jpeg/.png/.webp "
                 f"(lowercase, no spaces)")
    return [p for p in sorted(photos.iterdir()) if p.is_file() and not p.name.startswith(".")]


# ---------------------------------------------------------------- design

def check_design(html_path):
    text = html_path.read_text(encoding="utf-8")
    relp = rel(html_path)
    m = re.search(r"<title>\s*([^<]+?)\s*</title>", text)
    if not m or not m.group(1).strip():
        fail(f"{relp}: missing or empty <title> (the index uses it for navigation)")
    title = m.group(1).strip() if m else ""
    if ":root" not in text:
        fail(f"{relp}: missing :root with design tokens")
    else:
        missing = [v for v in REQUIRED_VARS if v not in text]
        if missing:
            fail(f"{relp}: design tokens missing: {', '.join(missing)}")
    if not re.search(r"@page\s*\{[^}]*size\s*:\s*A4", text):
        fail(f"{relp}: missing @page {{ size: A4 }} print rule")
    if not _page_print_rule_ok(text):
        fail(f"{relp}: missing @media print rule resetting .page margins "
             f"(required: @media print{{... .page{{margin:0;box-shadow:none}}}})")
    for marker in CANONICAL_MARKERS:
        if marker not in text:
            fail(f"{relp}: missing canonical block {marker}")
    for marker in LEGACY_MARKERS:
        if marker in text:
            fail(f"{relp}: legacy layout detected ({marker}) — use the pileca-lava template")
    return text, title


def _page_print_rule_ok(text):
    """True if some @media print block resets the .page margins for printing."""
    for m in re.finditer(r"@media\s+print", text):
        seg = text[m.start():m.start() + 300]
        if re.search(r"\.page\s*\{margin\s*:\s*0", seg):
            return True
    return False


def check_gallery(html_path, text, photos):
    relp = rel(html_path)
    start = text.find("<!-- GALLERY_START -->")
    end = text.find("<!-- GALLERY_END -->")
    has_markers = start != -1 and end != -1 and end > start
    has_btn = '<button class="gallery-btn"' in text
    if photos:
        if not has_markers:
            fail(f"{relp}: photos exist but gallery block (GALLERY_START/END) is missing")
        if not has_btn:
            fail(f"{relp}: photos exist but gallery button is missing")
        if PRINT_HIDE_RULE not in text:
            fail(f"{relp}: print rule must hide the gallery: {PRINT_HIDE_RULE}")
        srcs = re.findall(r'<img class="gallery-slide" src="([^"]+)"', text)
        expected = {f"photos/{p.name}" for p in photos}
        actual = set(srcs)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            if missing:
                fail(f"{relp}: photos not referenced in gallery: {', '.join(missing)}")
            if extra:
                fail(f"{relp}: gallery references missing files: {', '.join(extra)}")
        for m in re.finditer(r"<img\b", text):
            if not (start <= m.start() < end):
                fail(f"{relp}: <img> outside the gallery block "
                     f"(images must live in the modal only)")
                break
    else:
        if has_markers or has_btn:
            fail(f"{relp}: gallery block/button present but no photos/ directory")


def check_photos(photos):
    try:
        import piexif
    except ImportError:
        warn("piexif not installed — EXIF/GPS check skipped")
        return
    for p in photos:
        if p.suffix.lower() not in (".jpg", ".jpeg"):
            continue
        try:
            ex = piexif.load(str(p))
        except Exception as e:
            fail(f"{rel(p)}: cannot parse EXIF ({e})")
            continue
        if ex.get("GPS"):
            fail(f"{rel(p)}: GPS metadata present — strip it (public repo)")
        dirty = [k for k, v in ex.items() if k != "thumbnail" and v]
        if dirty:
            fail(f"{rel(p)}: EXIF metadata present ({', '.join(dirty)}) "
                 f"— strip it (public repo)")


# ---------------------------------------------------------------- index

def check_index(dirs, titles):
    if not INDEX.is_file():
        fail("missing index.html")
        return
    text = INDEX.read_text(encoding="utf-8")
    start = text.find("<!-- RECIPE_LINKS_START -->")
    end = text.find("<!-- RECIPE_LINKS_END -->")
    if start == -1 or end == -1 or end < start:
        fail("index.html: missing RECIPE_LINKS_START/END markers")
        return
    block = text[start:end]
    hrefs = re.findall(r'<a href="([^"]+)" class="recipe-link">', block)
    strongs = [re.sub(r"\s+", " ", s).strip()
               for s in re.findall(r"<strong>(.*?)</strong>", block, re.S)]
    expected = {f"recipes/{d.name}/{d.name}.html" for d in dirs}
    actual = set(hrefs)
    for h in sorted(actual - expected):
        fail(f"index.html: link points outside recipe set: {h}")
    for h in sorted(expected - actual):
        fail(f"index.html: recipe missing from navigation: {h}")
    if len(hrefs) != len(set(hrefs)):
        fail("index.html: duplicate recipe links")
    if len(strongs) != len(hrefs):
        fail("index.html: link markup mismatch (each link needs exactly one <strong>)")
        return
    for href, strong in zip(hrefs, strongs):
        target = ROOT / href
        if not target.is_file():
            fail(f"index.html: broken link {href}")
            continue
        slug = href.split("/")[1]
        t = titles.get(slug)
        if t and t != strong:
            fail(f"index.html: link title '{strong}' does not match "
                 f"<title> '{t}' of {href}")


# ---------------------------------------------------------------- PR format

def check_pr():
    body = os.environ.get("PR_BODY", "")
    status = os.environ.get("CHANGED_STATUS", "")
    title = os.environ.get("PR_TITLE", "")
    if not body or not status:
        return  # push or manual run — no PR context
    lines = [ln for ln in status.splitlines() if ln.strip()]
    relevant = any(re.search(r"(^|\t)(recipes/|index\.html)", ln) for ln in lines)
    if not relevant:
        return
    norm = re.sub(r"\r\n?", "\n", body)
    for sec in PR_SECTIONS:
        if sec not in norm:
            fail(f"PR body missing required section: {sec}")
    for sec in PR_SECTIONS:
        m = re.search(re.escape(sec) + r"\s*\n(.*?)(?=\n## |\Z)", norm, re.S)
        if m is None or not m.group(1).strip():
            fail(f"PR body section '{sec}' is empty")
    added = [ln.split("\t", 1)[1].strip() for ln in lines
             if ln.startswith("A") and "\t" in ln
             and re.search(r"recipes/[^/]+/[^/]+\.html", ln)]
    if added and not title.startswith("Add recipe: "):
        fail(f"PR adds a new recipe ({added[0]}) — title must start with 'Add recipe: '")


# ---------------------------------------------------------------- summary

AREAS = ("Directory structure", "Recipe contents & naming", "Design system",
         "Gallery integrity", "Photo privacy", "Index consistency", "PR format")


def write_summary(passed, n_recipes):
    if not SUMMARY_FILE:
        return
    verdict = "✅ PASS" if passed else "❌ FAIL"
    lines = [f"## 🛡️ Quality Gate — {verdict}", ""]
    meta = f"**Recipes validated:** {n_recipes}"
    pr_num = os.environ.get("PR_NUMBER", "")
    if pr_num:
        meta += f" · **PR:** #{pr_num}"
        if os.environ.get("PR_TITLE"):
            meta += f" — {os.environ['PR_TITLE']}"
    lines.append(meta)
    lines.append("")
    lines.append("| Check area | Status |")
    lines.append("|---|---|")
    for area in AREAS:
        errs = [m for a, m in errors if a == area]
        warns = [m for a, m in warnings if a == area]
        status = "❌" if errs else ("⚠️" if warns else "✅")
        lines.append(f"| {area} | {status} |")
    if errors:
        lines.append("")
        lines.append(f"**Errors ({len(errors)}):**")
        lines.extend(f"- {m}" for _, m in errors)
    if warnings:
        lines.append("")
        lines.append(f"**Warnings ({len(warnings)}):**")
        lines.extend(f"- {m}" for _, m in warnings)
    lines.append("")
    lines.append("See the job log for the full console report.")
    try:
        Path(SUMMARY_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"summary written: {SUMMARY_FILE}")
    except OSError as e:
        print(f"cannot write summary: {e}")


# ---------------------------------------------------------------- main

def main():
    print("Quality gate — family-recipes")
    print("=" * 40)
    set_area("Directory structure")
    check_root_layout()
    dirs = check_recipe_dirs()
    titles = {}
    for d in dirs:
        slug = d.name
        html = d / f"{slug}.html"
        set_area("Recipe contents & naming")
        photos = check_recipe_contents(d)
        if html.is_file():
            set_area("Design system")
            text, title = check_design(html)
            titles[slug] = title
            set_area("Gallery integrity")
            check_gallery(html, text, photos)
        set_area("Photo privacy")
        check_photos(photos)
    set_area("Index consistency")
    check_index(dirs, titles)
    set_area("PR format")
    check_pr()
    print()
    for _, w in warnings:
        print(f"  \u26a0 {w}")
    for _, e in errors:
        print(f"  \u2717 {e}")
    print()
    passed = not errors
    if not passed:
        print(f"FAIL — {len(errors)} error(s), {len(warnings)} warning(s)")
    elif warnings:
        print(f"PASS — {len(warnings)} warning(s)")
    else:
        print("PASS — all checks clean")
    write_summary(passed, len(dirs))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
