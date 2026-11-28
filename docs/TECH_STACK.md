# VibeChem — Tech Stack, Repository Layout & Conventions

> Status: v0.6 · Last updated: 2026-11-26 · Owner: Quan
> v0.6 (tooling v0.5): K removed from the workflow — Quan approves dependencies (§9); the Phase 3 native-kernel rules moved here from the former CLAUDE.md section 15 (§5).
> v0.5 (2026-11-25): §11.2 pengoo port inventory (T1.00b); PyWavelets candidate.
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
| pyarrow | latest | Parquet, Arrow IPC to the UI (engine only; CSV/TSV is read in core with stdlib `csv` + NumPy since T1.05) |
| pandas | 2.x (latest) | Excel/CSV import convenience only; drop if installer size budget requires (§12) |
| openpyxl | 3.1.x | Excel import/export (`vibechem-core` runtime dependency since T1.05, imported lazily in `vibechem_core/io/table.py`) |
| jcamp | 1.3.x | JCAMP-DX reader (`vibechem-core` runtime dependency since T1.06, imported lazily in `vibechem_core/io/jcamp.py`; numpy only) |
| brukeropus | 1.4.x | Bruker OPUS reader (`vibechem-core` runtime dependency since T1.06b, imported lazily in `vibechem_core/io/opus.py`; pure Python, numpy only; its `control` submodule (Windows DDE to a running OPUS) is loaded by the package `__init__` but never used) |
| loky | 3.7.x (`>=3.7,<3.8`: `loky_freeze_support()` relies on its command lines) | Process-pool executor (ADR-004; `vibechem-engine` runtime dependency since T2.07) |
| threadpoolctl | ≥ 3.8 | BLAS thread limits per worker (`vibechem-engine` runtime dependency since T2.07) |
| fastapi | 0.162.5 (pin patch; 2026-11 sync: newest release at least two weeks old) | Engine API (ADR-003) |
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
| httpx2 | HTTP client required by FastAPI's `TestClient` (engine API tests, T0.09) |
| pytest-regressions (brings PyYAML, read by `check_golden`) | Golden files for `vibechem_core.testing.check_golden` (T0.07) |
| hypothesis | Property-based tests |
| import-linter | Enforce package boundaries (§3.1) |
| pyinstaller 6.22.x | Engine bundle for the desktop app |
| pre-commit | Run lint/format before commits |

### 1.4 Native (C++)
| Package | Version line | Purpose |
|---|---|---|
| nanobind | 2.x latest (T0.05: 2.9.2, pinned in `packages/native/pyproject.toml`) | C++ ↔ Python bindings |
| scikit-build-core | 1.1.x (T0.05: 1.1.2, pinned in `packages/native/pyproject.toml`) | Build backend (CMake → wheel) |
| cibuildwheel | latest | Wheels for Windows/macOS/Linux in CI |
| Eigen | 3.4.x | Linear algebra in kernels (Eigen 5.x may be evaluated) |
| Catch2 | 3.x (T0.05: v3.16.1 via CMake FetchContent in `packages/native/tests/cpp/`) | C++ unit tests (Python equivalence tests stay in pytest) |
| clang-format, clang-tidy | latest | Formatting, static analysis |

