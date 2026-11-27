# VibeChem — Architecture (system design + decision records)

> Status: v0.4 · Last updated: 2026-11-26 · Decider: Quan (owner)
> v0.4 (tooling v0.5): K removed from the workflow; ADR-003…009 set from `Accepted (provisional)` to `Accepted` (Quan accepted them at the Phase 0 gate); reviews = Quan + agents (docs/QA.md#8-review-checklists).
> v0.3: ADR-009 (reuse first), D-021, packaging risks in §6, PDF reports produced by the desktop app only.
> Contents: §1 Requirements · §2 High-level design · §3 Deep dive · §4 Scale · §5 Options considered · §6 Trade-offs & revisit list · §7 Architecture Decision Records · §8 Technical decision log
> Exact versions/folders: TECH_STACK.md · Exact fields/endpoints: DATA_MODEL.md · Tests: QA.md

## 1. Requirements

### 1.1 Functional (summary — full list in PRD.md and FUNCTION_CATALOG.md)
Import spectral data · build analyses as a typed multi-port block graph (DAG) on a canvas · inspect output at any block · incremental, parallel, leakage-safe runs with nested validation · save/load projects, pipelines, templates · export models, reports, Python scripts · EN/JA/VI with student tooltips.

### 1.2 Non-functional targets
| Area | Target |
|---|---|
| Data size (v1) | 50–5,000 spectra × 200–4,000 variables (≤ ~160 MB float64) |
| Data size (imaging, P2) | Cubes 0.5–10 GB, out-of-core |
| Interactive preview | Single-block change → preview < 300 ms for 2,000 × 2,000 |
| Plot redraw | < 100 ms for 2,000 spectra (server-side decimation) |
| Canvas | Smooth at 200 blocks |
| Progress events | ≥ 1 per second during jobs |
| Parallel speed-up | ≥ 4× on 8 cores for nested CV |
| Reproducibility | Identical metrics for any core count; across OS within METHODS.md tolerance |
| Hardware floor | 8 GB RAM, 4-core laptop |
| Start-up | < 5 s (warm) |
| Installer | < 400 MB per OS (see TECH_STACK.md §12 for size risks) |
| Network | Fully offline; no data leaves the machine unless exported |
| Robustness | A failing block or native kernel never closes the app or loses the project |

### 1.3 Constraints
One part-time owner (Quan) working with AI agents · ≈80–90 % AI-generated code · zero budget · Windows, macOS (Intel + Apple Silicon), Linux · GPL-3.0-or-later · docs must let a newcomer continue the project alone · reuse existing open-source code before building (ADR-009).

## 2. High-level design

### 2.1 Process model
```
┌──────────────────────── User's computer (offline) ─────────────────────────┐
│  Electron main (TypeScript): window, menus, file dialogs, update check,    │
│  print-to-PDF; starts / supervises / restarts the engine;                  │
│  hands port + token to renderer                                            │
│        │ spawn + health check                                              │
│        ▼                                                                   │
│  Engine process (Python) ◄── HTTP + WebSocket on 127.0.0.1:<random> ──┐    │
│   ├─ API (REST, WS events, binary data)                                │    │
│   ├─ Block registry (metadata → UI schema)                             │    │
│   ├─ Graph compiler (user DAG → task graph; expands CV folds)          │    │
│   ├─ Scheduler (core budget, memory guard, seeds, cancel)              │    │
│   ├─ Cache store (content-addressed, on disk)                          │    │
│   └─ Project store (folder read/write, migrations)                     │    │
│        │ tasks; large arrays shared via memory-mapped files            │    │
│        ▼                                                               │    │
│  Worker processes ×N (Python blocks + C++ kernels, GIL released)       │    │
│                                                                        │    │
│  Renderer (React, sandboxed): canvas, inspector, plots, jobs ──────────┘    │
└────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 "Run" data flow
1. Renderer sends the pipeline to `POST /runs`.
2. Engine validates (schema, port types, cycles, required inputs, leakage).
3. Compiler builds the task graph: fitted blocks → *fit* + *apply* tasks; CV/nested CV → per-fold sub-graphs; grid search → candidate branches.
4. Cache key per task = hash(block id, block version, parameters, input keys, seed); hits skipped.
5. Scheduler dispatches ready tasks within core and memory budgets.
6. Workers write outputs to the cache (`.npy` / Arrow / Parquet), return keys + small summaries.
7. Engine emits WebSocket events (node state, progress, logs) with sequence numbers.
8. Renderer requests previews only for visible blocks (decimated binary data).
Endpoint and event fields: DATA_MODEL.md §2–3.

### 2.3 Storage — project folder, no database
```
HoneyNIR.vibechem/
  project.json           manifest (format version, datasets, pipelines)
  data/                  imported data: Parquet (tables), .npy (matrices)
  pipelines/*.vcp.json   pipeline files (JSON Schema validated)
  cache/                 content-addressed results + index (size cap, LRU)
  models/*.vcm           zip: manifest.json + .npy arrays (no pickle)
  reports/               HTML (engine) and PDF (desktop app print-to-PDF)
```
Sharing: "Export project" → `.vcz` zip (cache optional). Imaging (P2): chunked Zarr or memory-mapped `.npy`, tiled processing.

## 3. Deep dive

### 3.1 Block model
One Python class per function: ports, typed parameters, references, tooltip keys, icon, `fitted`, `version`. Fitted blocks implement `fit(train) -> State` and `apply(State, data)`; stateless blocks implement `apply` only. State must serialise to JSON + arrays (ADR-007). UI forms are generated from the parameter schema; a few blocks may add a custom React panel (ADR-005). A block may call an external library internally (ADR-009); the block file is the only place that library is imported.

### 3.2 Leakage safety by construction
Inside a fold context, the compiler wires a fitted block's `fit` task to training indices only and its `apply` task to train and validation indices. Any connection that would feed validation/test rows into a `fit` task is rejected at compile time (`PIPELINE_LEAKAGE`). A synthetic leakage test suite runs in CI (QA.md §3).

### 3.3 Caching and incremental runs
Content-addressed: a parameter change alters that task's key and all downstream keys; upstream results stay cached. Fold-level reuse: preprocessing fitted on fold k is shared by all models evaluated on fold k in a grid search. A block's cache key includes its `version`; upgrading a wrapped library bumps the block version when results change.

### 3.4 Parallel execution
Process pool (loky), warm workers · one core budget owned by the scheduler (parallel across tasks *or* inside a C++ kernel, never both at full width) · BLAS threads = 1 per worker (threadpoolctl) · per-task memory estimate; concurrency lowered when the free-RAM budget is exceeded · one root seed per run, `SeedSequence.spawn` per task · large inputs passed as memory-mapped files · frozen app calls `multiprocessing.freeze_support()` first (TECH_STACK.md §12).

### 3.5 Events and state sync
Events carry run id + increasing sequence number. On a gap, the renderer calls `GET /runs/{run_id}` to resync.

### 3.6 Failure handling
| Failure | Behaviour |
|---|---|
| Invalid input/parameters | Typed error → node `error`, translatable message key + suggestion |
| Python exception in block | Node `error`; traceback in log; independent branches continue |
| Native kernel crash | Worker dies → task retried once with the Python reference; `native.fallback` event; logged (and a `docs/RISKS.md` row if it recurs) |
| Out of memory | Concurrency lowered, retry; then error with advice |
| Engine crash | Electron restarts engine, reopens project; cache and pipelines intact; banner in UI |
| Cancel | Cooperative flag; stuck workers terminated and replaced after timeout |
| Corrupt cache entry | Checksum mismatch → discard and recompute |
| Reused library changes behaviour | Version pinned; reference tests (independent expected values) fail in CI before users see it |

### 3.7 Security
Engine on 127.0.0.1 only, random port, per-launch token, Origin check (dev server origin allowed only in dev mode), no wildcard CORS · Electron hardening (TECH_STACK.md §10) · no pickle in any file · JSON schema validation and size limits on imports · P1 script block requires an explicit trust prompt · secret scanning on the repo.

### 3.8 Versioning and extensibility
Blocks carry semantic versions; pipelines record them; migrations upgrade old files · project/pipeline formats versioned · registry can later load third-party blocks via Python entry points · scheduler talks to an executor interface (remote/HPC executors possible later) · same Engine API for the future web Lite edition (PDF export there would need a server-side renderer).

## 4. Scale estimates
| Workload | Estimate | Design response |
|---|---|---|
| 2,000 × 2,000 float64 | 32 MB | In memory; memory-mapped to workers |
| Nested CV 10 × 10 × 20 LVs × 50 preprocessing candidates | ≈ 100,000 PLS fits | Fold-level preprocessing cache; LV sweep from one fit; parallel folds |
| Cube 1,000 × 1,000 × 256 float32 | ≈ 1 GB | Out-of-core tiles; parallel pixel prediction |
| 2,000 spectra on screen | 4 M points | Decimation to plot width; density mode above 500 spectra |
Monitoring: local structured logs (JSON lines, rotating), "Copy diagnostics". No telemetry in v1.

## 5. Architecture options considered
| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **A. Electron + Python engine + C++ kernels** | Modern UI; Python science ecosystem; API reusable for web Lite; clean review split | Two runtimes to package; IPC layer | **Chosen** |
| B. Pure Python desktop (PySide6/Qt) | One language, no IPC | Harder to reach the minimalist canvas UI; no web path | Rejected |
| C. Browser UI + local Python server (no Electron) | Smallest install; becomes web Lite easily | Less app-like; limited file dialogs | **Fallback** if Electron packaging fails |
| D. Pyodide (Python in WebAssembly) | Single runtime | Slow, memory-limited, poor parallelism, C++ hard | Rejected |
| E. Whole engine in C++ | Fastest | Algorithms not reviewable by Quan; slow development | Rejected |
| F. Extend Orange/Quasar as an add-on | Huge existing feature set | Qt UI, single-port widgets, their architecture limits our core differentiators (multi-port DAG, nested CV, parallel scheduler) | Rejected as a base; **port algorithms** from it under GPL (ADR-009) |

## 6. Trade-offs and what to revisit
- Two processes + HTTP cost a few ms per call but give crash isolation, independent testing and web reuse.
- No database keeps projects inspectable and git-friendly; no multi-user access (out of scope).
- Process pool costs memory per worker; memory-mapped inputs limit the overhead.
- Schema-generated UI limits per-block UI freedom but makes adding a block a Python-only task.
- Wrapping libraries saves effort but adds dependencies that can be abandoned or change numbers (R-17); block-level isolation and pinned versions keep each one replaceable.
- **Packaging risks** (details TECH_STACK.md §12): PyInstaller + spawn-based workers need `freeze_support`; installer size (Electron + Python + SciPy) may exceed 400 MB; macOS needs separate arm64/x64 builds; Windows long paths. All must be proven in the walking skeleton (T0.11), not later.

Revisit as VibeChem grows: remote/HPC executor · plugin sandboxing · GPU kernels and their share of the core budget · web Lite (auth, job queue, quotas, server-side PDF) · cache format if imaging dominates · option C if Electron becomes a maintenance burden.

## 7. Architecture Decision Records
Format: Status · Date · Context · Options · Decision · Consequences · Action items. An ADR is **Accepted** only when Quan signs off.

### ADR-001 Desktop shell — Electron
**Status:** Accepted · 2026-11-17
**Context:** Cross-platform window around a React UI that starts a Python engine; ease of learning prioritised.
**Options:** Electron (TypeScript only, mature, large installer) · Tauri v2 (small, needs Rust) · PySide6 (one language, no web reuse).
**Decision:** Electron. Shell performance barely affects compute speed; learning cost dominates.
**Consequences:** One language across UI and shell; larger installer; security settings must be correct (TECH_STACK.md §10). Revisit Tauri or option C if installer size blocks adoption.
**Actions:** walking skeleton proves Electron + engine packaging on 3 OS (TASKS.md T0.11).

### ADR-002 Compute — Python engine and blocks, C++20 kernels
**Status:** Accepted · 2026-11-17
**Context:** Algorithms must be reviewable by Quan (Python) and fast; native code needs a careful C++ review (cpp-reviewer, TECH_STACK.md §5).
**Options:** Python + C++ · Python + Rust (safer, but a less familiar language to review) · all-C++ engine · Julia.
**Decision:** Python for engine and blocks; C++20 only for profiled hotspots, each with a Python reference, an equivalence test and automatic fallback.
**Consequences:** Reviewers work in their strongest language; C++ wheel builds and memory-safety discipline required (sanitizers, clang-tidy).

### ADR-003 UI ↔ engine transport — local HTTP + WebSocket
**Status:** Accepted · 2026-11-24 (proposed 2026-11-17)
**Context:** Commands, frequent progress events and large numeric arrays; reuse for web Lite.
**Options:** A. HTTP + WS on 127.0.0.1 (debuggable, web-reusable, local port) · B. stdio JSON-RPC via Electron main (no port, poor for binary, no web reuse) · C. ZeroMQ/gRPC (more complex).
**Decision:** A, hardened with random port, per-launch token, Origin check; binary endpoints for arrays.
**Consequences:** Engine testable from pytest/curl; OpenAPI → generated TS types. Revisit B as fallback transport if loopback servers are blocked by antivirus in user reports.
**Actions:** transport spike (T0.12): 2,000 × 2,000 preview < 300 ms on 3 OS — done: worst 207 ms (`docs/spikes/transport.md`). Phase 4: vectorised/native decimation (≤ 50 ms server time), one list column for many lines, density layout into DATA_MODEL.md §2.8. stdio stays the documented fallback.

### ADR-004 Parallel execution — own scheduler over a process pool
**Status:** Accepted · 2026-11-24 (proposed 2026-11-17)
**Context:** Nested, embarrassingly parallel work; determinism; 8 GB laptops; C++ kernels may want threads.
**Options:** A. own scheduler + loky (full control, small) · B. Dask local (heavier, partial budget control) · C. Ray (large install) · D. raw multiprocessing (more code).
**Decision:** A, behind an executor interface so Dask/Ray/HPC executors can be added later.
**Consequences:** Exact control of core budget, memory guard and seeds; scheduler code is ours to maintain with high test coverage. This is a deliberate "build" under ADR-009: the budget/memory/seed requirements are the differentiator and no existing library meets them without heavy wrapping.
**Actions:** parallel spike (T0.13) incl. Windows spawn — done: 2.1–2.2× at 4 workers, bit-identical to serial on 3 OS and frozen (`docs/spikes/parallel.md`). Executor step: `loky_freeze_support()` in the engine entry (frozen loky fails without it), loky `>=3.7,<3.8`, frozen executor test in `installers.yml`, fixed BLAS width per task, memmap above a size threshold, `VECLIB_MAXIMUM_THREADS=1` on macOS, cross-machine checks by tolerance. Determinism test in nightly CI.

### ADR-005 Blocks define the UI (schema-driven, optional custom panels)
**Status:** Accepted · 2026-11-24 (proposed 2026-11-17); review again at the Phase 4 gate
**Context:** ~90 P0 blocks, mostly AI-generated; hand-built UI per block would not scale.
**Options:** fully schema-driven · hand-built panel per block · hybrid.
**Decision:** Hybrid — inspector generated from block metadata; custom React panel only for interactions forms can't express (ROI drawing, peak picking, range brushing).
**Consequences:** Adding a block is Python-only; schema must be expressive (DATA_MODEL.md §5). If > 10 % of blocks need custom panels, extend the schema instead.

### ADR-006 Project storage — folder + content-addressed cache, no database
**Status:** Accepted · 2026-11-24 (proposed 2026-11-17)
**Options:** project folder (inspectable, git-friendly, per-file corruption) · single SQLite file · single HDF5 file.
**Decision:** Project folder; `.vcz` zip export for sharing.
**Consequences:** Relative paths only; revisit single-file default if users ask for it.

### ADR-007 No pickle in any shareable file
**Status:** Accepted · 2026-11-24 (proposed 2026-11-17)
**Context:** Shared pickle files can execute code on load.
**Decision:** Pipelines = schema-validated JSON; models = zip of `manifest.json` + `.npy` (`allow_pickle=False`); fitted block state must serialise to JSON + arrays (part of the block contract).
**Consequences:** Safe sharing; every fitted block implements explicit state serialisation — including blocks that wrap library objects (e.g. a scikit-learn PLSRegression): their state is extracted to arrays, never pickled. In-memory pickling of task arguments sent to loky workers (cloudpickle IPC, never written to a project or shared file) is allowed.

### ADR-008 Walking skeleton before depth
**Status:** Accepted · 2026-11-24 (proposed 2026-11-17); outcome achieved in Phase 0
**Context:** Packaging Python + C++ + Electron was the riskiest integration and was scheduled late.
**Decision:** Phase 0 builds one trivial block end-to-end (C++ stub → engine → API → canvas → Electron → installers for 3 OS in CI); later phases thicken one layer at a time.
**Consequences:** Packaging problems surface in weeks, not months; Phase 0 grows by ~1 week. The temporary `/skeleton/run` endpoint (DATA_MODEL.md §2.12) is removed in T4.01.

### ADR-009 Reuse first, build last
**Status:** Accepted · 2026-11-24 (proposed 2026-11-18)
**Context:** ≈80–90 % of code is AI-generated. An AI agent tends to write everything from scratch, which wastes money and review time and produces less-tested code than mature libraries. Many needed pieces already exist under compatible licences (scikit-learn, SciPy, chemotools, pybaselines, kennard-stone, project templates, Orange-Spectroscopy).
**Options:**
| Option | Effort | Quality risk | Dependency risk |
|---|---|---|---|
| A. Build everything | Highest | Highest (new, untested code) | None |
| B. Reuse first: reuse > wrap > port > build, with an estimate before each step | Lowest | Low, if reference tests are independent | Medium (pins + isolation in block files) |
| C. Depend heavily on one big framework (e.g. Orange) | Low at first | Low | High — its architecture limits our differentiators |
**Decision:** B. Before each step Claude Code searches for existing options, judges them (licence GPL-compatible, maintained, tested, size), and writes an estimate table (docs/rules/CODING.md#reuse-first-and-estimate-before-committing). Order of preference: **reuse** (call a library as is) > **wrap** (a block around a library call) > **port** (copy and adapt code with source header and `THIRD_PARTY.md` entry) > **build**. Building when a listed candidate exists needs Quan's approval. External chemometrics libraries are imported only inside block files (import-linter rule, TECH_STACK.md §3.1). Every wrapped function still gets a reference test whose expected value comes from an independent source (paper, other software, hand calculation).
**Consequences:** Less code to write and review; faster phases; more dependencies to pin and watch (R-17); estimates become a tracked metric (QA.md health metrics). Some core pieces stay deliberately "build" because they are the differentiator (scheduler, graph compiler, leakage checks — ADR-004).
**Quasar port-max (2026-11-24, Phase 0 gate):** Quasar (orange-spectroscopy + the non-Qt parts of Orange3, both GPL-3.0) is the **first port source** for spectroscopy algorithms and file readers. Every relevant Quasar/Orange function is inventoried (T1.00) and, where it fits, ported into our blocks: `Orange.data.Table` replaced by NumPy + `SpectralDataset`, source header + `THIRD_PARTY.md`, block template. Quasar/Orange is **never a runtime dependency** — orange-spectroscopy pulls in Orange3, AnyQt, pyqtgraph and network libraries (httpx, requests, serverfiles), which conflict with the no-network rule and the installer budget. Building on Quasar as the app base (§5 option F) stays rejected. Ported code still gets reference tests from an independent source; Quasar's own tests count only as extra regression checks.
**Actions:** reuse register in TECH_STACK.md §11; reuse scan + estimate in every plan; reuse ratio and estimate accuracy reviewed at each phase gate; Quasar port inventory (TASKS.md T1.00).

### ADR-010 Coded warnings from blocks; where error and warning definitions live
**Status:** Accepted · 2026-11-27, Phase 1 gate (proposed 2026-11-26; Quan approved the direction for T1.08)
**Context:** METHODS.md N4 needs a block to report a non-fatal, coded condition (`BLOCK_AXIS_NOT_UNIFORM`) while still returning its output; T1.09 (N3) and later blocks need the same. Until now `Block.apply` returns outputs only and `vibechem_core.errors` defines exceptions only. Readers report warnings as return data (`TableImport.warnings`, DATA_MODEL.md §2.5), which a block cannot do without changing the block contract. A second question came with it (Quan): should error and warning definitions for all modules live in one central place, or be grouped per module / block family?
**Options — channel:** A. stdlib `warnings.warn` with a coded `VibeChemWarning(UserWarning)`; the engine records them · B. a `warnings` list in the block's return value (changes the block contract and every block) · C. a context object or logger passed into `apply` (new contract argument; logging has no `code`/`params`).
**Options — placement** (what is defined where: classes, code constants, the registry of codes, message keys):
| Option | Discoverability | Single source of truth (DATA_MODEL §7, i18n keys) | Duplicate / clashing codes | Imports and boundaries | Engine collection | Cost now |
|---|---|---|---|---|---|---|
| P1. Everything central: all classes **and** all code constants in `errors.py` | One file to read | Two lists to keep in step (`errors.py` + §7) | Easy to spot in one file | Every module imports `errors.py` already; no cycle | Same as P3 | Move ≈ 15 constants out of `block.py`, `io/table.py`, `blocks/preprocess/__init__.py` and their importers; one shared file every step edits (merge conflicts) |
| P2. Everything per family: each area (`io/`, `blocks/preprocess/`, engine modules) defines its own warning/error **classes** and codes, with a central index | Classes scattered; the index must be maintained | Index + §7 + modules: three places | The index must catch clashes | Families may need each other's classes (cross-family imports); engine must know every family class or a shared base anyway | Engine catches a shared base, so the per-family classes add nothing | New classes per family; existing `BlockInputError` etc. split up |
| **P3. Split by kind (current rule, written down):** classes central in `vibechem_core/errors.py` (`VibeChemError` family, `VibeChemWarning`); each **code constant** in the module that raises it, as DATA_MODEL §7 "Defined in" already lists; **DATA_MODEL §7 the single registry** of codes and their kind (error / warning) | Search for the code finds the constant next to the code that raises it (QA.md §5); §7 lists all | §7 only; message keys are derived from the code (`errors.`/`warnings.` + area + name), never typed by hand | §7 is one table, `test_errors.py` already parses it; area prefixes (`BLOCK_`, `IMPORT_`) keep families apart | `errors.py` imports nothing from VibeChem; `vibechem_core` modules import it, `vibechem_engine` may import core (TECH_STACK §3.1) — no new edge, import-linter unchanged | Engine catches `VibeChemError` / records `VibeChemWarning` — two base classes, whatever module raised them | None: matches the existing code |
**Decision:** Channel **A**: blocks call `warnings.warn(VibeChemWarning(code, params), stacklevel=2)` and return normally. `VibeChemWarning` carries `code`, `message_key` (`warnings.<area>.<name>`) and `params` like `VibeChemError`, and pickles by code + params so warnings recorded in a loky worker reach the scheduler. Placement **P3**: classes central, code constants local to the raising module, DATA_MODEL §7 the only registry (rows marked *warning* / *warning (node)*). The block contract (`Block.apply` signature and return) does not change.
**Rejected:** B and C change the block contract for every block. P1 creates a second list beside §7 and an edit hotspot for every step, and costs a move of existing codes for no gain in correctness. P2 multiplies classes the engine cannot use beyond a shared base, and needs a third list (the index).
**Consequences:** A block warning is invisible unless the caller records it: the engine (T2.04/T2.08) wraps each block call in `warnings.catch_warnings(record=True)` with `simplefilter("always")` (Python's default filter shows a warning once per code location) and turns each `VibeChemWarning` into a `severity: "warning"` node issue / `log` event; other warnings stay `log` events. Tests use `pytest.warns(VibeChemWarning)`. Code constants stay where they are; nothing moves.
**Actions:** T2.04 proposes the exact DATA_MODEL §3 event fields for node warnings (`code`, `message_key`, `params`) and implements the recording. Follow-up (optional, small): a registry consistency test — every `UPPER_SNAKE` code constant in `vibechem_core`/`vibechem_engine` has exactly one §7 row and vice versa (PROGRESS.md notes). Open review item: `docs/RISKS.md` R06.

## 8. Technical decision log (one line each, newest first)
| ID | Date | Decision |
|---|---|---|
| D-025 | 2026-11-27 | Phase 1 gate: ADR-010 accepted; `METRIC_UNDEFINED`, `METRIC_FEW_SAMPLES` and the RPD/RPIQ = NaN rule on RMSE 0 accepted; SIMPLS PLS2 and VIP stay provisional until Quan's R values arrive (R32); gasoline data (Kalivas 1997) kept as a test benchmark; T1.00b catalog rows and the PyWavelets candidate approved |
| D-024 | 2026-11-26 | Tooling v0.5: K removed from the workflow; reviews = Quan + agents (ponytail-review, silent-failure-hunter, cpp-reviewer, mle-reviewer; docs/QA.md#8-review-checklists); caveman / ponytail / ECC take precedence over the project rules where they conflict (docs/rules/PRECEDENCE.md, D1–D6); the K review backlog became `docs/RISKS.md`; ADR-003…009 `Accepted` |
| D-023 | 2026-11-26 | Coded block warnings via `warnings.warn(VibeChemWarning)`; error/warning classes central in `errors.py`, code constants in the raising module, DATA_MODEL §7 the single registry (ADR-010, accepted at the Phase 1 gate 2026-11-27) |
| D-022 | 2026-11-24 | Phase 0 gate: ADR-003…009 accepted (provisional — K to confirm); ADR-007 allows in-memory pickling to loky workers only; Quasar port-max under ADR-009 (port, never depend); Phase 1 sizes revised (T1.02, T1.12 split; T1.03, T1.15 → M); new step T1.00 Quasar port inventory |
| D-021 | 2026-11-18 | Reuse first, build last (ADR-009, proposed); every step has a size (S/M/L) and reuse line in TASKS.md; PDF reports produced only by the desktop app |
| D-020 | 2026-11-17 | Docs consolidated: ARCHITECTURE (incl. ADRs), TECH_STACK, DATA_MODEL, UI_GUIDE, QA, TASKS for building; PROJECT for planning |
| D-019 | 2026-11-17 | Walking skeleton first (ADR-008, proposed) |
| D-018 | 2026-11-17 | Native kernels in C++20 (supersedes Rust); rules in TECH_STACK.md §5 |
| D-017 | 2026-11-17 | Languages: Python 3.14 (engine, blocks, API) · C++20 (kernels) · TypeScript strict (UI, shell) |
| D-016 | 2026-11-17 | Port selected pengoo code (relicensed GPL-3.0 by owner; pengoo itself stays a separate private project) and Quasar/Orange code, with source header + `THIRD_PARTY.md` |
| D-014 | 2026-11-17 | Electron shell (ADR-001) |
| D-012 | 2026-11-16 | AI-generated code with review gates: K reviews infra/architecture/C++/packaging; Quan reviews algorithms; block template + `# Step N:` comments; reference test per numerical function |
| D-011 | 2026-11-16 | Parallel computing is core (ADR-004) |
| D-010 | 2026-11-16 | Multi-port typed blocks; pipelines are DAGs |
| D-005 | 2026-11-16 | Local desktop app; UI and engine separable for a later web Lite |

**Pending sign-off by Quan:** none.
