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
- Native C++20 package skeleton `vibechem-native` (CMake + scikit-build-core + nanobind, built by `uv sync`) with a stub `row_mean` kernel, automatic NumPy fallback when the extension is missing, Catch2 and Python equivalence tests. `scripts/check.py --only native` checks its Python wrapper and tests.
- QA tooling: `vibechem_core.testing` (tolerance, reference, golden-file and hypothesis helpers); `scripts/check.py` now checks package boundaries (import-linter), writes `reports/reference_report.md` and enforces per-package coverage thresholds.
- Reference datasets in `testdata/`: gasoline NIR (60 spectra with octane numbers) and olive oil FTIR (120 spectra from four countries). Their sources, licences and published results are in `testdata/datasets/PROVENANCE.md` and `testdata/expected/`; `vibechem_core.reference_datasets` loads them.
- Engine API walking skeleton: `python -m vibechem_engine.api` serves `/api/v1/health`, `/api/v1/blocks` (SNV only) and the temporary `/api/v1/skeleton/run` on a random loopback port, protected by a per-launch session token and an Origin check, and announces port and token on stdout.
