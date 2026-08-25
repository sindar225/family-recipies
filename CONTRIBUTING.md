# Contributing to family-recipes

This repository is the family recipe site served at **https://recipe.geekway.dev**
(GitHub Pages). The repo is **public** — treat every file as publishable:
no personal data, no names beyond dish titles, no GPS/EXIF in photos.

The repository is maintained end-to-end by an autonomous agent; human
contributors follow the same standards. Every change lands via a pull
request, and a CI **quality gate** enforces the rules below. A PR that
violates them fails the check.

## 1. Directory structure

```
/
├── index.html                    # navigation (auto-managed, see §4)
├── recipes/
│   └── <slug>/
│       ├── <slug>.html           # the recipe page (name = slug)
│       └── photos/               # optional, only if photos exist
│           └── photo-1.jpg       # photo-N.jpg/.jpeg/.png/.webp
├── scripts/quality_gate.py       # the gate (runs locally & in CI)
└── .github/workflows/quality-gate.yml
```

- Every recipe lives in `recipes/<slug>/` — never in the root.
- A recipe directory contains exactly two things: `<slug>.html` and an
  optional `photos/` folder. Nothing else.
- The root contains only `index.html`, docs, `CNAME`, `scripts/`, `.github/`.

## 2. Naming conventions

| Thing        | Rule                                                          | Example             |
|--------------|---------------------------------------------------------------|---------------------|
| Recipe slug  | lowercase letters/digits, hyphen-separated words, no spaces   | `chicken-paprikash` |
| Recipe file  | `<slug>.html` (must match the directory name)                 | `chicken-paprikash.html` |
| Photo files  | `photo-N.<ext>`, N = 1,2,3…, lowercase extension              | `photo-1.jpg`       |
| Page title   | `<title>` in Russian, human-readable (used in the index)      | `Цыплёнок по-паприкаши` |
| Branch       | `recipes/<slug>` for new recipes, `<type>/<summary>` otherwise| `recipes/chicken-paprikash` |
| PR title     | `Add recipe: <Russian title>` for new recipes                 | `Add recipe: Цыплёнок по-паприкаши` |

## 3. Design system

The canonical template is **`recipes/pileca-lava/pileca-lava.html`** — copy it
for every new recipe. Never copy the old `khachapuri` layout (legacy:
hardcoded colors, no design tokens).

- **Fonts:** Cormorant Garamond (600;700) + Inter (400;500;600;700) via Google Fonts.
- **Palette (CSS variables):** `--paper #fbf8f2`, `--ink #292825`,
  `--muted #77736b`, `--green #385c4e`, `--green-soft #eaf1ec`,
  `--red #b85f45`, `--red-soft #f5e8e1`, `--line #e2ddd4`.
- **A4 rule:** `@page { size: A4; margin: 10mm }` and the page
  (`<main class="page">`, 210mm × 297mm) must hold **exactly one printed
  page** — tighten wording or padding if the content overflows. No external
  frameworks, no heavy libraries.
- **Canonical blocks** (in order): `.header` (`.kicker` / `h1` / `.subtitle`)
  → `.stats` (`.stat` + `.icon`) → `.layout` grid (`.card` with
  `.section-label` + `h2`) → `.ingredients` (`.ingredient` + `.check`) and
  `.steps` (`.step` + `.num`) → `.finish` (`.finish-card`) → `.footer`.
- **Print:** `@media print { body{background:#fff} .page{margin:0;box-shadow:none} }`
  plus the mobile `@media(max-width:800px)` block.

## 4. Gallery

Only when the recipe has photos:

- Button right after `<main class="page">`:
  `<button class="gallery-btn" onclick="openGallery()">📸 Посмотреть фото</button>`
- Modal block between `<!-- GALLERY_START -->` and `<!-- GALLERY_END -->`
  before `</body>`: `<style>` + `#gallery-modal` + vanilla JS
  (`openGallery` / `closeGallery` / `showSlide` / `changeSlide`).
- The print rule **must** hide it:
  `@media print { .gallery-modal, .gallery-btn { display: none !important; } }`
- `<img>` tags appear **only** inside the gallery block — never in the page flow.
- Every photo in `photos/` must be referenced; every reference must resolve.
- **Strip all EXIF/GPS metadata** from photos before committing (public repo!):
  `exiftool -overwrite_original -all= <photo>` or `piexif.remove()`.

Text-only recipes (no photos): no button, no gallery block.

## 5. Index (navigation)

`index.html` links are generated between the markers
`<!-- RECIPE_LINKS_START -->` / `<!-- RECIPE_LINKS_END -->`. When adding a
recipe, append one `.recipe-link` card (same markup as the existing ones,
`<strong>` = the recipe `<title>`). Never touch anything outside the markers.

## 6. Pull request format

Every PR that touches `recipes/` or `index.html` **must** have this body
structure (the quality gate enforces it):

```markdown
## Motivation
Why this change exists — e.g. adding a new family recipe.

## Changes
- `recipes/<slug>/<slug>.html` — new recipe page
- `recipes/<slug>/photos/photo-1.jpg` — photos
- `index.html` — navigation link added

## Risks
Anything that could break: A4 page fit, broken image links, print layout.

## Testing
How to verify: open the page in a browser, click the gallery button,
check print preview (Ctrl+P / Cmd+P) shows a single A4 page.
```

New-recipe PRs must be titled `Add recipe: <Russian title>`.

## 7. Releases

After a recipe PR merges, create a GitHub Release:

- **Tag:** `recipes/<slug>` (e.g. `recipes/chicken-paprikash`)
- **Title:** the dish name
- **Notes:** one-paragraph changelog summary in English

### Post-deploy validation

GitHub Pages deploys with a lag of ~3 minutes. After every merge that
touches `recipes/` or `index.html`, the **Post-Deploy Site Check**
workflow (`.github/workflows/post-deploy-check.yml`) waits for the deploy,
then validates the live site with `scripts/verify_live_site.py`:

- `index.html` is up and lists every expected recipe URL
- every recipe page returns 200 and carries the canonical markers
  (`<title>`, `.page`, print media rule)
- every gallery photo loads (200)

If validation fails, the workflow opens an issue automatically. The fix
goes back through the normal cycle: **patch PR → quality gate → merge →
re-validate**. Local run:

```bash
python3 scripts/verify_live_site.py    # validates recipe.geekway.dev
```

## 8. The quality gate

`scripts/quality_gate.py` runs on every PR (see
`.github/workflows/quality-gate.yml`) and locally:

```bash
python3 scripts/quality_gate.py          # pass/fail for the whole repo
python3 scripts/quality_gate.py --summary /tmp/g.md   # also write a markdown report
PR_BODY="..." PR_TITLE="..." CHANGED_STATUS="$(git diff --name-status origin/main...HEAD)" \
  python3 scripts/quality_gate.py        # also checks the PR body format
```

It validates: directory layout, slug & photo naming, design-system
compliance, gallery integrity, index consistency, photo EXIF/GPS privacy,
and (on PRs) the body/title format. Exit code 0 = pass.

Both CI workflows publish a human-readable **markdown summary** on the
run page (via `$GITHUB_STEP_SUMMARY`): the quality gate shows a
per-area status table, the post-deploy check shows a per-URL result
table. Summaries render even on failed runs.
