# VibeChem — Tech Stack, Repository Layout & Conventions

> Status: v0.3 · Last updated: 2026-11-22 · Owner: K (until demo v0: Quan approves, K reviews the backlog later)
> v0.4 (2026-11-23): `@playwright/cli` dev tool; GitHub/Playwright MCP removed; `GITHUB_PAT` no longer needed.
> v0.3: branches and rulesets for phase mode (§8.1); CI triggers on `phase-*`; `.claude/`, `.mcp.json`, `PROGRESS.md`, `merge_step.py` in the layout; legal and citation files (§13, moved from the project plan); Claude Code in developer setup.
> Rule: **no dependency may be added unless it is listed in §1 or approved from the reuse register (§11).** Exact patch versions live in the lock files (`uv.lock`, `pnpm-lock.yaml`); this file fixes the *version line*.

## 1. Versions (chosen for stability, checked November 2026)

### 1.1 Toolchain
| Component | Version line | Why this line | Upgrade rule |
|---|---|---|---|
| Python | **3.14.x** | In bugfix support (≈ until Oct 2027); NumPy/SciPy/scikit-learn/PyInstaller all support it. 3.15 is too new for the scientific wheel ecosystem; 3.13 and 3.12 are now security-only | Move to 3.15 at v1.1 if all deps ship wheels |
| Supported Python for `pip install vibechem-core` | ≥ 3.12 | Users with older environments can still use the library | Drop a version when NumPy drops it |
| uv (Python env + lock) | latest | One tool for Python install, venvs, workspace, lock file | Update monthly |
| Node.js | **24 LTS** | Same Node major as Electron 45; maintenance LTS until Apr 2028 | Move to 26 LTS with the first Electron that ships Node 26 |
| pnpm | 10.x via Corepack (pinned in `package.json` `packageManager`) | Fast, strict workspaces | Update with Node |
| C++ | **C++20** | ARCHITECTURE ADR-002 | — |
| CMake | ≥ 3.28 (fetched automatically by scikit-build-core) | | — |
| Compilers | MSVC (Visual Studio 2022 Build Tools, "Desktop development with C++"), Apple Clang (Xcode CLT), GCC ≥ 13 | Default compilers on each CI runner | Follow runner images |
| Git, GitHub CLI (`gh`) | Git ≥ 2.45, `gh` latest | `gh` is used by Claude Code for PRs and labels | — |
| Claude Code | latest | Builds the project (CLAUDE.md) | Update when prompted |

### 1.2 Python runtime libraries
| Package | Version line | Purpose |
|---|---|---|
| numpy | 2.5.x | Arrays, linear algebra |
| scipy | 1.18.x | Signal processing, statistics, optimisation |
| scikit-learn | 1.9.x | PLS, CV splitters, reference implementations, some models |
| pyarrow | latest | CSV/Parquet reading, Arrow IPC to the UI |
| pandas | 2.x (latest) | Excel/CSV import convenience only; drop if installer size budget requires (§12) |
| openpyxl | latest | Excel import/export |
| jcamp | latest | JCAMP-DX reader (wrapped behind our reader interface) |
| loky | latest | Process-pool executor (ADR-004) |
| threadpoolctl | ≥ 3.5 | BLAS thread limits per worker |
| fastapi | 0.14x (pin minor) | Engine API (ADR-003) |
| uvicorn | latest | ASGI server |
| pydantic | 2.13.x | API models, parameter schemas |
| jinja2 | 3.x | HTML reports |
Chemometrics libraries (chemotools, pybaselines, kennard-stone…) are **candidates** in §11; each is added to this table only after its TASKS step approves it.
PDF reports: the engine produces HTML; the desktop app converts to PDF with Chromium's print-to-PDF (no Python PDF dependency). The headless CLI exports HTML only.

### 1.3 Python dev tools
| Tool | Purpose |
|---|---|
| ruff | Lint + format |
| pyright (strict) | Type checking (installed as `pyright[nodejs]`, which brings a Node binary via `nodejs-wheel-binaries`, so no system Node is needed) |
| pytest, pytest-cov, pytest-xdist | Tests, coverage (per-package thresholds in `check.py`), parallel tests |
| pytest-regressions (brings PyYAML, read by `check_golden`) | Golden files for `vibechem_core.testing.check_golden` (T0.07) |
| hypothesis | Property-based tests |
| import-linter | Enforce package boundaries (§3.1) |
| pyinstaller 6.21.x | Engine bundle for the desktop app |
| pre-commit | Run lint/format before commits |

