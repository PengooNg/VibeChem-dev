# Changelog

All notable changes to VibeChem are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Repository skeleton: package folders, legal and citation files, contribution guide, PR template and issue forms.
- `scripts/merge_step.py`, the guarded merge of step PRs into their phase branch.
- Python uv workspace (`vibechem-core`, `vibechem-engine`) on Python 3.14 with ruff, pyright (strict), pytest and pre-commit.
- `scripts/check.py`, the local quality check that prints the health summary (`--fast`, `--only`, `--verbose`; full log in `reports/check.log`).
- Desktop app workspace in `app/`: Electron 45 + electron-vite, React 19 with strict TypeScript, Tailwind 4 with the UI_GUIDE design tokens, shadcn/ui config, bundled fonts, English/Japanese/Vietnamese strings, ESLint, Prettier and Vitest. `scripts/check.py --only app` runs the app's lint, type check and tests.
