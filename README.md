# Семейные рецепты 🍲

Lightweight static recipe website for the family, served at
**[https://recipe.geekway.dev](https://recipe.geekway.dev)** via GitHub Pages.
Pure HTML5 + CSS3 + Vanilla JS — no frameworks, no build step, no database.

## Structure

```
/
├── index.html              # navigation / table of contents
├── recipes/
│   └── <slug>/             # one folder per recipe
│       ├── <slug>.html     # the recipe page (prints on a single A4 page)
│       └── photos/         # optional photo gallery
├── scripts/quality_gate.py # CI quality gate (run it locally too)
└── .github/workflows/      # GitHub Actions
```

## Adding a recipe

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full standards: directory
layout, slug/photo naming, design system, gallery rules, PR format and
release conventions. Every PR is validated by the quality gate CI check.

Quick local validation:

```bash
python3 scripts/quality_gate.py
```

## Deployment

GitHub Pages serves the repo root (see `CNAME`); pushing to `main`
deploys automatically. No manual steps.
