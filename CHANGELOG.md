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
- Desktop app walking skeleton: in development the app starts the engine itself and shows a fixed Dataset → SNV pipeline on a canvas; Run loads the gasoline NIR spectra and plots them raw and after SNV. The first end-to-end test (Playwright, Electron) checks this flow on Windows, macOS and Linux.
- Installers for Windows (NSIS), macOS (dmg, Apple Silicon) and Linux (AppImage, deb), built in CI. They bundle the engine as a standalone program, so no Python install is needed. Each build is smoke-tested: the bundled engine must report ready, and the packaged app must run the Dataset → SNV pipeline. The builds are unsigned for now.
- `vibechem_core.data.SpectralDataset`: an immutable container for spectra (signal values, spectral axis with unit, signal unit, sample IDs, source-row index, groups, Y with units, classes, metadata columns, pixel layout, processing history). It checks its inputs and keeps every annotation aligned with the rows when signals are replaced (`with_X`) or rows are selected (`subset`).
- Block contract for developers (`vibechem_core.block`, `vibechem_core.registry`, `vibechem_core.errors`): a block declares its ports, typed parameters and metadata, implements `fit` and `apply` (fitted blocks) or `apply` only, and keeps any fitted state as JSON values plus arrays. A registry lists blocks with their metadata, and errors carry the codes from the error catalogue.
- Fitted block state can be saved and loaded as JSON plus `.npy` files, never pickle (`vibechem_core.block.save_state`/`load_state`). `vibechem_core.wrap.TransformerBlock` turns a scikit-learn-style transformer into a fitted block whose state is saved the same way. `vibechem-core` now depends on scikit-learn 1.9.