### 1.4 Native (C++)
| Package | Version line | Purpose |
|---|---|---|
| nanobind | 2.x latest (T0.05: 2.9.2, pinned in `packages/native/pyproject.toml`) | C++ ↔ Python bindings |
| scikit-build-core | 1.1.x (T0.05: 1.1.2, pinned in `packages/native/pyproject.toml`) | Build backend (CMake → wheel) |
| cibuildwheel | latest | Wheels for Windows/macOS/Linux in CI |
| Eigen | 3.4.x | Linear algebra in kernels (K may evaluate Eigen 5.x) |
| Catch2 | 3.x (T0.05: v3.16.1 via CMake FetchContent in `packages/native/tests/cpp/`) | C++ unit tests (Python equivalence tests stay in pytest) |
| clang-format, clang-tidy | latest | Formatting, static analysis |

### 1.5 Frontend and desktop
| Package | Version line | Purpose |
|---|---|---|
| Electron | **45.x** | Desktop shell (supported until Apr 2027; upgrade every second major) |
| electron-builder | latest | Installers: NSIS `.exe`, `.dmg` (arm64 + x64), AppImage/`.deb` |
| TypeScript | **6.0.x** | Last JavaScript-based compiler; all tooling compatible. Re-evaluate TypeScript 7 at v1.1 |
| React | 19.2.x | UI |
| Vite | 7.x | Dev server + build |
| electron-vite | 5.x | Runs Vite for the renderer and builds the Electron main process (`app/electron.vite.config.ts`); chosen in T0.04 over electron-forge, which brings its own packaging next to electron-builder |
| @vitejs/plugin-react | matching Vite 7 | |
| Tailwind CSS | 4.x | Styling (UI_GUIDE.md tokens) |
| shadcn/ui | CLI latest (copies components into repo) | Component primitives (Radix); `app/components.json`, `cn` helper from `clsx` 2.x + `tailwind-merge` 3.x |
| @xyflow/react | 12.x (not 13 pre-release) | Pipeline canvas (keep its attribution; MIT) |
| uPlot | 1.6.x | Fast line plots for spectra; density mode drawn on canvas |
| zustand | 5.x | UI state |
| @tanstack/react-query | 5.x | Server state / API calls |
| i18next + react-i18next | latest | EN/JA/VI |
| apache-arrow (JS) | latest, matching pyarrow format | Binary previews |
| openapi-typescript | latest | Generate TS types from the engine's OpenAPI |
| lucide-react | latest | Base icons (custom glyphs in `app/renderer/src/ui/glyphs`) |
Fonts Inter, JetBrains Mono, Noto Sans JP: SIL Open Font Licence, bundled locally (no web fonts) through the `@fontsource-variable/*` 5.x npm packages; Vite copies the font files into the build.

### 1.6 Frontend dev tools
| Tool | Purpose |
|---|---|
| ESLint 9 (flat config) + typescript-eslint, eslint-plugin-react-hooks, eslint-plugin-react-refresh | Lint |
| Prettier 3 | Format |
| Vitest 4 + Testing Library + jsdom | Component/unit tests |
| `@playwright/test` (Electron mode) | End-to-end tests of the desktop app |
| `@playwright/cli` | Agent browser control for visual checks (token-efficient; replaces Playwright MCP) |

### 1.7 CI and repository services
GitHub Actions standard runners (`ubuntu-latest`, `windows-latest`, `macos-latest` = Apple Silicon, `macos-15-intel` = Intel), Dependabot (monthly grouped updates + security alerts), secret scanning + push protection, rulesets (§8.1), CODEOWNERS, issue forms, Zenodo integration (at release).