### 1.5 Frontend and desktop
| Package | Version line | Purpose |
|---|---|---|
| Electron | **45.x** | Desktop shell (supported until Apr 2027; upgrade every second major) |
| electron-builder | 26.x (T0.11: 26.18.0, exact pin) | Installers: NSIS `.exe`, `.dmg` (arm64 + x64), AppImage/`.deb` |
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
   - `uv sync` (creates `.venv`, installs all Python packages incl. native build) [macOS: `bash scripts/uv_sync.sh` instead, then `uv run --no-sync …` (or `export UV_NO_SYNC=1`): it installs the NumPy/SciPy wheels with OpenBLAS via `MACOSX_DEPLOYMENT_TARGET=13.0 uv sync --locked --python-platform <arch>-apple-darwin`, because Accelerate breaks bit-identity (BUG #84, R67); a plain `uv run` may sync back to the Accelerate wheels. CI, nightly and the installer builds use the same script.]
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
│  │  │  ├─ io/                  File readers/writers (csv, excel, jcamp, spc, spa, perkinelmer, wdf, opus)
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
pengoo is **not** stored in this repository. When a step ports pengoo code, Quan points Claude Code to his local copy (since T1.00b: `pengoo/` at the repo root, excluded through `.git/info/exclude`); only the ported parts enter the repo (D-016). Inventory: §11.2.

### 3.1 Dependency boundaries (enforced by import-linter in CI)
| Package | May import | Must never import |
|---|---|---|
| `vibechem_core` | numpy, scipy, scikit-learn, approved chemometrics libraries from §11, file-format libraries listed in §1.2/§11 (openpyxl, jcamp, brukeropus; imported only inside `vibechem_core/io/`, decision by Quan in T1.05), `vibechem_native` (optional) | `vibechem_engine`, fastapi, pyarrow (T1.05: tables in core are column name → NumPy array mappings; the engine converts to Arrow), anything UI |
| `vibechem_engine` | `vibechem_core`, numpy, loky, threadpoolctl, fastapi (+ starlette, pydantic), uvicorn, pyarrow | renderer code |
| `vibechem_native` (Python wrapper) | numpy, `vibechem_core` reference functions (for fallback) | `vibechem_engine` |
| `app/renderer` | engine **only via HTTP/WS API** | Node.js APIs (sandboxed) |
| `app/main` | Electron, child-process control of engine | business logic |
External chemometrics libraries are only imported inside block files (wrapped), never spread across the codebase — so one library can be replaced in one place.

Each package folder has a `README.md`: purpose, public API, allowed dependencies, where its tests are. Claude Code reads this README before touching a package.

## 4. Python conventions
- First line of every source file: `# SPDX-License-Identifier: GPL-3.0-or-later` (ported files keep the original notice too).
- Fully typed; `pyright --strict` clean. No `Any` except at I/O boundaries.
- Docstrings: NumPy style. Every block file starts with the header docstring from docs/rules/CODING.md#block-template-and-comment-style (incl. `Implementation:` line).
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
- **Every native kernel (Phase 3)** has a Python reference, equivalence tests against it, sanitizer-clean CI and an automatic fallback to the Python reference; each kernel step gets a **cpp-reviewer** pass, and open findings become `docs/RISKS.md` rows. A kernel is written only if no existing fast implementation can be reused and NumPy/SciPy vectorisation is not enough.

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
| `pnpm --dir app dist` | Build installers locally (`app/dist/`); first freeze the engine with `uv run python scripts/build_engine.py` (→ `build/engine/`) |
Claude Code commands: `/phase N`, `/step T<x> [wait]`, `/resume [answer]`, `/status`, `/bug <issue>` (`.claude/skills/`).

## 8. CI workflows
| Workflow | Trigger | Jobs | Target time |
|---|---|---|---|
| `ci.yml` | pull requests to `main` or `phase-*`; pushes to `phase-*` | `check --fast` + Electron e2e (`pnpm --dir app e2e`) on Windows, macOS (arm64), Linux; native wheels build; sanitizer job (Linux) | < 15 min |
| `installers.yml` | PRs touching `app/`, `packages/engine/`, `packages/native/`, `testdata/`, packaging config (`scripts/build_engine.py`, `scripts/smoke_engine.py`, `pyproject.toml`, `uv.lock`); or label `build-installers`; pushes to `phase-*` that touch those paths | Installers for 3 OS (PyInstaller engine + electron-builder) + smoke tests: bundled engine `/health` = ready (`scripts/smoke_engine.py`) and the packaged app runs the skeleton pipeline (`app/e2e/packaged.spec.ts`); sizes in the job summary; artifacts kept 14 days | < 30 min |
| `nightly.yml` | daily on `main` and the newest `phase-*` branch | Full `check` incl. slow tests, benchmarks, determinism 1 vs N cores, e2e on 3 OS, installers incl. **macOS Intel**; opens an `S2` issue on failure | — |
| `release.yml` | version tag | Installers (Windows x64, macOS arm64 + x64, Linux x64) + checksums → GitHub Release → Zenodo | — |

### 8.1 Branches and rulesets
| Branch | Who writes | Ruleset |
|---|---|---|
| `main` | Quan merges the phase PR at each gate (merge commit); Dependabot PRs | PR required · required checks (`ci.yml` jobs, added after T0.06) · **0 approvals** (Quan is the only reviewer; CODEOWNERS routes everything to him) · block force push · block deletion |
| `phase-*` | Claude Code via `scripts/merge_step.py` (squash) | PR required · same required checks · 0 approvals · block force push · block deletion |
| `t<step>-*`, `bug-*` | Claude Code | none |
Merge methods: squash for step PRs, merge commit for `phase-N → main`. `main` changes during a phase (Dependabot) are brought into the phase branch by a `[SYNC]` PR (docs/rules/WORKFLOW.md#session-preflight).

## 9. Dependency policy
- New dependency → add a row in §1 (version line, purpose, licence) and update §11 status in the same PR; Quan approves (or automatic for listed candidates per docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.5); an open concern becomes a `docs/RISKS.md` row).
- Licences must be GPL-3.0-compatible (MIT, BSD, Apache-2.0, LGPL, GPL).
- Prefer packages with wheels for Windows, macOS (arm64 + x64) and Linux on Python 3.14; no packages that need a compiler at install time on users' machines.
- Small single-maintainer libraries: pin exact version, wrap inside block files only, keep our reference tests; if abandoned, vendor (copy with licence) or replace.
- Dependabot opens one grouped PR per ecosystem per month against `main`; Quan merges it when CI is green; it reaches the phase branch through `[SYNC]`.

## 10. Electron security checklist
`contextIsolation: true` · `sandbox: true` · `nodeIntegration: false` · no `remote` module · Content-Security-Policy restricting to `self` · no loading of remote URLs · preload exposes only a typed minimal API (engine port + token, file dialogs, print-to-PDF) · engine bound to 127.0.0.1 with token (DATA_MODEL.md §1).

## 11. Reuse register — check before building anything
Status: **candidate** (evaluate in the listed step, per docs/rules/CODING.md#reuse-first-and-estimate-before-committing) · **approved** (in §1) · **rejected** (reason recorded).
| Area / step | Candidate | Licence | What it could save | Status |
|---|---|---|---|---|
| Python package scaffold (T0.03) | `scientific-python/cookie` template; `uv init --lib` | BSD-3 / — | pyproject, ruff, pytest, pre-commit, CI patterns | approved (T0.03: cookie's ruff/pytest settings adopted in root `pyproject.toml`; `uv_build` src layout as from `uv init --lib`; the full copier template was not used — no nox/docs/CI) |
| C++ extension scaffold (T0.05) | `nanobind_example` (wjakob); `uv init --lib --build-backend=scikit` | BSD-3 / — | Working CMake + scikit-build-core + nanobind + cibuildwheel setup | approved (T0.05: nanobind_example / nanobind packaging-guide configuration — stable ABI `cp312`, `build-dir`, `wheel.packages`; `uv init --build-backend=scikit` rejected: pybind11 scaffold) |
| Electron + Vite + React scaffold (T0.04) | `create-vite` React-TS template; electron-vite or electron-forge templates | MIT | Dev server + Electron wiring | approved (T0.04: electron-vite 5 with the layout of its react-ts template; shadcn config written by hand from its manual-install guide because `shadcn init` does not detect electron-vite; electron-forge rejected: its packaging overlaps electron-builder) |
| Canvas, plots, binary previews, API types (T0.10) | `@xyflow/react`, `uplot`, `apache-arrow`, `@tanstack/react-query`, `openapi-typescript` | MIT / MIT / Apache-2.0 / MIT / MIT | Pipeline canvas, spectra plots, Arrow decoding, server state, generated API types | approved (T0.10: exact pins 12.12.1, 1.6.32, 21.2.0, 5.107.1, 7.13.0; `openapi-fetch` not used — a small typed `fetch` client is enough) |
| Process pool, BLAS limits (T0.13) | `loky` 3.7.0 + `threadpoolctl` 3.8.0 (both §1); joblib `Parallel` | BSD-3 / BSD-3 / BSD-3 | Reusable warm pool, worker initializer, BLAS thread limits | approved (T2.07: moved from the dev group into `vibechem-engine`, loky pinned `>=3.7,<3.8`, threadpoolctl in §3.1, the shim now lives in `vibechem_engine.executor.freeze`; T0.13: dev-group deps for the spike only; transitive cloudpickle constrained `<3.1.3` in the root `pyproject.toml` until 3.1.3 is two weeks old; joblib rejected: its auto-memmapping is a one-line `np.load(mmap_mode="r")` and its backend layer is what ADR-004's own scheduler replaces; loky in a frozen bundle needs the `loky_freeze_support()` shim from `scripts/bench_parallel.py`, see `docs/spikes/parallel.md`) |
| Python sidecar packaging (T0.11) | electron-builder `extraResources` + PyInstaller one-folder (common pattern) | MIT / GPL-with-exception | Bundling the engine | approved (T0.11: PyInstaller 6.21 one-folder `vibechem-engine` built by `scripts/build_engine.py` — `--collect-submodules uvicorn`, native `_core` added as a binary because the editable install hides it; electron-builder 26.18.0 `extraResources` → `<resources>/engine` + `<resources>/testdata`; renderer served from `app://vibechem`) |
| Golden-file tests (T0.07) | `pytest-regressions` | MIT | Golden data/num regression fixtures | approved (T0.07: `data_regression` stores the per-node hash file and handles `--force-regen`; `num_regression` available for metric tables in T2.13) |
| Reference datasets (T0.08) | `rdata` (reads R `.RData`/`.rds` without R) | MIT | Converting R package datasets | not a dependency (T0.08: used once in a throwaway `uv run --no-project --isolated` env to convert `gasoline.RData` to CSV; loaders use stdlib `csv` + numpy) |
| Preprocessing: MSC, SG derivatives, scaling, smoothing, some baselines (T1.07–T1.09, Phase 6) | `chemotools` (scikit-learn-style transformers) | MIT | Large part of P0 preprocessing | candidate |
| Baselines: AsLS, airPLS, arPLS, polynomial, SNIP… (Phase 6) | `pybaselines` (50+ algorithms) | BSD-3 | Almost all baseline methods | candidate |
| Kennard–Stone split (T1.10) | `kennard-stone` | MIT | KS split; SPXY may still be ours | candidate |
| Fitted state files, scikit-learn wrapper (T1.02b) | NumPy `.npy` (`allow_pickle=False`) + stdlib `json`; scikit-learn fitted-attribute convention; `skops.io` | BSD-3 / — / MIT | State save/load; generic transformer wrapper | approved (T1.02b: NumPy + json + scikit-learn, now a `vibechem-core` dependency; `skops.io` rejected — not in §1, stores whole estimators in its own schema instead of the JSON + named arrays `State` of ADR-007) |
| CV splitters (T1.11) | scikit-learn `KFold`, `GroupKFold`, `LeaveOneOut`, `RepeatedKFold` | BSD-3 | Most fold generators (venetian/contiguous are small extras) | approved (scikit-learn in §1) |
| PLS (T1.12a/b) | scikit-learn `PLSRegression` (NIPALS) | BSD-3 | PLS1/PLS2 fit/predict; VIP and SIMPLS are small additions | approved |
| EMSC, spike removal, ALS, interpolation (Phase 6) | Orange-Spectroscopy (port with header) | GPL-3.0 | Proven implementations | candidate (port) — T1.00: EMSC, spike removal, interpolation, rubber-band, normalisations, T↔A, PCA denoising → port (Phase 6); ALS/arPLS/airPLS → wrap `pybaselines` instead; full list in §11.1 |
| Preprocessing grid search (T2.10) | pengoo (Quan's local copy, port selected parts) | owner | Search logic | candidate (port; no numba) — T1.00b: pengoo provided (local `pengoo/`, git-excluded); per-function decisions for preprocessing, metrics, CV, LV rules, splits, grid search, variable selection and EDA in §11.2 |
| Wavelet denoising (P1, pengoo `wavelet_denoise`) | `PyWavelets` | MIT | DWT/IDWT kernels | candidate, approved at the Phase 1 gate 2026-11-27 (T1.00b; pengoo depends on it; not installed; check Python 3.14 wheels when the P1 step starts) |
| CSV/TSV and Excel import (T1.05) | stdlib `csv` + NumPy; `openpyxl` 3.1.5 (+ `et-xmlfile`); pyarrow CSV; pandas | PSF / MIT / Apache-2.0 / BSD-3 | Parsing, quoting, delimiter sniffing; xlsx cells | approved (T1.05: stdlib `csv` + NumPy for text tables, `openpyxl` as a `vibechem-core` runtime dependency read with `read_only=True, data_only=True, keep_links=False`; pyarrow CSV rejected by Quan — core stays free of pyarrow; pandas not needed; no `defusedxml` — the bundled expat limits entity expansion, covered by a malformed-file test) |
| JCAMP-DX (T1.06) | `jcamp` | MIT | Reader | approved; in use since T1.06 (1.3.2, wrapped in `vibechem_core/io/jcamp.py`) |
| SPC (T1.06) | port of osp `utils/spc/` (Rohan Isaac's `spc`, GPL-3.0) | GPL-3.0 | Reader | **ported in T1.06** → `vibechem_core/io/spc.py` (new LSB format only; upstream's per-subfile x decoding fixed). `spc-io` (MIT, needs pandas + pydantic, last release 2025-04) rejected as a dependency, used only as the independent reference for test values; `spc_spectra` rejected (last release 2018) |
| Quasar / Orange port source (T1.00, ADR-009 port-max) | `quasars/orange-spectroscopy` + non-Qt `biolab/orange3` | GPL-3.0-or-later / GPL-3.0+ | Preprocessing, readers, interferogram FFT, permutation test, PLS diagnostics | **port source** (never a dependency); per-module decisions in §11.1, commits pinned in `THIRD_PARTY.md` |
| Bruker OPUS (T1.06b) | `brukeropus` | MIT | OPUS reader (pure Python, NumPy only; v1.4.3, 2025-11) | approved; in use since T1.06b (1.4.3, wrapped in `vibechem_core/io/opus.py`; its docstring SyntaxWarning is silenced at import) |
| Bruker OPUS | `opusFC` (what Quasar calls) | MIT declared | OPUS reader | rejected (T1.00: compiled binary wheels only, no source distribution or public repository — cannot be reviewed or ported; a native dependency) |
| Renishaw WDF (T1.06b) | `renishawWiRE` (py-wdf-reader) | MIT | WDF reader | rejected as a dependency (T1.06b: no release or commit since 2023-01); its WDF1/XLST/DATA parsing **ported** → `vibechem_core/io/wdf.py` (MIT notice kept). rosettasciio 0.15.0 (GPL-3.0, HyperSpy) used only as the independent reference for test values |
| ENVI cubes (P2 imaging) | `spectral` (Spectral Python) | MIT | ENVI `.hdr/.raw` reader (what Quasar uses) | candidate (T1.00; v0.26, 2026-11) |
| Agilent FPA images/mosaics (P2 imaging) | `agilent-format` | MIT | Agilent `.seq/.dmt/.bsp` reader (what Quasar uses) | candidate (T1.00; v0.4.7, 2026-01) |
| Peak fitting (P1) | `lmfit` | BSD-3 | Constrained peak models (what Quasar's Peak Fit uses) | candidate (T1.00; v1.3.4, 2025-07) |
| NaN-aware reductions | `bottleneck` (Quasar uses it) | BSD-2 | Fast nanmean/nanmedian | rejected (T1.00: NumPy `nan*` functions are enough; one native dependency less) |
| X-ray absorption, nano-IR | `extranormal3`, `pySNOM` (Quasar uses them) | GPL-3.0 / GPL | XAS normalisation, SNOM readers | rejected (T1.00: outside vibrational chemometrics scope) |
Add a row whenever a step finds a new candidate, even if rejected — it prevents the same search next time.

### 11.1 Quasar / Orange port inventory (T1.00)
Sources, read with read-only `gh api` at pinned commits (also in `THIRD_PARTY.md`): **osp** = `quasars/orange-spectroscopy` `df9246d7d6d7537b18ef5852e30c6ce212ebc92c` (0.9.4, 2026-11-20), path prefix `orangecontrib/spectroscopy/`; **o3** = `biolab/orange3` `562b03c91319acd75282799edfd33bd01231bef6` (2026-11-20), path prefix `Orange/`. Licences: osp GPL-3.0-or-later, o3 GPL-3.0+ (both compatible with ours). Neither is ever a runtime dependency (ADR-009).
**Decision:** **port** = copy and adapt (recipe below) · **wrap** = call SciPy / scikit-learn / another §11 library instead (Quasar's code then serves only as a behaviour cross-check) · **skip** = not ported (reason given). **Coupling:** how tied the upstream code is to `Orange.data.Table`/`Domain` (T) or Qt/pyqtgraph (Q). Almost every osp preprocessor has the same shape — a NumPy core inside `_XxxCommon.transformed(X)` wrapped in `Preprocess` + `SelectColumn` domain plumbing — so "T: wrapper only" means the NumPy core ports cleanly and the plumbing is dropped.
Catalog references are `C§<section> <function> · <tier>` (FUNCTION_CATALOG.md; its rows have no F-IDs); PRD F-IDs are given where one applies.

**Preprocessing (osp `preprocess/`)**
| Upstream module · class | Our catalog function (+F-ID) | Decision (reason) | Coupling | Own third-party deps | Upstream tests / sample data | Target |
|---|---|---|---|---|---|---|
| `preprocess/__init__.py` · `Cut` | C§4 Range cut · P0 | port (small: inclusive bounds, unsorted axis, several ranges) | T: wrapper only | — | `tests/test_cut.py` | T1.07 |
| `__init__` · `GaussianSmoothing` | C§4 Gaussian smoothing · P0 | wrap `scipy.ndimage.gaussian_filter1d` (Quasar calls it too); port its NaN edge handling | T: wrapper only | SciPy | `tests/test_preprocess.py` | P6 preprocessing |
| `__init__` · `SavitzkyGolayFiltering` | C§4 Savitzky–Golay · P0 | wrap `scipy.signal.savgol_filter` (as Quasar does); NaN/unsorted-axis handling as behaviour reference | T: wrapper only | SciPy | `tests/test_preprocess.py` | T1.08 |
| `__init__` · `RubberbandBaseline` | C§4 Baseline: rubber-band · P0 | port (convex-hull baseline; not in pybaselines) | T: wrapper only | SciPy `ConvexHull` | `tests/test_preprocess.py`, `tests/test_editor_baseline.py` (widget) | P6 baselines |
| `concaverubberband.py` · `ConcaveRubberbandBaseline` (new in 0.9.4) | — (no catalog row) | skip for now (new, not in catalog; proposed as a P1 catalog row) | T: wrapper only | SciPy; uses a thread pool — drop | none yet | v1.1+ (P1) if accepted |
| `__init__` · `LinearBaseline` | C§4 Baseline: polynomial · P0 (degree 1 through edges / zero points) | port (small) | T: wrapper only | — | `tests/test_preprocess.py` | P6 baselines |
| `als/__init__.py` + `als/baseline.py` · `ALSP`, `ARPLS`, `AIRPLS` | C§4 Baseline: ALS, airPLS · P0 | wrap `pybaselines` (BSD-3, maintained, 50+ methods); Quasar's copy is LGPL-3.0 code from irfpy (M. Wieser, 2015) — keep only as extra regression check | T: wrapper only; `baseline.py` imports matplotlib at module level | SciPy sparse | `tests/test_als.py` | P6 baselines |
| `__init__` · `Normalize` (Vector, Area, Attribute, MinMax, SNV) | C§4 Normalisation: vector, min-max, area, by peak/attribute · P0; SNV · P0 | port (Area uses `Integrate`; Attribute = divide by a metadata column); SNV mode is our own NumPy in T1.07 | T: wrapper only; Attribute mode reads a Table column | scikit-learn `normalize` | `tests/test_preprocess.py`, `tests/test_editor_normalize.py` | P6 normalisations (SNV → T1.07) |
| `__init__` · `NormalizeReference`, `NormalizePhaseReference` | C§4 Normalisation: by reference · P0 | port | T: reference passed as Table → second input port | — | `tests/test_preprocess.py` | P6 normalisations |
| `__init__` · `Interpolate`, `InterpolateToDomain`; `utils.py` interpolation helpers | C§2 Interpolate / resample to common axis · P0 | port (NaN-aware `interp1d_with_unknowns_*`, edge filling) on top of `scipy.interpolate.interp1d` | T: wrapper + domain matching | SciPy | `tests/test_interpolate.py` | P6 data handling |
| `transform.py` · `Absorbance`, `Transmittance` | C§4 Transmittance↔absorbance · P0 | port (optional reference spectrum; log(1/R), Kubelka–Munk are ours) | T: wrapper only | — | `tests/test_conversion.py` | P6 preprocessing |
| `__init__` · `PCADenoising` | C§4 PCA denoising · P0 | port (thin layer over scikit-learn `PCA`) | T: wrapper only | scikit-learn | `tests/test_preprocess.py` | P6 preprocessing |
| `__init__` · `MNFDenoising` | — (no catalog row) | skip (not in catalog; P2 imaging candidate) | T | scikit-learn | `tests/test_preprocess.py` | — |
| `__init__` · `ShiftAndScale` | PRD Appendix A "shift"; C§4 axis shift · P1 is a different thing (x-axis) | port (intensity offset + scale, 5 lines) | T: wrapper only | — | `tests/test_preprocess.py` | P6 preprocessing |
| `__init__` · `Despike` | C§4 Spike/cosmic-ray removal · P0 | port (modified z-score of first differences, Whitaker–Hayes 2018, with window interpolation) | T: wrapper only | — | `tests/test_despike.py` | P6 preprocessing |
| `__init__` · `SpSubtract` | used by C§4 Atmospheric correction · P1 | port together with `AtmCorr` | T: reference as Table | — | `tests/test_preprocess.py` | v1.1+ (P1) |
| `atm_corr.py` · `AtmCorr` | C§4 Atmospheric H₂O/CO₂ correction · P1 | port | T: wrapper only; reference as Table | SciPy | `tests/test_atm_corr.py` | v1.1+ (P1) |
| `emsc.py` · `EMSC` (+ `npfunc.py` `Function`/`Segments`, weights `SelectionFunction`) | C§4 EMSC (basic) · P0; Extended EMSC (interferents via `badspectra`) · P1; also MSC as the order-0 special case | port | T: reference/bad spectra as Tables; `ranges` weighting | — | `tests/test_emsc.py` (some values hand-derived, "TODO find test values" in places), `tests/test_npfunc.py` | P6 preprocessing (extended options P1) |
| `me_emsc.py` · `ME_EMSC` | C§4 ME-EMSC (Mie scattering) · P2 | port | T: wrapper only | SciPy `hilbert`, scikit-learn `TruncatedSVD` | `tests/test_me_emsc.py` + `datasets/emsc/MieStd1–7` (outputs of the authors' MATLAB code — candidate independent reference, see rule 3) | P2 |
| `integrate.py` · `Integrate` (simple, edge baseline, separate baseline, peak max, peak x, at peak) | PRD Appendix A "Integrate" (v1.0 parity); no catalog row — proposed P0 row "Band integration (area, height, position)" | port | T: output = new Table columns; imports `AnyQt.QtCore.Qt` for enum only — drop | SciPy `integrate`, bottleneck → NumPy | `tests/test_integrate.py` | P6 preprocessing |
| `__init__` · `XASnormalization`, `ExtractEXAFS` | — (X-ray absorption) | skip (outside vibrational scope) | T | extranormal3 | `tests/test_xas.py` | — |
| `utils.py` · `CommonDomain*`, `SelectColumn`, `table_eq_x`, `replacex` | — (Orange plumbing) | skip (replaced by `SpectralDataset` + block contract) | T | — | `tests/test_preprocess_utils.py` | — |

**Readers (osp `io/`, `utils/` vendored readers)**
| Upstream module · reader | Our catalog function | Decision (reason) | Coupling | Own third-party deps | Upstream tests / sample data | Target |
|---|---|---|---|---|---|---|
| `io/omnic.py` · `SPCReader` + `utils/spc/` (Rohan Isaac's `spc`, GPL-3.0, commit f35b90f, 2019) | C§1 Thermo SPC · P0 | port (pure `struct` + NumPy; single-x and multi-x files) | T: reader returns Table — thin | — (matplotlib only in an unused plot method — drop) | `tests/test_readers.py`; `datasets/m_xyxy.spc` | T1.06 |
| `io/omnic.py` · `SPAReader` | C§1 Other vendor formats → proposed P1 "Thermo OMNIC SPA" | port (pure `struct`) | T: thin | — | `tests/test_readers.py`; `datasets/sample1.spa` | **ported in T1.06b** → `io/spa.py` |
| `io/opus.py` · `OPUSReader` | C§1 Bruker OPUS · P1 | wrap `brukeropus` instead (Quasar calls the closed binary `opusFC`, rejected in §11); keep Quasar's block-selection behaviour (data blocks as "sheets") | T: thin | opusFC, Pillow (visible image) | `tests/test_readers.py`; `datasets/peach_juice.0` | **wrapped in T1.06b** → `io/opus.py` |
| `io/perkinelmer.py` · `PerkinElmerReader` + `utils/specio/` (BSD-3, Lemaitre 2017 + Diamond) | C§1 Other vendor formats → proposed P1 "PerkinElmer .sp" | port (BSD-3 notice kept) | T: thin | — | `tests/test_readers.py`; `datasets/perkinelmer/single_PE_spectrum.sp` | **ported in T1.06b** → `io/perkinelmer.py` (`.sp` only; `.fsm` images P2) |
| `io/wire.py` · `WiREReaders` | C§1 Other vendor formats → proposed P1 "Renishaw WDF" | port the needed parts of `renishawWiRE` (MIT; unmaintained since 2023-01) | T: thin | renishawWiRE | `tests/test_readers.py`; `datasets/renishaw_test_files/*.wdf` | **ported in T1.06b** → `io/wdf.py` (maps P2) |
| `io/ascii.py` · `AsciiColReader` (incl. Bruker `.dpt`), `AsciiMapReader` | C§1 CSV/TSV · P0 | skip (covered by our table reader); its `;`-comment and headerless two-column rules go into T1.05 tests | T | — | `tests/test_readers.py`; `datasets/peach_juice.dpt`, `map_test.xyz` | T1.05 (behaviour only) |
| `io/matlab.py` · `MatlabReader` | C§1 MATLAB .mat · P1 | wrap `scipy.io.loadmat` (as Quasar does); port its variable-role rules | T | SciPy | `tests/test_readers.py`; `datasets/matlab/*.mat` | v1.1+ (P1) |
| `io/envi.py`, `io/meta.py` · `EnviMapReader`, `HDRMetaReader`, `DatMetaReader` | C§1 ENVI cubes · P2 | wrap `spectral` (candidate) | T | spectral | `tests/test_readers.py` | P2 |
| `io/agilent.py` · image / mosaic / IFG / tile readers | C§1 Hyperspectral cubes · P2 | wrap `agilent-format` (candidate) | T | agilent-format | `tests/test_readers.py`, `tests/test_tile_reader.py`; `datasets/agilent/` | P2 |
| `io/omnic.py` · `OmnicMapReader` + `utils/pymca5/` (MIT, ESRF) | C§1 Hyperspectral cubes · P2 | port (MIT notice kept) | T | — | `tests/test_readers.py`; `datasets/small_Omnic.map` | P2 |
| `io/ptir.py` · `PTIRFileReader` (photothermal) | C§1 Other vendor formats · P3 | skip until requested | T | h5py, Pillow | `datasets/photothermal/` | P3 (on request) |
| `io/neaspec.py`, `io/gsf.py` (nano-IR/SNOM) | — | skip (nano-IR, outside scope) | T | pySNOM, pandas | `datasets/Nea*`, `*.gsf` | — |
| `io/diamond.py`, `maxiv.py`, `soleil.py`, `cls.py` (synchrotron STXM/XAS HDF5) | — | skip (X-ray facility formats) | T | h5py | `datasets/*.nxs`, `*.xim`, `Hermes_HDF5/` | — |
| `io/util.py` · `SpectralFileFormat`, `TileFileFormat`; `data.py` · `getx`, `spectra_mean` | — (Orange plumbing) | skip (our reader interface + `SpectralDataset.axis`) | T | — | — | — |

**Other osp modules (non-widget code and compute functions inside widget files)**
| Upstream module | Our catalog function (+F-ID) | Decision (reason) | Coupling | Own third-party deps | Upstream tests / sample data | Target |
|---|---|---|---|---|---|---|
| `irfft.py` · `IRFFT`, `MultiIRFFT`, `ComplexFFT`, apodisation, zero filling, phase correction | C§4 Interferogram → spectrum · P3 | port (pure NumPy, no Orange imports) | none | — | `tests/test_irfft.py`; `datasets/IFG_single.dpt` | P3 |
| `models/pls.py` · `PLSRegressionLearner` | C§9 PLS · P0 | skip (older copy of o3 `regression/pls.py`; we wrap scikit-learn in T1.12a) | T | scikit-learn | `tests/test_owpls.py` | — |
| `widgets/owaverage.py` · `average_table` | C§2 Average replicates by group · P0 | port (logic only, ~20 lines) | T + Q (inside widget) | — | `tests/test_owaverage.py` | P6 data handling |
| `widgets/owsnr.py` · `calc_table_np` | PRD Appendix A "SNR" (v1.0 parity); no catalog row — proposed P0 row "SNR per group/position" | port (logic only) | T + Q | bottleneck → NumPy | `tests/test_owsnr.py` | P6 exploration |
| `widgets/owcos.py` · `calc_cos` (synchronous/asynchronous, Hilbert–Noda) | C§3 2D-COS · P1 | port (upstream TODO says it is not yet checked against the `corr2D` R package — that is our independent reference) | T + Q | colorcet (plot only) | `tests/test_owcos.py` | v1.1+ (P1) |
| `widgets/peakfit_compute.py`, `peak_editors.py` | C§4 Peak fitting · P1 | wrap `lmfit` (candidate); port Quasar's model/constraint set-up | Q (editors) | lmfit | `tests/test_owpeakfit.py` | v1.1+ (P1) |
| `widgets/owmultifile.py` | C§1 Multi-file import + concatenate · P0 | skip code (Qt); adopt its axis-union / file-name-column behaviour as T1.06 spec | Q | — | `tests/test_owmultifile.py` | T1.06 (behaviour only) |
| `widgets/owinterpolate.py`, `owpreprocess.py`, `owintegrate.py`, `preprocessors/*` | (UI for the preprocessors above) | skip (Qt editors; parameter ranges and defaults read when the matching block is built) | Q | AnyQt, pyqtgraph | `tests/test_editor_*.py`, `tests/test_owpreprocess.py` | with each block (defaults only) |
| `widgets/owspectra.py`, `owhyper.py` | C§3 Spectra viewer QoL · P0; C§15 Cube viewer · P2 | skip (pyqtgraph UI); feature list used as UI spec | Q | pyqtgraph | `tests/test_owspectra.py`, `tests/test_owhyper.py` | T4.08 (spec only), P2 |
| `utils/__init__.py` (hypercube helpers), `utils/binning.py`, `widgets/owbin.py`, `owreshape.py`, `owstackalign.py`, `utils/skimage/` (BSD-3 copy of scikit-image) | C§15 Hyperspectral imaging · P2 | port (BSD-3 notice kept for the scikit-image parts) | T | bottleneck → NumPy | `tests/test_owbin.py`, `test_owreshape.py`, `test_owalignstack.py` | P2 |
| `widgets/owfft.py` | C§4 Interferogram → spectrum · P3 | skip (UI over `irfft.py`) | Q | — | `tests/test_owfft.py` | P3 (with irfft) |
| `widgets/owpolar.py`, `owgate.py`, `owoverlay.py`, `owspectralseries.py`, `owtilefile.py` | — | skip (polarisation analysis, gating, image overlay, tile loading: not in catalog) | Q | — | own widget tests | — |

**Orange3 non-Qt code (o3)**
| Upstream module | Our catalog function (+F-ID) | Decision (reason) | Coupling | Own third-party deps | Upstream tests / sample data | Target |
|---|---|---|---|---|---|---|
| `preprocess/preprocess.py`, `normalize.py` · `Normalize`, `Scale`, `Continuize`, `RemoveNaN*`, `RemoveConstant`, `Randomize` | C§4 Mean-centring, autoscaling, range scaling · P0 | wrap scikit-learn scalers (Orange's are Table/Domain transformations around the same arithmetic) | T (heavy) | scikit-learn | `Orange/tests/test_preprocess.py`, `test_normalize.py` | T1.09 |
| `preprocess/impute.py` · `Average`, `Model`, `Random`, `DropInstances` | C§2 Missing values: detect, remove, impute · P0 | wrap scikit-learn `SimpleImputer` | T (heavy) | scikit-learn | `Orange/tests/test_impute.py` | P6 data handling |
| `projection/pca.py` · `PCA`, `IncrementalPCA`, `TruncatedSVD` | C§3 PCA · P0; C§11 PCA · P0 | wrap scikit-learn `PCA` (Orange does the same); T²/Q are ours | T | scikit-learn | `Orange/tests/test_pca.py` | P6 exploration |
| `clustering/hierarchical.py` · `Tree`, `prune`, `top_clusters`, `optimal_leaf_ordering` | C§3 Hierarchical clustering + dendrogram · P0 (raised by Quan 2026-11-25) | wrap `scipy.cluster.hierarchy`; port the small tree helpers (`prune`, `top_clusters`) | T (light) | SciPy | `Orange/tests/test_clustering_hierarchical.py` | Phase 6 exploration (P0) |
| `clustering/kmeans.py` | C§3 k-Means · P0 (raised by Quan 2026-11-25) | wrap scikit-learn `KMeans` | T | scikit-learn | `Orange/tests/test_clustering_kmeans.py` | Phase 6 exploration (P0) |
| `evaluation/testing.py` · `CrossValidation`, `CrossValidationFeature` (grouped), `LeaveOneOut`, `ShuffleSplit`, `TestOnTestData`, `Results` | C§6 k-fold, LOO, Monte-Carlo CV, group k-fold · P0 | wrap scikit-learn splitters (Orange does the same); runners and results are our engine (T2.10, differentiator) | T (heavy) | scikit-learn | `Orange/tests/test_evaluation_testing.py` | T1.11, T2.10 |
| `widgets/evaluate/owpermutationplot.py` · `permutation()` (compute part, no Qt in the function) | C§6 Permutation / Y-randomisation test · P0; F-45 | port (logic: shuffle Y, score on training + CV, \|r(Y, Y_perm)\|, intercept lines); replace its global `np.random.seed(0)` with a `Generator` and its fixed CV with our fold block | T | SciPy `stats` | `widgets/evaluate/tests/test_owpermutationplot.py` | P6 validation |
| `regression/pls.py` · `PLSModel.dmodx`, `_residual_ssx`, `residuals_normal_probability`, `coefficients_table` | C§14 Residuals, leverage, T²/Q influence · P0; C§16 applicability domain · P0 (F-71) | port DModX / residual SSX; fit/predict stay scikit-learn (T1.12a) | T | scikit-learn, SciPy | `Orange/tests/test_pls.py` | P6 diagnostics |
| `evaluation/scoring.py` · `CA`, `AUC`, `R2`, `RMSE`, `Specificity`, … | C§14 Confusion matrix, ROC/AUC · P0; F-44 | wrap scikit-learn metrics (Orange does the same); chemometric metrics are ours | T | scikit-learn | `Orange/tests/test_evaluation_scoring.py` | T1.14 |
| `distance/`, `statistics/`, `classification/`, `regression/` (other learners), `projection/manifold.py`, `som.py`, `freeviz.py`, `radviz.py`, `clustering/louvain.py`, `dbscan.py` | C§3 t-SNE/MDS · P1; C§9/§10 models · P0–P2; SOM, DBSCAN · P2 | skip (thin wrappers over scikit-learn/SciPy; FreeViz/Radviz/Louvain not planned — PRD Appendix A) | T | scikit-learn, SciPy | — | wrap the underlying library in the matching step |

**Port recipe** (every **port** row above)
1. **Find the NumPy core.** In osp preprocessors it is `_XxxCommon.transformed(self, data, X)`; drop `Preprocess`, `SelectColumn`, `CommonDomain*`, `Domain` and `compute_value` plumbing. In readers keep only the byte parsing that yields `x` (axis), `Y` (spectra) and metadata.
2. **`Orange.data.Table` → `SpectralDataset`.** `getx(data)` → `ds.axis`; `data.X` → `ds.X`; metas/class columns → `ds.metadata` / `ds.Y` / `ds.classes`; a reference Table → a second input port (DATA_MODEL.md §4); a new output Table → `ds.with_X(...)` or a `Table` port. Unsorted axes: keep Quasar's sort-then-restore order behaviour and test it.
3. **Block template** (docs/rules/CODING.md#block-template-and-comment-style, `block-template` skill): header docstring, typed `Param`s with Quasar's defaults unless METHODS.md says otherwise, numbered `# Step N:` comments matching METHODS.md. Global random state (`np.random.seed`) → a `numpy.random.Generator` parameter. Thread pools, `bottleneck`, matplotlib and Qt imports are removed.
4. **Source header** at the top of the file, below our SPDX line:
   `# Ported from <repo> <path> at commit <sha> (<licence>).` · `# Original copyright: <holder(s) from the upstream file/LICENSE>.` · `# Changes: <one line, e.g. "Orange Table plumbing replaced by SpectralDataset">.` Code that Quasar itself vendored (spc, specio, pymca5, scikit-image, irfpy ALS) also names the original project and keeps its licence notice (MIT/BSD text verbatim).
5. **`THIRD_PARTY.md`** "Ported or vendored code" row in the same PR: component, source path, commit, licence, our file.
6. **Tests** (rule 3 below): reference test with an independent expected value, property tests, and — optional — Quasar's own test values as extra regression checks marked as such.

**Rule 3 — reference-test independence.** Quasar's (and Orange's) own test values are **not** an independent reference for code ported from them (CLAUDE.md#hard-rules): a bug copied with the code would pass them. Every ported block needs an expected value from a paper, other software (e.g. R `corr2D` for 2D-COS, the authors' MATLAB code for EMSC/ME-EMSC, pybaselines for baselines) or a hand calculation. Quasar test values are kept only as extra regression checks, named `test_*_quasar_regression`. Exception to check case by case: `datasets/emsc/MieStd1–7` were produced by the original authors' MATLAB ME-EMSC code (Solheim et al.), not by Quasar, so they could serve as the independent reference for ME-EMSC — but their origin is **unconfirmed** (Quan, 2026-11-25: unknown). Until it is confirmed from the files' source or the Solheim et al. paper/supplement, treat them as Quasar regression data only; the ME-EMSC step (P2) must find another independent reference (published values or the authors' MATLAB code run by us) or stop `MISSING_INPUT`.

**Rule 4 — sample data licences.** osp has one repository-wide licence (GPL-3.0-or-later) and **no per-file licence or provenance notes** for `datasets/` (git history only shows the files being added or renamed). Treat them as GPL-3.0-or-later test data: allowed in our GPL-3.0-or-later repo **for tests only**, each copied file with a `testdata/` PROVENANCE entry and a `THIRD_PARTY.md` row, never shipped in installers. **Approved by Quan 2026-11-25** for this use. Vendor-produced files may carry the instrument maker's copyright underneath; that stays an open point (like the gasoline dataset).
| File (osp `datasets/`) | Format / vendor | Use | Status |
|---|---|---|---|
| `m_xyxy.spc` | Thermo Galactic SPC (multi-x); originally from `rohanisaac/spc` `test_data/` (GPL-3.0 repo) | T1.06 | approved as GPL test data (tests only) |
| `sample1.spa` | Thermo OMNIC SPA | T1.06b | as above |
| `peach_juice.0` | Bruker OPUS | T1.06b | as above |
| `peach_juice.dpt` | Bruker DPT (ASCII) | T1.05 tests | as above |
| `perkinelmer/single_PE_spectrum.sp` | PerkinElmer `.sp` | T1.06b | as above |
| `renishaw_test_files/sp.wdf`, `single-spectrum_undefined-type.wdf` | Renishaw WDF | T1.06b | as above |
| `emsc/MieStd1–7_*.csv` | ME-EMSC inputs and MATLAB outputs | P2 ME-EMSC regression data | as above; origin unconfirmed, not an independent reference (rule 3) |
| `collagen.csv` (1 MB), `small_Omnic.map`, `agilent/`, `photothermal/`, `matlab/` | FTIR table, OMNIC map, Agilent FPA, PTIR, .mat | P6/P2 | as above |
| `Nea*`, `*.gsf`, `*.nxs`, `*.xim`, `Hermes_HDF5/`, `exafs-test.tab`, `polar/` | nano-IR, synchrotron, XAS, polarisation | — | not needed |
Second SPC vendor for T1.06's "two instrument vendors": `rohanisaac/spc` `test_data/` (GPL-3.0 repo, same caveat) has SPC files from several instruments (`nir.spc`, `RAMAN.SPC`, `Ft-ir.spc`, `s_xy.spc`, `s_evenx.spc`, …). JCAMP-DX samples: `nzhagen/jcamp` `data/` (MIT repo; includes the jcamp-dx.org official test data and IR/Raman spectra) — licence of the individual files to check in T1.06.

### 11.2 pengoo port inventory (T1.00b)
Source: Quan's local copy of pengoo ("Spectroscopy Toolkit"), 7 modules, ~7,900 lines, read 2026-11-25. It lives in `pengoo/` at the repo root on Quan's machine and is excluded from git through `.git/info/exclude` (D-016: only ported parts enter the repo). A step that ports pengoo code needs that folder; if it is missing on the current machine → `MISSING_INPUT` (Quan copies it in). Owner's code, so there is no licence barrier. Ported files carry `# Ported from pengoo <module>.py (owner's code, relicensed GPL-3.0-or-later by the author).` below the SPDX line, and a `THIRD_PARTY.md` row is **not** needed. The port recipe of §11.1 applies otherwise (block template, Generator instead of global RNG, no `print`, no matplotlib).
**Rule 5 — pengoo is not an independent reference** either: values pengoo produced only serve as extra regression checks (`test_*_pengoo_regression`), and only after the fixes below are applied. Reference values come from papers, other software or hand calculations (§11.1 rule 3).
Decisions as in §11.1 (**port** / **wrap** / **skip**). **Fix** = a defect or convention clash found in pengoo that the port must not carry over; each one gets a test in the target step. Items marked **(T1.04)** are behaviour or default choices for Quan to settle in METHODS.md.

**Defects confirmed by running pengoo** (2026-11-25, scratch script, not committed):
- **D1 · MSC slope off by n/(n−1).** `msc()` divides `np.cov(x, ref)` (ddof = 1) by `ref.var()` (ddof = 0). On an exact case x = a + b·ref (50 points) the corrected spectrum should equal `ref`; pengoo is off by up to 0.013. `utils.residual()` has the same ddof mix.
- **D2 · Per-fold preprocessing refits on the validation fold.** `calculate_cv_rmse(apply_preprocessing_in_cv=True)` runs the stateless pipeline separately on `X[val_idx]`: MSC takes the validation mean as its reference, MeanCenter/Autoscaling use validation statistics. With LOO, every validation spectrum becomes all zeros after MeanCenter/Autoscaling (checked), so the reported RMSECV is wrong without warning. The same applies to any test set passed through `apply_preprocessing_pipeline`. In VibeChem, fitted blocks `fit` on training rows and `apply` to the rest (CLAUDE.md#hard-rules; leakage rules T2.05), so this cannot happen by design, but results Quan produced earlier with pengoo + LOO + centring/scaling inside CV should be re-checked.

**Preprocessing (`preprocessing.py`; needs SciPy, PyWavelets, pybaselines)**
| pengoo function | Our catalog function | Decision (reason) | Fix / improvement | Target |
|---|---|---|---|---|
| `snv` | C§4 SNV · P0 | port (4 lines) | `+1e-10` silently maps a constant spectrum to 0: raise or return NaN with a warning; ddof (pengoo 0, skeleton engine 1) **(T1.04)** | T1.07 |
| `msc(X, ref)` | C§4 MSC · P0 | port as a `fitted` block (reference = training mean, learned in `fit`); chemotools/EMSC order 0 as cross-check | D1: fit a + b·ref by least squares (`np.polyfit`/`lstsq`); optional user reference spectrum = second input port | T1.07 |
| `perform_baseline_correction('Detrend')` (pybaselines `poly` on `x_data`) | C§4 detrend · P0 | wrap/port: polynomial fitted on the real axis, not the index | pengoo falls back to the index when no axis is given; ours always has `ds.axis` | T1.07 |
| `perform_smoothing('Sav-Gol')` | C§4 Savitzky–Golay · P0 | wrap `scipy.signal.savgol_filter` (pengoo does the same) | pengoo uses `mode='nearest'`, SciPy's default is `'interp'` — default and the derivative `delta` (axis spacing) **(T1.04)**; one vectorised call instead of `apply_along_axis` | T1.08 |
| `perform_scaling('MeanCenter', 'Autoscaling')` | C§4 Mean-centring, autoscaling · P0 | wrap `StandardScaler` as `fitted` blocks | D2 (statistics must come from training rows only) | T1.09 |
| `perform_scaling('Normalization')` (per-sample min-max) | C§4 Normalisation: min-max · P0 | port into the osp `Normalize` block (it is a per-spectrum normalisation, not a column scaling) | — | P6 normalisations |
| `als_baseline_correction` (banded Cholesky, `solveh_banded`) | C§4 Baseline: ALS · P0 | wrap `pybaselines` (T1.00); keep pengoo's banded solver as a speed reference for the native/benchmark work | fixed `niter=10`, no convergence test | P6 baselines; Phase 3 benchmark |
| `perform_baseline_correction('SNIP')` (pybaselines `snip`) | no catalog row → proposed P0 mode "SNIP" of the baseline block | wrap `pybaselines` | — | P6 baselines |
| `spike_removal` (Coca-Lopez 2024, peak width + interpolation) | C§4 Spike/cosmic-ray removal · P0 | port as a second method of the despike block (next to osp `Despike`, Whitaker–Hayes) | width threshold in points → axis units; vectorise over spectra | P6 preprocessing |
| `wavelet_denoise` (batched DWT, universal/energy threshold, edge mask) | C§4 Wavelet denoising · P1 | port; needs PyWavelets (§11 candidate) | edge-zone warnings become a block warning, not strings per spectrum | v1.1+ (P1) |
| `median_denoise` | no catalog row → proposed P0 mode "median" of the smoothing block | wrap `scipy.signal.medfilt` / `scipy.ndimage.median_filter` | — | P6 preprocessing |
| `perform_*` dispatchers, `apply_preprocessing_pipeline` (fixed order scatter → baseline → denoise → smooth → scale) | — (plumbing) | skip (blocks + pipeline graph); the fixed order and the option lists become the T2.10b search space spec | unknown method names silently return a copy → our registry raises | T2.10b (spec) |

**Model metrics, CV, LV choice, splits (`model_metrics.py`)**
| pengoo function | Our catalog function | Decision (reason) | Fix / improvement | Target |
|---|---|---|---|---|
| `regression_metrics`, `calculate_metrics` (RMSE, Bias = mean(ŷ − y), SEP ddof 1, R², RPD with SD ddof 1) | F-44; T1.14 metrics | port the definitions (they match the module docstring) | missing RPIQ and slope (F-44); sign convention of bias **(T1.04)** | T1.14 |
| `_y_scale`, `to_original_units`, `convert_y` | F-44 "original units" | port the idea: Y autoscaling is a `fitted` block whose inverse is applied to predictions before metrics | pengoo needs the user to pass `y_sdev` by hand | T1.09, T1.14 |
| `validate_cv_groups`, `_split_group_variables` (several group columns combined as `A\|B`, NaN check) | C§6 Group k-fold · P0 | port | — | T1.11 |
| `make_cv_splitter`, `PredefinedFolds`, `make_fixed_folds`, `get_cv_splits` (folds materialised once, group-leak assertion) | C§6 k-fold, LOO, group k-fold · P0 | port the behaviour on scikit-learn splitters; folds = the `Folds` port (DATA_MODEL §4) | fixed `random_state=69` → `Generator`; `GroupKFold(shuffle=True)` needs scikit-learn ≥ 1.6; "int ≥ n → LOO" rule **(T1.04)** | T1.11 |
| `calculate_cv_rmse` (fold loop, `fold_mean` vs `pooled` RMSECV, per-fold SD/SE, PRESS) | C§6/§7; T2.10a CV runner | port the aggregation rules; the loop is our engine | D2; default RMSECV aggregation (pengoo `fold_mean`, chemometrics usually pooled) **(T1.04)** | T1.14 (formulas), T2.10a |
| `_predict_pls_at_lv` (grid search), `_predict_at_lv` (variable selection) — predictions for every LV count from one fit | T1.12a "LV sweep from one fit" | port | two copies → one function; test "sweep = separate fits" | T1.12a |
| `PLSRegression(n_components)` everywhere | C§9 PLS · P0 | — (T1.12a wraps scikit-learn) | scikit-learn's default `scale=True` autoscales X without telling: every pengoo PLS result was on autoscaled X. VibeChem default (mean-centre only, scaling as a visible block) **(T1.04)** | T1.12a |
| `calculate_vip` | C§8 VIP · P0 | port (standard formula on `x_weights_`, `x_scores_`, `y_loadings_`) | PLS1 only; PLS2 VIP **(T1.04)**; independent reference value needed | T1.12b |
| `calculate_selectivity_ratio` (target projection) | C§8 Selectivity ratio · P0 | port | `+1e-10` guards; check against Rajalahti et al. 2009 | P6 variable selection |
| `_wold_r_criterion`, `select_n_components`, `check_selection_rule`, `find_knee` (global min, 1-SE, paired t-test, Wold R) | C§7 LV-number rules · P0 | port | t-test α fixed at 0.05 → parameter; unknown rule raises (keep); `1se`/`ttest` need per-fold errors (keep the check) | T2.10a |
| `_ks_order`, SPXY distance (`Dx/max + Dy/max`), `_duplex_order` | C§5 Kennard–Stone, SPXY, Duplex · P0 | port (short); cross-check KS with the `kennard-stone` package | pengoo measures distances on PCA scores of unit means (99 % variance), the classic KS/SPXY use raw X **(T1.04)**; Duplex is in C§5 P0 but not in T1.10 — proposed addition | T1.10 |
| `split_cal_test` (strata + sampling units kept whole, `rank_rotate`, `protect_extremes`) | C§5 by group, Y-stratified · P0 | port unit-preserving and stratified selection as T1.10's "group-aware option"; `rank_rotate` and `protect_extremes` → proposed P1 catalog row | `print` report → result table | T1.10; v1.1+ (P1) |
| `validate_models` (ISO 12099 bias t-test and slope test, van der Voet randomisation test, Pitman–Morgan, F-test, Brown–Forsythe, Welch, bootstrap CI of ΔRMSEP, Holm, tests on unit means) | C§13 Model comparison (van der Voet) · P0; C§13 multiple-testing, bootstrap CIs · P1; proposed P0 row "Bias and slope tests (ISO 12099)" | port | `n_perm=9999`, `n_boot=2000` defaults **(T1.04 / P6)**; already uses `default_rng` (keep, pass a `Generator`) | P6 validation |

**Preprocessing grid search (`grid_search.py`)**
| pengoo function | Our catalog function | Decision (reason) | Fix / improvement | Target |
|---|---|---|---|---|
| `generate_all_method_combinations_optimized`, `count_combinations_per_step_type`, `_step_identity`, `_pipeline_sort_key` (fixed-order product, dedup, deterministic order) | C§7 Preprocessing chain grid search · P0 | port the logic; option lists become a default search-space file (JSON) built from registered blocks | pipeline identity = our content hash (T2.06) | T2.10b |
| `pls_cv_score_single_pipeline`, `_evaluate_pipeline_chunk` (shared folds, LV sweep per fold, chunked) | C§7 · P0 | port the scoring; parallelism = our executor (T2.07, loky); joblib rejected (§11) | D2 | T2.10b |
| `load_pipelines_from_excel` (`ast.literal_eval` of a params cell) | C§7 user-defined pipelines | port as an option reading a pipelines table through the T1.05 reader | JSON params instead of Python literals | T2.10b |
| random subsample of pipelines (`max_combinations`) | C§7 Random search · P1 | port | global `np.random.seed(42)` → `Generator` | v1.1+ (P1) |
| `save_results_to_file`, `save_checkpoint`, `load_checkpoint` | — | skip: pickle (CLAUDE.md#hard-rules) and a hard-coded user Desktop path; replaced by the cache (T2.06) and crash recovery (T2.09) | — | — |

**Variable selection (`variable_selection.py`)** — all receive pengoo-preprocessed X; the module documents that preprocessing is fitted once on the whole training set before selection (optimistic RMSECV, deliberate). Whether VibeChem offers that mode next to selection inside CV is **(P6 step, Quan)**.
| pengoo function | Our catalog function | Decision (reason) | Fix / improvement | Target |
|---|---|---|---|---|
| `SubsetCV`, `_make_scorer` (one fold set for all subsets, `n_components='auto'` per subset) | C§8 Selection inside CV · P0 | port as the shared scorer of the variable-selection blocks | — | P6 variable selection |
| `vip_variable_selection` | C§8 VIP · P0 | port | — | P6 |
| `jackknife_variable_selection` (Martens & Martens 2000) | C§8 Regression coefficients + jackknife · P0 | port | independent reference needed (Unscrambler or the paper) | P6 |
| `successive_projections_algorithm` (Araújo 2001) | C§8 SPA · P0 | port | starts only from the variable with the largest \|r\| and has no validation of the subset size; the paper tries every start variable and picks by validation error — check and fix | P6 |
| `competitive_adaptive_reweighted_sampling` | C§8 CARS · P0 | port | global `np.random.choice` → `Generator`; Monte-Carlo sample subsets and the exponential decay function of Li et al. 2009 are simplified — align with the paper | P6 |
| `stepwise_selectivity_ratio` | C§8 SWSR · P1 | port | — | v1.1+ (P1) |
| `sparse_pls_variable_selection` (Lê Cao 2008) | C§8 sPLS · P1 | port | — | v1.1+ (P1) |
| `ant_colony_optimization_variable_selection`, `aco_with_convergence_detection` | C§8 ACO · P1 | port as one block with an early-stop option | global RNG → `Generator` | v1.1+ (P1) |
| `synergy_interval_pls` (Nørgaard 2000) | C§8 siPLS · P1 (iPLS forward/backward P0 is not in pengoo — build) | port | — | v1.1+ (P1) |
| `moving_window_pls` (Jiang et al. 2002) | no catalog row → proposed P1 row "MW-PLS" | port | — | v1.1+ (P1) |
| `run_all_variable_selection_methods` | — (orchestration) | skip: the pipeline graph runs several blocks; the stability map is ours | global `np.random.seed` | — |

**EDA, plotting, utilities (`eda_spectra.py`, `plotting.py`, `utils.py`)** — interactive `input()` + matplotlib code; nothing is ported as is, the compute parts are.
| pengoo function | Our catalog function | Decision (reason) | Fix / improvement | Target |
|---|---|---|---|---|
| `_pearson_profile`, `_split_by_sign` | C§3 Correlation spectrum · P0 | port (r per wavelength) | — | P6 exploration |
| `_plot_spectral_stats` (mean, SD, skewness, kurtosis per wavelength), `_plot_class_tests` (Shapiro, Levene, ANOVA, Kruskal per wavelength), `_plot_spectral_difference`, `_plot_sample_corr` | C§3 exploration; C§13 tests · P0 | port the computations into exploration/statistics blocks | per-wavelength tests need multiple-testing correction (C§13 P1) | P6 exploration / statistics |
| `_fit_pca`, `_plot_outlier_diagnostics` (T², Q with Jackson–Mudholkar limit, leverage) | C§3 PCA · P0; C§14 T²/Q influence · P0 | port T²/Q/leverage | T² limit uses the new-observation F formula for calibration samples (should be the Beta-distribution limit); fall back to the 95th percentile silently → warning | P6 diagnostics |
| `_compare_datasets` (train vs test distributions) | C§3 (no row) | spec only (comparison view) | — | P6 exploration (spec) |
| `_export_report` (Markdown report) | C§16 report | spec only | — | P6 reporting (spec) |
| `plot_measured_vs_predicted`, `draw_metrics_table`, `plot_residuals`, `plot_scree`, `plot_coefficients_vip_sr`, `plot_variable_selection_results` | C§14 plots · P0; C§3 publication presets · P0 | skip code (our plots are uPlot in the UI); layouts and metric tables are the UI spec | — | Phase 4 / P6 plot views (spec) |
| `utils.colormap` (spectra coloured by Y) | C§3 spectra viewer: colour by variable · P0 | spec only | — | Phase 4 viewer (spec) |
| `utils.stack_second_columns_to_dataframe` (folder of two-column `.txt` files → table) | C§1 Multi-file import + concatenate · P0 | spec for T1.06 multi-file | `os.listdir` order is unsorted and axes are not compared — ours sorts names and checks the axis | T1.06 (behaviour only) |
| `utils._as_1d`, `standardize`, `residual`, `extract_features` | — | skip (covered by `SpectralDataset` validation and the blocks) | `residual` has D1's ddof mix | — |

## 12. Known packaging pitfalls (check in T0.11, T0.13)
- **PyInstaller + process pools:** frozen apps must call `multiprocessing.freeze_support()` and use the spawn start method; loky workers inside a frozen bundle must be tested on Windows in the walking skeleton. T0.13: loky 3.7 workers do **not** start in a PyInstaller bundle with `freeze_support()` alone (workers die at start-up on all three OS); the entry script must first route loky's worker and resource-tracker command lines (`loky_freeze_support()` in `scripts/bench_parallel.py`, `docs/spikes/parallel.md`).
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