## 2. Developer setup (Windows first; macOS/Linux equivalents in brackets)
1. Install **Git for Windows** (Claude Code on Windows uses its Bash), **GitHub CLI** (`winget install GitHub.cli`, then `gh auth login`), **Visual Studio 2022 Build Tools** with "Desktop development with C++" [macOS: `xcode-select --install`; Linux: `build-essential`].
2. Install **uv**: `winget install astral-sh.uv` [macOS/Linux: official install script].
3. Install **Node 24 LTS** (`winget install OpenJS.NodeJS.LTS` or fnm/nvm) and run `corepack enable`, then `corepack install -g pnpm@10.34.9` (the version in `app/package.json`; without it, `pnpm --dir app …` run from the repo root picks Corepack's default pnpm and refuses to run).
4. Install **Claude Code** (official installer) and sign in.
5. Clone the repo, then from the repo root (after T0.04 also `pnpm --dir app exec playwright install chromium`):
   - `uv python install 3.14`
   - `uv sync` (creates `.venv`, installs all Python packages incl. native build)
   - `pnpm --dir app install`
6. Verify: `uv run python scripts/check.py --fast` → all PASS.
Environment variables per machine: `VIBECHEM_MACHINE` (e.g. `work-pc`, `laptop`; shown in PR status lines).
An existing conda Python can stay for personal work; VibeChem uses its own uv-managed 3.14 environment so nothing conflicts.

## 3. Repository layout and code map
```
vibechem/
├─ CLAUDE.md                     Rules for Claude Code (read first)
├─ .claude/
│  ├─ settings.json              Shared permissions for Claude Code
│  ├─ skills/                    /phase, /step, /resume, /status, /bug + ui-ux-pro-max, playwright-cli, Emil's four skills
│  └─ agents/step-runner.md      Subagent that executes one TASKS.md step
├─ .mcp.json                     Context7 MCP server
├─ CHANGELOG.md                  Keep-a-Changelog format; updated in every PR that changes behaviour
├─ THIRD_PARTY.md                Ported code and bundled assets with licences
├─ LICENSE, CITATION.cff, CONTRIBUTING.md
├─ docs/                         Project docs
│  ├─ TASKS.md, PROGRESS.md      Steps and the running progress log
│  ├─ METHODS.md                 Algorithm definitions (from T1.04)
│  ├─ references.bib             Method references (from T1.04)
│  ├─ handoff/                   Handoff notes while a step is paused (deleted at merge)
│  ├─ spikes/                    Spike results (T0.12, T0.13)
│  └─ research/                  Anonymised user-research notes and synthesis
├─ packages/
│  ├─ core/                      Python package `vibechem_core` — science only
│  │  ├─ src/vibechem_core/
│  │  │  ├─ data/                SpectralDataset, axis, roles
│  │  │  ├─ io/                  File readers/writers (csv, excel, jcamp, spc)
│  │  │  ├─ blocks/              One file per block, grouped by class
│  │  │  │  ├─ preprocess/ split/ validate/ select/ model/
│  │  │  │  ├─ explore/ stats/ transfer/ imaging/ deploy/
│  │  │  ├─ block.py             Block contract (base class, Param, port)
│  │  │  ├─ registry.py          Block registry
│  │  │  ├─ metrics.py           Chemometric metrics
│  │  │  └─ errors.py            Error classes + codes
│  │  └─ tests/                  Mirrors src/ exactly (test_<module>.py)
│  ├─ engine/                    Python package `vibechem_engine` — runs pipelines
│  │  ├─ src/vibechem_engine/
│  │  │  ├─ ports/ graph/ formats/ compiler/ cache/ executor/
│  │  │  ├─ scheduler/ runners/ project/ api/ cli/
│  │  └─ tests/                  Mirrors src/
│  └─ native/                    C++ package `vibechem_native`
│     ├─ src/ include/vibechem/ bindings/
│     ├─ python/vibechem_native/ Python wrapper + fallback dispatch
│     ├─ tests/cpp/              Catch2 tests
│     └─ tests/python/           Equivalence tests vs core reference
├─ app/
│  ├─ main/                      Electron main + preload (TypeScript)
│  ├─ renderer/src/
│  │  ├─ api/                    Generated client + hooks
│  │  ├─ canvas/ inspector/ plots/ jobs/ library/
│  │  ├─ i18n/{en,ja,vi}/        String files
│  │  ├─ state/                  zustand stores
│  │  └─ ui/                     shadcn components, tokens, glyphs, fonts
│  └─ e2e/                       Playwright tests
├─ testdata/
│  ├─ datasets/                  Reference datasets + PROVENANCE.md
│  └─ expected/                  Golden outputs (metrics, node snapshots)
├─ reports/                      Generated by check.py (reference_report.md); not edited by hand
├─ scripts/                      check.py, merge_step.py, bench.py, release helpers
└─ .github/                      workflows/, ISSUE_TEMPLATE/, PULL_REQUEST_TEMPLATE.md, CODEOWNERS, dependabot.yml
```
pengoo is **not** stored in this repository. When a step ports pengoo code, Quan points Claude Code to his local copy; only the ported parts enter the repo (D-016).

### 3.1 Dependency boundaries (enforced by import-linter in CI)
| Package | May import | Must never import |
|---|---|---|
| `vibechem_core` | numpy, scipy, scikit-learn, approved chemometrics libraries from §11, `vibechem_native` (optional) | `vibechem_engine`, fastapi, anything UI |
| `vibechem_engine` | `vibechem_core`, loky, fastapi, pyarrow | renderer code |
| `vibechem_native` (Python wrapper) | numpy, `vibechem_core` reference functions (for fallback) | `vibechem_engine` |
| `app/renderer` | engine **only via HTTP/WS API** | Node.js APIs (sandboxed) |
| `app/main` | Electron, child-process control of engine | business logic |
External chemometrics libraries are only imported inside block files (wrapped), never spread across the codebase — so one library can be replaced in one place.

Each package folder has a `README.md`: purpose, public API, allowed dependencies, where its tests are. Claude Code reads this README before touching a package.

## 4. Python conventions
- First line of every source file: `# SPDX-License-Identifier: GPL-3.0-or-later` (ported files keep the original notice too).
- Fully typed; `pyright --strict` clean. No `Any` except at I/O boundaries.
- Docstrings: NumPy style. Every block file starts with the header docstring from CLAUDE.md §5 (incl. `Implementation:` line).
- Numbered `# Step N:` comments for algorithm steps, matching METHODS.md.
- Errors: raise subclasses from `vibechem_core.errors` with a `code` from DATA_MODEL.md §7. Never raise bare `Exception`.
- Logging: `logging.getLogger(__name__)`; no `print`.
- Randomness: accept a `numpy.random.Generator` argument; never use global random state.
- No pickle for anything persisted or shared (ADR-007).
- Files: one block per file; one public class per block; ≤ 400 lines per file (split otherwise).

## 5. C++ conventions
- SPDX header as above. C++20, Eigen; no raw `new`/`delete`; `std::span` for views; RAII.
- Every exported function: doc comment with the matching Python reference function and METHODS.md section. (The T0.05 stub `row_mean` has no core counterpart; its reference is `vibechem_native/_reference.py`.)
- Accept `n_threads` (default 1); release the GIL in bindings.
- clang-format (repo config), clang-tidy clean, warnings as errors.

## 6. TypeScript conventions
- SPDX header as above. `strict: true`; no `any`.
- API types only from the generated OpenAPI types (`app/renderer/src/api/schema.d.ts`); never hand-write API field names.
- All user-visible text through i18next keys; no literal UI strings.
- Components small (≤ 200 lines); state in zustand stores; server data via TanStack Query.

## 7. Commands (single source of truth)
| Command | What it does |
|---|---|
| `uv run python scripts/check.py` | **Full local check**: format, lint, types, import boundaries, all Python tests, reference report, golden pipeline, app lint + unit tests. Prints the health summary |
| `uv run python scripts/check.py --fast` | Same, skipping slow tests (< 3 min target) |
| `uv run python scripts/check.py --fast --only core` | One area (`core`, `engine`, `native`, `app`) |
| `uv run pytest packages/core/tests/blocks/preprocess/test_snv.py` | One test file |
| `uv run python scripts/merge_step.py <pr>` | Merge a green step PR into its phase branch (the only allowed merge path for Claude Code) |
| `uv run python scripts/bench.py` | Speed-up and determinism benchmarks |
| `pnpm --dir app dev` | Run UI + Electron in development |
| `pnpm --dir app e2e` | Playwright end-to-end tests |
| `pnpm --dir app dist` | Build installers locally |
Claude Code commands: `/phase N`, `/step T<x> [wait]`, `/resume [answer]`, `/status`, `/bug <issue>` (`.claude/skills/`).

## 8. CI workflows
| Workflow | Trigger | Jobs | Target time |
|---|---|---|---|
| `ci.yml` | pull requests to `main` or `phase-*`; pushes to `phase-*` | `check --fast` on Windows, macOS (arm64), Linux; native wheels build; sanitizer job (Linux) | < 15 min |
| `installers.yml` | PRs touching `app/`, `packages/engine/`, `packages/native/`, packaging config; or label `build-installers`; pushes to `phase-*` that touch those paths | Installers for 3 OS + smoke test (`/health` = ready); artifacts kept 14 days | < 30 min |
| `nightly.yml` | daily on `main` and the newest `phase-*` branch | Full `check` incl. slow tests, benchmarks, determinism 1 vs N cores, e2e on 3 OS, installers incl. **macOS Intel**; opens an `S2` issue on failure | — |
| `release.yml` | version tag | Installers (Windows x64, macOS arm64 + x64, Linux x64) + checksums → GitHub Release → Zenodo | — |

### 8.1 Branches and rulesets
| Branch | Who writes | Ruleset |
|---|---|---|
| `main` | Quan merges the phase PR at each gate (merge commit); Dependabot PRs | PR required · required checks (`ci.yml` jobs, added after T0.06) · **0 approvals until K joins, then 1 (CODEOWNERS)** · block force push · block deletion |
| `phase-*` | Claude Code via `scripts/merge_step.py` (squash) | PR required · same required checks · 0 approvals · block force push · block deletion |
| `t<step>-*`, `bug-*` | Claude Code | none |
Merge methods: squash for step PRs, merge commit for `phase-N → main`. `main` changes during a phase (Dependabot) are brought into the phase branch by a `[SYNC]` PR (CLAUDE.md §14.1).

## 9. Dependency policy
- New dependency → add a row in §1 (version line, purpose, licence) and update §11 status in the same PR; K approves (until demo v0: Quan, or automatic for listed candidates per CLAUDE.md §12.5, plus a K backlog row).
- Licences must be GPL-3.0-compatible (MIT, BSD, Apache-2.0, LGPL, GPL).
- Prefer packages with wheels for Windows, macOS (arm64 + x64) and Linux on Python 3.14; no packages that need a compiler at install time on users' machines.
- Small single-maintainer libraries: pin exact version, wrap inside block files only, keep our reference tests; if abandoned, vendor (copy with licence) or replace.
- Dependabot opens one grouped PR per ecosystem per month against `main`; Quan merges it when CI is green; it reaches the phase branch through `[SYNC]`.

## 10. Electron security checklist
`contextIsolation: true` · `sandbox: true` · `nodeIntegration: false` · no `remote` module · Content-Security-Policy restricting to `self` · no loading of remote URLs · preload exposes only a typed minimal API (engine port + token, file dialogs, print-to-PDF) · engine bound to 127.0.0.1 with token (DATA_MODEL.md §1).

## 11. Reuse register — check before building anything
Status: **candidate** (evaluate in the listed step, per CLAUDE.md §12) · **approved** (in §1) · **rejected** (reason recorded).
| Area / step | Candidate | Licence | What it could save | Status |
|---|---|---|---|---|
| Python package scaffold (T0.03) | `scientific-python/cookie` template; `uv init --lib` | BSD-3 / — | pyproject, ruff, pytest, pre-commit, CI patterns | approved (T0.03: cookie's ruff/pytest settings adopted in root `pyproject.toml`; `uv_build` src layout as from `uv init --lib`; the full copier template was not used — no nox/docs/CI) |
| C++ extension scaffold (T0.05) | `nanobind_example` (wjakob); `uv init --lib --build-backend=scikit` | BSD-3 / — | Working CMake + scikit-build-core + nanobind + cibuildwheel setup | approved (T0.05: nanobind_example / nanobind packaging-guide configuration — stable ABI `cp312`, `build-dir`, `wheel.packages`; `uv init --build-backend=scikit` rejected: pybind11 scaffold) |
| Electron + Vite + React scaffold (T0.04) | `create-vite` React-TS template; electron-vite or electron-forge templates | MIT | Dev server + Electron wiring | approved (T0.04: electron-vite 5 with the layout of its react-ts template; shadcn config written by hand from its manual-install guide because `shadcn init` does not detect electron-vite; electron-forge rejected: its packaging overlaps electron-builder) |
| Python sidecar packaging (T0.11) | electron-builder `extraResources` + PyInstaller one-folder (common pattern) | MIT / GPL-with-exception | Bundling the engine | candidate |
| Golden-file tests (T0.07) | `pytest-regressions` | MIT | Golden data/num regression fixtures | approved (T0.07: `data_regression` stores the per-node hash file and handles `--force-regen`; `num_regression` available for metric tables in T2.13) |
| Reference datasets (T0.08) | `rdata` (reads R `.RData`/`.rds` without R) | MIT | Converting R package datasets | not a dependency (T0.08: used once in a throwaway `uv run --no-project --isolated` env to convert `gasoline.RData` to CSV; loaders use stdlib `csv` + numpy) |
| Preprocessing: MSC, SG derivatives, scaling, smoothing, some baselines (T1.07–T1.09, Phase 6) | `chemotools` (scikit-learn-style transformers) | MIT | Large part of P0 preprocessing | candidate |
| Baselines: AsLS, airPLS, arPLS, polynomial, SNIP… (Phase 6) | `pybaselines` (50+ algorithms) | BSD-3 | Almost all baseline methods | candidate |
| Kennard–Stone split (T1.10) | `kennard-stone` | MIT | KS split; SPXY may still be ours | candidate |
| CV splitters (T1.11) | scikit-learn `KFold`, `GroupKFold`, `LeaveOneOut`, `RepeatedKFold` | BSD-3 | Most fold generators (venetian/contiguous are small extras) | approved (scikit-learn in §1) |
| PLS (T1.12) | scikit-learn `PLSRegression` (NIPALS) | BSD-3 | PLS1/PLS2 fit/predict; VIP and SIMPLS are small additions | approved |
| EMSC, spike removal, ALS, interpolation (Phase 6) | Orange-Spectroscopy (port with header) | GPL-3.0 | Proven implementations | candidate (port) |
| Preprocessing grid search (T2.10) | pengoo (Quan's local copy, port selected parts) | owner | Search logic | candidate (port; no numba) |
| JCAMP-DX (T1.06) | `jcamp` | MIT | Reader | approved |
| SPC (T1.06) | Existing SPC readers on PyPI/GitHub — search first | to check | Reader | candidate (search; build only if none fit) |
Add a row whenever a step finds a new candidate, even if rejected — it prevents the same search next time.

## 12. Known packaging pitfalls (check in T0.11, T0.13)
- **PyInstaller + process pools:** frozen apps must call `multiprocessing.freeze_support()` and use the spawn start method; loky workers inside a frozen bundle must be tested on Windows in the walking skeleton.
- **Installer size:** Electron (~100 MB) + Python + NumPy/SciPy/scikit-learn + pyarrow can approach the 400 MB budget. Measure in T0.11; options: exclude tests/docs from wheels, drop pandas, use pyarrow's CSV reader.
- **macOS:** build arm64 and x64 separately; unsigned apps need the first-launch guide (D-015).
- **Windows long paths:** keep install paths short; avoid deep cache paths (a problem already seen with numba caches).

## 13. Legal and citation files
| File | Created in |
|---|---|
| `LICENSE` (GPL-3.0-or-later), `CITATION.cff`, `THIRD_PARTY.md`, `CHANGELOG.md`, `CONTRIBUTING.md` | T0.02 |
| `docs/references.bib` (every implemented method) | T1.04, then grows with each block |
| README "How to cite", `codemeta.json` | T7.01 |
```yaml
cff-version: 1.2.0
message: "If you use VibeChem, please cite it as below, and cite the methods listed in your VibeChem report."
title: "VibeChem: an open-source visual workbench for predictive chemometrics of vibrational spectra"
type: software
authors:
  - family-names: Nguyen
    given-names: Minh Quan
    orcid: "https://orcid.org/0000-0000-0000-0000"   # TODO: real ORCID (ask Quan)
  # - add K (name + ORCID) once authorship is agreed
version: "0.0.0"
doi: "10.5281/zenodo.XXXXXXX"   # TODO after first release
license: "GPL-3.0-or-later"
repository-code: "https://github.com/<owner>/vibechem"
keywords: [chemometrics, NIR, Raman, FTIR, spectroscopy, PLS, calibration transfer]
```
Reused libraries that implement methods (e.g. chemotools, pybaselines) are cited in the generated reports alongside the method papers. Identifiers: Zenodo–GitHub integration (version DOIs + concept DOI) · ORCID for authors · Software Heritage archiving once public.
