# VibeChem — Tasks

> Status: v1.0 · Last updated: 2026-11-28
> v1.0: Phase 2 gate (T2.14, *proposed* until Quan approves the gate PR) — **T2.15 dataset transfer by memory map** *proposed (T2.14)* before `phase-2 → main` (R65); Phases 3 and 4 detailed (Phase 3 kernels from the T2.12 profiling report: Kennard–Stone/SPXY only, NumPy fix first, kernel conditional).
> v0.9: Phase 1 gate (Quan, 2026-11-27) — new first Phase 2 step **T2.00 CI false-pass guards** (R42); leakage and row_index guards in the T2.04, T2.05 and T2.10a "Done when" (R39, R40); Phase 4 outline gains app dependency major upgrades (Dependabot #27).
> v0.8: tooling v0.5 — K removed from the workflow: the `· K ·` / `· Q ·` area tags are gone from the step headings, Quan reviews everything (docs/QA.md#8-review-checklists), risks go to `docs/RISKS.md`.
> v0.7: T1.00b pengoo port inventory (Quan's request) — Phase 1 and T2.10 reuse lines name the pengoo function to port and the defect to fix (TECH_STACK.md §11.2); Duplex in T1.10 *proposed (T1.00b)*.
> v0.6: T1.00 Quasar port inventory — Phase 1 and Phase 6 reuse lines name the Quasar/Orange module to port or the library to wrap (TECH_STACK.md §11.1); **T1.06b vendor readers** *proposed (T1.00)* — Quan approves by merging the T1.00 PR, or deletes the T1.06b row and block.
> v0.5: Playwright CLI + design skills installed in T0.04; first Electron e2e test in T0.10; every `app/` step has a visual check (docs/TOOLS.md#51-visual-check-by-step-type); 👤 glyph-set step added to Phase 4.
> v0.4: **phase mode** — Quan types `/phase N`; Claude Code runs the steps below in order, each step = one PR merged into branch `phase-N`, until the gate or a stop condition (docs/rules/WORKFLOW.md#phase-mode). Phases run in numeric order. 👤 steps are prepared by Claude Code and finished/merged by Quan.
> Phases 0–4 are detailed. Later phases are outlines, detailed at the previous phase gate.
> Each step lists **exactly what to read** — Claude Code reads CLAUDE.md (automatic) plus only those sections and files.

## Run order
| Order | Phase | Branch | Ends with |
|---|---|---|---|
| 1 | 0 Foundations + walking skeleton | `phase-0` | Skeleton installers on 3 OS |
| 2 | 1 Core library | `phase-1` | `vibechem-core` 0.1 |
| 3 | 2 Pipeline engine | `phase-2` | `vibechem-core` 0.2 + CLI |
| 4 | 3 Native kernels | `phase-3` | `vibechem-native` 0.1 |
| 5 | 4 Engine API + UI | `phase-4` | Dev build of the app |
| 6 | 5 Desktop hardening | `phase-5` | **Alpha** (internal + S5 usability test) |
| 7 | 6 P0 breadth | `phase-6` | **Beta = demo v0** |
| 8 | 7 v1.0 release | `phase-7` | **v1.0** |
A phase starts only after the previous phase's PR is merged into `main`.

## How to run
- Whole phase: `/phase 1` · one step: `/step T1.07` (add `wait` to approve its plan first) · continue after a stop: `/resume [your answer]` · progress: `/status` · bug: `/bug <issue>`.
- A ticked box means "merged into the phase branch". It reaches `main` at the phase gate.

**Size** (planning estimate; Claude Code re-estimates in its plan): **S** = 1–2 checkpoints · **M** = 3–4 checkpoints · **L** = split into a/b steps when starting (docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.4)).
**Reuse** = candidates to evaluate first (TECH_STACK.md §11). "—" means nothing obvious; still do the §12 search if the step is M.
Legend: 👤 = Claude Code prepares, Quan acts and merges (stop `HUMAN_STEP`). Quan reviews every step (docs/QA.md#8-review-checklists); the agents per area are in TOOLS.md §3.

## Status overview
| Phase 0 | Phase 1 | Phase 2 |
|---|---|---|
| [x] T0.01 CI smoke 👤 | [x] T1.00 Quasar port inventory 👤 | [x] T2.00 CI false-pass guards 👤 |
| | [x] T1.00b pengoo port inventory | [x] T2.01 Port types |
| [x] T0.02 Repo skeleton + legal + labels 👤 | [x] T1.01 SpectralDataset | [x] T2.02 Pipeline graph |
| [x] T0.03 Python workspace + check.py | [x] T1.02a Block contract: base + registry | [x] T2.03 Pipeline file format |
| [x] T0.04 App workspace | [x] T1.02b Block contract: state + sklearn wrapper | [x] T2.04 Graph compiler |
| [x] T0.05 Native skeleton | [x] T1.03 Parameter schema | [x] T2.05 Leakage rules + suite |
| [x] T0.06 Full CI + rulesets 👤 | [x] T1.04 METHODS.md part 1 👤 | [x] T2.06 Cache |
| [x] T0.07 QA tooling | [x] T1.05 CSV/Excel readers | [x] T2.07 Executor + seeds |
| [x] T0.08 Reference datasets 👤 | [x] T1.06 JCAMP/SPC readers | [x] T2.08 Scheduler |
| [x] T0.09 Skeleton engine | [x] T1.06b Vendor readers | [x] T2.09 Crash recovery |
| [x] T0.10 Skeleton UI | [x] T1.07 SNV, MSC, detrend, cut | [x] T2.10a CV runner + LV rules 👤 |
| | | [x] T2.10b CV of PLS2 + PLS-DA, `model` output 👤 |
| | | [x] T2.10c Preprocessing grid search 👤 |
| | | [x] T2.10d Nested CV 👤 |
| [x] T0.11 Skeleton shell + installers | [x] T1.08 Savitzky–Golay | [x] T2.11 Python API + CLI |
| [x] T0.12 Spike: transport | [x] T1.09 Scaling blocks | [x] T2.12 Benchmarks + profiling |
| [x] T0.13 Spike: parallel | [x] T1.10 KS, SPXY, random split | [x] T2.13 Golden pipeline |
| [x] T0.14 Port-type design 👤 | [x] T1.11 CV fold generators | [ ] T2.15 Dataset transfer by memory map *(proposed)* |
| [x] T0.15 Phase gate 👤 | [x] T1.12a PLS: NIPALS wrap + LV sweep | [x] T2.14 Phase gate 👤 (report; Quan's gate open) |
| | [x] T1.12b PLS: SIMPLS + VIP | |
| | [x] T1.13 PLS-DA | |
| | [x] T1.14 Metrics | |
| | [x] T1.15 Reproduce published result + gate 👤 | |

| Phase 3 | Phase 4 |
|---|---|
| [ ] T3.01 Native template hardening | [ ] T4.01a Engine server: system, blocks, projects |
| [ ] T3.02 Native CI gating 👤 | [ ] T4.01b Engine server: imports, datasets, pipelines |
| [ ] T3.03 KS/SPXY without the n × n matrix | [ ] T4.02 Runs, results, cache, WebSocket events |
| [ ] T3.04 KS/SPXY native kernel *(conditional)* | [ ] T4.03 OpenAPI → TypeScript client |
| [ ] T3.05 Phase gate 👤 | [ ] T4.04 Preview service |
| | [ ] T4.04g Glyph set and block widget 👤 |
| | [ ] T4.05 Block library panel |
| | [ ] T4.06 Canvas with typed ports and states |
| | [ ] T4.07 Auto-generated inspector |
| | [ ] T4.08 Spectra viewer |
| | [ ] T4.09 Jobs panel |
| | [ ] T4.10 i18n completeness |
| | [ ] T4.11 Engine restart handling |
| | [ ] T4.11b App dependency major upgrades |
| | [ ] T4.12 Phase gate 👤 |

Phases 5–7: outlines at the end of this file; their status rows are added when they are detailed.

---

## Phase 0 — Foundations + walking skeleton
**Exit:** CI green on 3 OS; skeleton installers run SNV from the canvas; spikes reported with numbers; conventions, legal files and merge tooling merged.

### T0.01 · Verify GitHub Actions 👤 · Size S
- **Read:** TECH_STACK.md §8
- **Reuse:** GitHub's starter workflow; `actions/checkout`, `actions/setup-python`
- **Do:** create `phase-0` from `main` (docs/rules/WORKFLOW.md#session-preflight); add a 3-OS "hello" workflow triggered on pull requests to `main` and `phase-*`; push on a branch; open a PR into `phase-0`. If no run appears: tell Quan to allow Actions (repo Settings → Actions → General).
- **Files:** `.github/workflows/ci-smoke.yml`
- **Done when:** PR shows 3 green jobs (ubuntu, windows, macos). 👤 Quan merges (no merge script yet). The workflow is deleted in T0.06.

### T0.02 · Repository skeleton, legal files, labels, merge script 👤 · Size M
- **Read:** TECH_STACK.md §3, §4 (SPDX), §8.1 (branches), §13 (legal and citation files); ARCHITECTURE.md §8 (D-016); docs/rules/WORKFLOW.md#merging-a-step
- **Reuse:** GitHub's GPL-3.0 licence text; Keep-a-Changelog template; GitHub issue-form examples
- **Do:** folder tree per TECH_STACK §3 (empty packages with README stubs), `docs/handoff/`, `docs/spikes/`, `docs/research/` (with `.gitkeep`), `.gitignore` (incl. `.env`, `.claude/settings.local.json`), `.editorconfig`, `.gitattributes` (LF), `LICENSE`, `CITATION.cff`, `CHANGELOG.md`, `THIRD_PARTY.md`, `CODEOWNERS` (`* @<quan-github-username>` — ask Quan for the username if not in the repo URL), `CONTRIBUTING.md`, PR template (first line `Status: …`; sections from QA.md §7 incl. "Plan as executed", "Reuse decision", "Estimate vs actual"), issue forms (bug with diagnostics, feature, method request). **`scripts/merge_step.py`** (stdlib only, calls `gh`): refuses unless base matches `phase-*`, PR not draft, all checks green (`gh pr checks`), title starts with `[T`, `[BUG` or `[SYNC]`, and the step is not 👤 in TASKS.md; then `gh pr merge --squash --delete-branch` with the PR title; unit tests with a fake `gh`. Labels with `gh label create`: `in-progress`, `paused`, `needs-quan`, `build-installers` (a fourth review label was dropped in tooling v0.5), `S1`, `S2`, `S3`, `S4`, `qa-gate`.
- **Done when:** tree matches TECH_STACK §3; merge-script tests pass; `gh label list` shows the ten labels. 👤 Quan reviews the legal files and merges.

### T0.03 · Python workspace and `scripts/check.py` · Size M
- **Read:** TECH_STACK.md §1.1–1.3, §4, §7; QA.md §2, §4
- **Reuse:** `scientific-python/cookie` (pyproject, ruff, pytest, pre-commit settings); `uv init`
- **Do:** uv workspace (`packages/core`, `packages/engine`), Python 3.14, ruff, pyright strict, pytest config, pre-commit; `scripts/check.py` with `--fast`, `--only` and `--verbose`, printing the health summary format of QA.md §4; by default it prints only the summary plus the details of failures (keeps agent context small), full logs go to `reports/check.log`.
- **Done when:** `uv sync` + `uv run python scripts/check.py --fast` pass on a fresh clone on Windows; one trivial test per package.

### T0.04 · App workspace · Size M
- **Read:** TECH_STACK.md §1.5–1.6, §6; UI_GUIDE.md §2–3
- **Reuse:** `create-vite` React-TS template; electron-vite / electron-forge templates (pick one in the plan); `shadcn` CLI init
- **Do:** pnpm workspace in `app/` (renderer: Vite + React + TS strict + Tailwind + shadcn; main: Electron 45 TS), ESLint, Prettier, Vitest, i18next with `en/ja/vi` files, design tokens from UI_GUIDE, bundled fonts; `check.py --only app` calls lint + tests. Dev tools: `@playwright/test` and `@playwright/cli` as devDependencies, `playwright-cli install --skills` and commit the generated skill under `.claude/skills/`, `.playwright-cli/` in `.gitignore`; vendor Emil Kowalski's `break-ui`, `prototype`, `review-animations`, `animation-performance` skills from `emilkowalski/skills` at a pinned commit into `.claude/skills/` (MIT; commit hash + licence in THIRD_PARTY.md).
- **Done when:** `pnpm --dir app dev` opens an empty window with the app name translated in 3 languages; one Vitest test passes; `playwright-cli` can open the dev window and save a screenshot.

### T0.05 · Native C++ skeleton · Size M
- **Read:** TECH_STACK.md §1.4, §5; ARCHITECTURE.md §7 ADR-002
- **Reuse:** `nanobind_example` (wjakob); `uv init --lib --build-backend=scikit`
- **Do:** `packages/native` with CMake + scikit-build-core + nanobind; stub kernel `row_mean(X, n_threads)`; Python wrapper with fallback to a NumPy reference; Catch2 test; Python equivalence test. Keep it to the template; real kernels come in Phase 3.
- **Done when:** `uv sync` builds the extension on Windows locally; equivalence test passes; fallback test passes when the extension is hidden.

### T0.06 · Full CI and rulesets 👤 · Size M
- **Read:** TECH_STACK.md §8; QA.md §2
- **Reuse:** cibuildwheel's example workflow; scientific-python/cookie CI examples
- **Do:** `ci.yml` (check --fast on 3 OS, native wheels via cibuildwheel, sanitizer job on Linux; triggers: PRs to `main` and `phase-*`, pushes to `phase-*`), `installers.yml` (path-filtered + `build-installers` label), `nightly.yml` skeleton (runs on `main` **and** the newest `phase-*` branch; incl. macOS Intel; opens an `S2` issue on failure), Dependabot config (target `main`, monthly, grouped); remove `ci-smoke.yml`. Write the exact check names into the PR so Quan can select them.
- **Done when:** CI green on the PR. 👤 Quan adds the required status checks to both rulesets (his setup guide, step "Rulesets — part 2") and merges; the next step's PR shows the checks as required.

### T0.07 · QA tooling · Size M
- **Read:** QA.md §3, §5; TECH_STACK.md §3.1
- **Reuse:** `pytest-regressions` (golden files), `import-linter`, `hypothesis`, `pytest-cov`
- **Do:** tolerance helpers (`assert_close`), golden-file helper (per-node hashes), hypothesis profile, coverage thresholds, import-linter contracts for §3.1 boundaries, `reports/reference_report.md` generator.
- **Done when:** a deliberate boundary violation and a deliberate tolerance failure both make `check.py` FAIL with a clear message (then reverted).

### T0.08 · Reference datasets 👤 · Size S
- **Read:** QA.md §3; TECH_STACK.md §3 (`testdata/`)
- **Reuse:** public chemometrics datasets with published results
- **Do:** if Quan has not named the datasets yet, stop `MISSING_INPUT` and propose 3 candidates (NIR regression with a published PLS result; optional Raman/FTIR classification) with source, licence and published values. Once chosen: add them, `PROVENANCE.md` (source, licence, citation, expected values) and loaders.
- **Done when:** loaders return arrays of the documented shapes; expected values recorded in `testdata/expected/`. 👤 Quan checks the expected values and merges.

### T0.09 · Walking skeleton — engine · Size S
- **Read:** DATA_MODEL.md §1, §2.2 (`/health`), §2.3 (`/blocks`), §2.12 (skeleton endpoint); ARCHITECTURE.md §2.1
- **Reuse:** FastAPI's standard app/test-client patterns
- **Do:** minimal `vibechem_engine.api` with token + Origin check (dev origin allowed only in dev mode), `/health`, `/blocks` (SNV only), and the temporary `POST /skeleton/run` (DATA_MODEL §2.12); start-up prints port + token for Electron.
- **Done when:** API tests pass; unauthorised request → 401.

### T0.10 · Walking skeleton — UI · Size M
- **Read:** UI_GUIDE.md §5–6; DATA_MODEL.md §1, §2.12
- **Reuse:** React Flow and uPlot examples; `openapi-typescript`
- **Do:** canvas with two fixed nodes (Dataset → SNV), Run button, uPlot spectra preview; API client generated from OpenAPI.
- **Do (also):** visual check (docs/TOOLS.md#51-visual-check-by-step-type); first `@playwright/test` e2e test in Electron mode (launch → Run → spectra visible), added to `nightly.yml`. The SNV glyph is a placeholder until the Phase 4 glyph-set step.
- **Done when:** in dev mode, clicking Run shows raw and SNV spectra; e2e test passes locally and in CI; screenshots in the PR.

### T0.11 · Walking skeleton — shell and installers · Size M (split if > 4 checkpoints)
- **Read:** ARCHITECTURE.md §2.1, §7 ADR-001/008; TECH_STACK.md §8, §10, §12
- **Reuse:** electron-builder `extraResources` + PyInstaller one-folder sidecar pattern
- **Do:** Electron main starts/stops the engine (PyInstaller bundle incl. native extension; `freeze_support`), passes port + token via preload; electron-builder config; `installers.yml` builds installers for 3 OS; smoke test (`/health` = ready); record installer sizes in PROGRESS.md notes.
- **Done when:** CI macOS/Linux/Windows installer smoke jobs pass; sizes recorded. (Quan's own install test happens at the gate.)

### T0.12 · Spike — transport · Size S
- **Read:** ARCHITECTURE.md §7 ADR-003; DATA_MODEL.md §2.8
- **Reuse:** —
- **Do:** benchmark preview round-trip for 2,000 × 2,000 (lines and density mode) on 3 OS (CI jobs); write results to `docs/spikes/transport.md`.
- **Done when:** numbers recorded; recommendation for ADR-003 (accept / change) written for the gate.

### T0.13 · Spike — parallel · Size S
- **Read:** ARCHITECTURE.md §3.4, §7 ADR-004; TECH_STACK.md §12
- **Reuse:** loky/joblib documentation patterns (memmapping, threadpoolctl)
- **Do:** loky pool + memory-mapped arrays + threadpoolctl + seed spawning; 1 vs N workers on 3 OS (Windows spawn, and inside the frozen skeleton bundle); write `docs/spikes/parallel.md`.
- **Done when:** speed-up and determinism measured; recommendation for ADR-004 written for the gate.

### T0.14 · Port-type design 👤 · Size S
- **Read:** DATA_MODEL.md §4; FUNCTION_CATALOG.md §12, §15; PRD.md F-07
- **Reuse:** —
- **Do:** draft DATA_MODEL.md §4 (types, fields, compatibility, multi-input rules incl. PDS and ImageCube).
- **Done when:** draft PR ready. 👤 Quan reviews §4 and merges. No code.

### T0.15 · Phase 0 gate 👤 · Size S
- **Read:** docs/rules/WORKFLOW.md#phase-end; QA.md §9.1; PROGRESS.md
- **Do:** gate report (docs/rules/WORKFLOW.md#phase-end); list ADR-003…009 with a recommendation each; estimate-vs-actual for Phase 0 and proposed size changes for Phase 1.
- **Done when:** gate report merged into `phase-0`, phase PR ready. 👤 Quan: install test on his machine, QA §9.1 items 1–2, risk review, ADR decisions (provisional), merge `phase-0 → main`.

---

## Phase 1 — Core library (`vibechem_core`)
**Exit:** `pip install vibechem-core` works on 3 OS; ~15 blocks pass reference tests; a published PLS result reproduced.

### T1.00 · Quasar port inventory 👤 · Size M
- **Read:** ARCHITECTURE.md §7 ADR-009 (Quasar port-max); TECH_STACK.md §11; FUNCTION_CATALOG.md; PRD.md Appendix A
- **Reuse:** `quasars/orange-spectroscopy` (GPL-3.0) at a pinned commit; `biolab/orange3` (GPL-3.0), non-widget code only. Read upstream with read-only `gh api`; never install either as a dependency.
- **Files:** `docs/TECH_STACK.md` (§11.1 inventory + port recipe), `docs/FUNCTION_CATALOG.md` ("Likely source" notes), `docs/TASKS.md` (reuse lines; new steps if any), `THIRD_PARTY.md` (upstream commit pins), `docs/PROGRESS.md`
- **Do:**
  1. Inventory (TECH_STACK.md §11.1), one row per module: orange-spectroscopy `preprocess/`, `io/`, `irfft.py`, `models/`, and the useful non-Qt parts of Orange3 (preprocessors, PCA/HCA/k-Means, CV and permutation evaluation). Columns: our catalog function + F-ID · decision (port / wrap SciPy or another listed library instead / skip, with reason) · coupling to `Orange.data.Table` or Qt · its own third-party dependencies (e.g. `spectral`, `renishawWiRE`, `lmfit`) · upstream tests and sample data · target step.
  2. Port recipe (TECH_STACK.md §11): `Orange.data.Table` → NumPy + `SpectralDataset`; source header with upstream path + commit; `THIRD_PARTY.md` row; block template (docs/rules/CODING.md#block-template-and-comment-style).
  3. Reference-test rule: Quasar's own test values are not an independent reference for code ported from Quasar (CLAUDE.md#hard-rules); they are kept as extra regression checks only.
  4. Sample data: check the licences of Quasar's test spectra (`datasets/`, `tests/`); list redistributable ones for T1.06 and later reader steps.
  5. Rewrite reuse lines: FUNCTION_CATALOG.md "Likely source", TASKS.md Phase 1 steps (T1.06 first) and the Phase 6 outline. Scope changes (e.g. a new T1.06b vendor-reader step for OPUS/OMNIC/ENVI…, new dependency candidates in the §11 register) are proposed in the PR for Quan to approve.
  6. Pin both upstream commits in `THIRD_PARTY.md`.
- **Done when:** draft PR ready with every inventory row decided and given a target step; every P0/P1 catalog row with a Quasar/Orange source names it; Phase 1 and Phase 6 reuse lines updated. 👤 Quan approves the scope changes and merges. No code.

### T1.00b · pengoo port inventory · Size S
*(Added 2026-11-25 at Quan's request when he provided his local pengoo copy; same pattern as T1.00.)*
- **Read:** `pengoo/*.py` (local, git-excluded); TECH_STACK.md §11, §11.1 (port recipe, rules 3–4); FUNCTION_CATALOG.md §4–8, §13–14
- **Reuse:** pengoo (owner's code) — inventory only, no code ported in this step
- **Files:** `docs/TECH_STACK.md` (§11.2 + register rows), `docs/FUNCTION_CATALOG.md` ("Likely source" notes, proposed rows), `docs/TASKS.md` (reuse lines), `docs/PROGRESS.md`
- **Do:** one row per pengoo function: catalog function, decision (port / wrap / skip), defect or convention clash to fix, target step; confirm suspected defects by running pengoo in a scratch environment; record behaviour choices for T1.04.
- **Done when:** every public pengoo function has a decided row with a target; Phase 1 and T2.10 reuse lines updated; confirmed defects listed with evidence. No code.

### T1.01 · SpectralDataset · Size M
- **Read:** ARCHITECTURE.md §3.1; DATA_MODEL.md §2.5 (dataset fields); TECH_STACK.md §4
- **Reuse:** — (own small dataclass; do not adopt a heavy data framework)
- **Files:** `packages/core/src/vibechem_core/data/`
- **Do:** immutable typed dataset (X, axis + unit, signal unit, Y, classes, metadata, sample/group IDs, history); validation; `with_X()`; row subset by indices.
- **Done when:** unit + property tests (shapes, immutability, subset consistency).

### T1.02a · Block contract: base, ports, metadata, registry · Size M
*(T1.02 split at the Phase 0 gate; same total scope as the former T1.02.)*
- **Read:** ARCHITECTURE.md §3.1, §7 ADR-005/007; docs/rules/CODING.md#block-template-and-comment-style (block template)
- **Reuse:** scikit-learn's `fit`/`transform` conventions (so wrapped transformers fit naturally)
- **Files:** `vibechem_core/block.py`, `registry.py`, `errors.py`
- **Do:** `Block` base, `Param`, `port()`, metadata (id, version, class, icon, references, fitted, tier), `fit`/`apply` split, error classes with codes, registry.
- **Done when:** a dummy fitted and a dummy stateless block run `fit`/`apply`; registry lists them with their metadata; error codes match DATA_MODEL.md §7.

### T1.02b · Block contract: state serialisation + scikit-learn wrapper · Size M · depends T1.02a
- **Read:** ARCHITECTURE.md §7 ADR-007; `vibechem_core/block.py`
- **Reuse:** scikit-learn's `fit`/`transform` conventions; NumPy `.npy` (`allow_pickle=False`)
- **Files:** `vibechem_core/block.py` (state), `vibechem_core/wrap.py` (or inside `block.py` if small)
- **Do:** JSON + array state serialisation for fitted blocks (no pickle); helper to wrap a scikit-learn-style transformer as a block.
- **Done when:** the dummy fitted and stateless blocks round-trip state save/load; a wrapped scikit-learn transformer works as a block and round-trips its state.

### T1.03 · Parameter schema · Size M
- **Read:** DATA_MODEL.md §5, §2.3 (`/blocks/{id}` example)
- **Reuse:** pydantic JSON Schema generation
- **Do:** draft DATA_MODEL.md §5 (types, units, `visible_if`, constraints) in the same PR; implement schema export from `Param` definitions.
- **Done when:** `/blocks/{id}`-shaped JSON generated for the dummy blocks and validated against §5.

### T1.04 · METHODS.md part 1 👤 · Size M
- **Read:** FUNCTION_CATALOG.md §4–9 (P0 rows used in Phase 1)
- **Reuse:** original papers; documentation of candidate libraries (to note where their definitions differ)
- **Do:** draft entries (definition, formula, reference, edge cases, tolerance, chosen implementation) for the T1.07–T1.14 methods; `docs/references.bib` with those references. Propose an answer for every **(T1.04)** item in TECH_STACK.md §11.2 (pengoo behaviour choices: SNV ddof, SG edge mode, PLS X scaling default, KS/SPXY distance space, RMSECV aggregation default, bias sign, LOO rule, PLS2 VIP) for Quan to confirm.
- **Done when:** draft PR ready. 👤 Quan corrects and approves the entries, then merges. T1.07–T1.14 depend on this step.

### T1.05 · CSV/TSV and Excel readers · Size M
- **Read:** DATA_MODEL.md §2.5; TECH_STACK.md §1.2
- **Reuse:** stdlib `csv` + NumPy (pyarrow CSV reader overruled by Quan: core stays free of pyarrow), openpyxl — write only role detection and validation. Quasar's `io/ascii.py` (`AsciiColReader`) is not ported; its rules (`;` comment lines, headerless two-column files such as Bruker `.dpt`) become test cases, with osp `datasets/peach_juice.dpt` as a sample (GPL test data, TECH_STACK.md §11.1 rule 4)
- **Files:** `vibechem_core/io/table.py`
- **Do:** read, detect roles (sample ID, groups, Y, spectral columns + axis), warnings (duplicate IDs, non-numeric).
- **Done when:** tests on reference data and malformed files.

### T1.06 · JCAMP-DX and SPC readers · Size M
- **Read:** DATA_MODEL.md §2.5; TECH_STACK.md §1.2, §11
- **Reuse:** `jcamp` (approved). SPC: **port** osp `io/omnic.py` `SPCReader` + `utils/spc/` (Rohan Isaac's `spc`, GPL-3.0, pure `struct` + NumPy — recommended) or wrap `spc-io` (MIT; pandas + pydantic; last release 2025-04) — compare both in the plan. Multi-file behaviour (axis union, file-name column) from osp `widgets/owmultifile.py` (spec only). Sample files: osp `datasets/m_xyxy.spc`, `rohanisaac/spc` `test_data/` (several instruments), `nzhagen/jcamp` `data/` (JCAMP-DX) — licences per TECH_STACK.md §11.1 rule 4
- **Files:** `vibechem_core/io/jcamp.py`, `io/spc.py`
- **Do:** readers behind the same interface; multi-file concatenation with axis check. Sample files from two vendors: use public ones with a redistributable licence; if none found → `MISSING_INPUT`.
- **Done when:** tests on sample files from at least two instrument vendors.

### T1.06b · Vendor readers: Bruker OPUS, Thermo OMNIC SPA, PerkinElmer .sp, Renishaw WDF · Size M · depends T1.06 · *proposed (T1.00)*
*(Proposed by T1.00 from the Quasar inventory; catalog row "Bruker OPUS" is P1 and the other three are proposed P1 rows. Approve by merging the T1.00 PR; to reject, delete this block and its status row — the readers then wait for v1.1.)*
- **Read:** DATA_MODEL.md §2.5; TECH_STACK.md §11, §11.1 (readers table, port recipe, rule 4); `vibechem_core/io/` (T1.06 interface)
- **Reuse:** OPUS → wrap `brukeropus` (MIT, candidate; Quasar's `opusFC` is rejected); SPA → port osp `io/omnic.py` `SPAReader`; PerkinElmer → port osp `io/perkinelmer.py` + `utils/specio/` (BSD-3 notice kept); WDF → wrap `renishawWiRE` (MIT, candidate; vendor it if still unmaintained)
- **Files:** `vibechem_core/io/{opus,spa,perkinelmer,wdf}.py`
- **Do:** readers behind the T1.06 interface; OPUS data-block choice (absorbance / sample / reference) as a reader option. Sample files from osp `datasets/` (`peach_juice.0`, `sample1.spa`, `perkinelmer/single_PE_spectrum.sp`, `renishaw_test_files/*.wdf`) if Quan accepts them as GPL test data; otherwise `MISSING_INPUT`.
- **Done when:** each reader has a test on a sample file with an independently known value (axis range, point count, one intensity read with the vendor's software or a second reader); new dependencies approved in the PR.

### T1.07 · Preprocessing A: cut, SNV, MSC, detrend · Size M · depends T1.04
- **Read:** METHODS.md (these entries); docs/rules/CODING.md#block-template-and-comment-style; `block.py`; TECH_STACK.md §11
- **Reuse:** `chemotools` (MSC, detrend, cut); SNV/cut may be simpler as own NumPy code. Quasar: port osp `Cut` (inclusive bounds, several ranges, unsorted axis); osp `Normalize` SNV mode and `EMSC` order 0 (= MSC) serve as behaviour cross-checks only (EMSC itself is ported in Phase 6). Reference values never from Quasar's tests (TECH_STACK.md §11.1 rule 3). pengoo (TECH_STACK.md §11.2, local `pengoo/`): port `snv`, `msc` (fix D1: least-squares fit of a + b·ref; reference learned in `fit`) and the axis-based polynomial detrend; no `+1e-10` guards (constant spectrum → error/NaN)
- **Files:** `vibechem_core/blocks/preprocess/{cut,snv,msc,detrend}.py`; parameter type `wavelength_ranges` (Quan, 2026-11-26): `vibechem_core/block.py` (`Param`, `parse_params`), `vibechem_core/testing.py` (`DummySchema`), `vibechem_engine/api/schemas.py`, DATA_MODEL.md §5.2/§5.3
- **Done when:** unit, property and reference tests pass (also for wrapped methods); MSC is `fitted` (reference spectrum learned).

### T1.08 · Savitzky–Golay smoothing and derivatives · Size S · depends T1.04
- **Read:** METHODS.md (SG entry); `block.py`
- **Reuse:** `scipy.signal.savgol_filter` (wrap; do not reimplement); pengoo `perform_smoothing` uses the same call with `mode='nearest'` (SciPy default `'interp'` — default chosen in METHODS.md, T1.04). Quasar's `SavitzkyGolayFiltering` wraps the same call — its NaN and unsorted-axis handling is the behaviour reference, not ported
- **Files:** `blocks/preprocess/savgol.py`
- **Done when:** matches SciPy within tolerance and an independent reference (hand-computed or published); edge handling documented.

### T1.09 · Scaling: mean-centre, autoscale, Pareto · Size S · depends T1.04
- **Read:** METHODS.md; `block.py`
- **Reuse:** scikit-learn `StandardScaler`; `chemotools` scalers (Pareto). Orange3 `preprocess` `Normalize`/`Scale` are not ported (Table/Domain transformations around the same arithmetic). pengoo (TECH_STACK.md §11.2, local `pengoo/`): `perform_scaling` centring/autoscaling computes statistics on whatever it is applied to (D2) — the test "apply uses training statistics only" covers it; Y autoscaling with inverse transform replaces pengoo's `convert_y`/`y_sdev`
- **Files:** `blocks/preprocess/scaling.py`
- **Done when:** all `fitted`; apply on new data uses training statistics only (test proves it).

### T1.10 · Splits: random, Kennard–Stone, SPXY · Size M · depends T1.04
- **Read:** METHODS.md; `block.py`; TECH_STACK.md §11
- **Reuse:** scikit-learn `train_test_split` (random/stratified); `kennard-stone` package (cross-check). pengoo (TECH_STACK.md §11.2, local `pengoo/`): port `_ks_order`, the SPXY distance and the stratified, unit-preserving selection of `split_cal_test` as the group-aware option (distance space — raw X or PCA scores — decided in T1.04); `_duplex_order` exists too (Duplex is C§5 P0 — *proposed (T1.00b)* addition to this step, `duplex.py`)
- **Files:** `blocks/split/{random_split,kennard_stone,spxy}.py`
- **Done when:** KS/SPXY match published/reference selections on the reference dataset; group-aware option.

### T1.11 · CV fold generators · Size S · depends T1.04
- **Read:** METHODS.md; `block.py`
- **Reuse:** scikit-learn `KFold`, `GroupKFold`, `LeaveOneOut`, `RepeatedKFold`; own code only for venetian blinds and contiguous blocks. Orange3 `evaluation/testing.py` (incl. `CrossValidationFeature` = grouped CV) wraps the same splitters — not ported. pengoo (TECH_STACK.md §11.2, local `pengoo/`): port `validate_cv_groups` (several group columns combined), folds materialised once (`PredefinedFolds`) and the group-leak assertion; fixed `random_state=69` → `Generator`
- **Files:** `blocks/validate/folds.py`
- **Done when:** property tests: folds partition samples; groups never split.

### T1.12a · PLS: NIPALS wrap, outputs, LV sweep (PLS1/PLS2) · Size M · depends T1.04
*(T1.12 split at the Phase 0 gate; same total scope as the former T1.12.)*
- **Read:** METHODS.md (PLS); `block.py`
- **Reuse:** scikit-learn `PLSRegression` (NIPALS). Quasar/Orange PLS (`models/pls.py`, o3 `regression/pls.py`) wraps the same class — not ported here; its DModX/residual code is ported in Phase 6 diagnostics. pengoo (TECH_STACK.md §11.2, local `pengoo/`): port the LV sweep from one fit (`_predict_pls_at_lv`); scikit-learn's default `scale=True` (all pengoo results used it) vs mean-centring only is decided in T1.04
- **Files:** `blocks/model/pls.py`
- **Do:** fit/apply, scores, loadings, weights, coefficients; LV sweep from one fit; PLS1 and PLS2.
- **Done when:** predictions match scikit-learn within tolerance and an independent reference; LV sweep equals separate fits.

### T1.12b · PLS: own SIMPLS + VIP · Size M · depends T1.12a
- **Read:** METHODS.md (PLS, VIP); `blocks/model/pls.py`
- **Reuse:** own SIMPLS (check the §12 search first); VIP: port pengoo `calculate_vip` (TECH_STACK.md §11.2) with an independent reference value
- **Files:** `blocks/model/pls.py`
- **Do:** SIMPLS algorithm option; VIP scores.
- **Done when:** SIMPLS matches NIPALS for PLS1; SIMPLS reference test against an independent source; VIP property tests.

### T1.13 · PLS-DA · Size S · depends T1.12a
- **Read:** METHODS.md (PLS-DA); `blocks/model/pls.py`
- **Reuse:** our PLS block + scikit-learn label encoding
- **Files:** `blocks/model/plsda.py`
- **Done when:** binary and multi-class tests; decision rule documented.

### T1.14 · Metrics · Size S · depends T1.04
- **Read:** METHODS.md (metrics); PRD.md F-44
- **Reuse:** scikit-learn metrics for R², confusion matrix, ROC-AUC; own code for RMSEC/CV/P, SEP, bias, slope, RPD, RPIQ. Orange3 `evaluation/scoring.py` wraps the same scikit-learn metrics — not ported. pengoo (TECH_STACK.md §11.2, local `pengoo/`): port the definitions in `regression_metrics` (RMSE, bias, SEP, R², RPD) and the `fold_mean`/`pooled` RMSECV aggregation; add RPIQ and slope; reference values hand-computed, never from pengoo (rule 5)
- **Files:** `vibechem_core/metrics.py`
- **Done when:** each metric has a hand-computed test; values in original Y units.

### T1.15 · Reproduce a published result + Phase 1 gate 👤 · Size M
- **Read:** `testdata/datasets/PROVENANCE.md`; QA.md §4, §9.1; docs/rules/WORKFLOW.md#phase-end
- **Do:** reference test reproducing the published PLS result; build `vibechem-core` wheel on 3 OS; gate report incl. estimate-vs-actual.
- **Done when:** reference report shows the published value within tolerance; phase PR ready. 👤 Quan: gate review, merge `phase-1 → main`.

---

## Phase 2 — Pipeline engine (`vibechem_engine`)
**Exit:** nested-CV pipeline runs from the CLI; identical results on 1 and 8 cores; ≥ 4× speed-up on 8 cores; leakage suite passes; pipeline format v1 frozen.

### T2.00 · CI false-pass guards 👤 · Size S
- **Read:** `docs/RISKS.md` R42 (also R01, R20, R21); `.github/workflows/ci.yml`, `.github/workflows/nightly.yml`; `scripts/merge_step.py`, `scripts/check.py`
- **Reuse:** — (CTest `--no-tests=error`, GitHub Actions status functions)
- **Do:** `ctest --no-tests=error` in the `check` and `sanitizer` jobs; nightly report job `if: failure() || cancelled()` so a cancelled or timed-out run also opens the S2 issue. `scripts/merge_step.py` (refuse unless every expected required job name passed) and `scripts/check.py` (pytest exit 5, nothing collected → FAIL) are Quan-only files (R21): prepare each as a patch with a failing test in `scripts/tests/`, attach it to the PR and stop `HUMAN_STEP`; Quan applies the patches and merges.
- **Done when:** a CI run with a test-less CTest build fails; the nightly condition is visible in the workflow; both patches attached with failing-first tests; R42 updated. 👤 Quan: apply the two patches, merge.

### T2.01 · Port type registry · Size S
- **Read:** DATA_MODEL.md §4; `vibechem_core/block.py`
- **Reuse:** —
- **Files:** `vibechem_engine/ports/`
- **Done when:** compatibility tests for every rule in §4.

### T2.02 · Pipeline graph and validation · Size M
- **Read:** DATA_MODEL.md §2.6 (pipeline shape), §7 (codes); `ports/`
- **Reuse:** Python `graphlib` (topological sort, cycle detection) before adding a graph library
- **Files:** `vibechem_engine/graph/`
- **Done when:** cycle, missing-input and type-mismatch tests return the documented error codes.

### T2.03 · Pipeline file format v1 + migrations · Size M
- **Read:** DATA_MODEL.md §6; ARCHITECTURE.md §7 ADR-006/007
- **Reuse:** pydantic models + JSON Schema export; `jsonschema` validation
- **Do:** draft DATA_MODEL.md §6 (project, pipeline, model formats) in the same PR; JSON Schema; save/load; migration framework with one example migration.
- **Files:** `vibechem_engine/formats/`
- **Done when:** round-trip tests; schema rejects invalid files; no pickle anywhere (test scans).

### T2.04 · Graph compiler · Size M
- **Read:** ARCHITECTURE.md §2.2, §3.2–3.3; `graph/`
- **Reuse:** —
- **Files:** `vibechem_engine/compiler/`
- **Do:** user graph → task graph; fit/apply split; per-fold expansion hooks.
- **Done when:** compiled task graphs for 3 example pipelines match expected structures; fold rows are taken by `row_index` through one helper (e.g. `SpectralDataset.rows(row_index)`), never as positions, with a failing-first test on a dataset whose `row_index` is offset from its positions (R40).

### T2.05 · Leakage rules and leakage test suite · Size M
- **Read:** ARCHITECTURE.md §3.2; QA.md §3 (leakage); PRD.md F-42
- **Reuse:** scikit-learn `Pipeline` + `cross_val_score` as the independent reference in tests
- **Files:** `compiler/leakage.py`, `packages/engine/tests/leakage/`
- **Done when:** leaky pipelines rejected with `PIPELINE_LEAKAGE`; noise-data tests show no score inflation; an MSC `reference` input wired from rows outside the training set (e.g. the unsplit dataset) is rejected, with a failing-first test (R39). Test design summarised in the PR for Quan's spot-check at the gate.

### T2.06 · Content-addressed cache · Size M
- **Read:** ARCHITECTURE.md §2.3, §3.3
- **Reuse:** joblib `Memory` patterns / `hashlib`; evaluate before writing a custom store
- **Files:** `vibechem_engine/cache/`
- **Done when:** key stability tests; LRU cap; corrupt-entry recovery test.

### T2.07 · Executor interface, process pool, seeds · Size M
- **Read:** ARCHITECTURE.md §3.4; `docs/spikes/parallel.md`
- **Reuse:** loky (approved), threadpoolctl (approved), `numpy.random.SeedSequence`
- **Files:** `vibechem_engine/executor/`
- **Done when:** tasks run in warm workers with memory-mapped inputs; per-task seeds; BLAS threads = 1.

### T2.08 · Scheduler · Size M
- **Read:** ARCHITECTURE.md §3.4–3.5; DATA_MODEL.md §3 (progress events)
- **Reuse:** —
- **Files:** `vibechem_engine/scheduler/`
- **Done when:** core budget, memory estimator, cancellation and progress events tested.

### T2.09 · Crash recovery · Size S
- **Read:** ARCHITECTURE.md §3.6
- **Reuse:** loky's worker-crash handling
- **Done when:** tests for worker crash (native fallback), OOM throttling, cancel timeout, corrupt cache.

### T2.10a · CV runner and LV rules 👤 · Size M *(split from T2.10, Size L, in T2.10a's PR)*
- **Read:** PRD.md F-43; METHODS.md §5, §8 (#rmsecv); `compiler/`, `scheduler/`; RISKS.md R25, R36, R40, R41, R53
- **Reuse:** pengoo (TECH_STACK.md §11.2): LV rules from `select_n_components`/`_wold_r_criterion` (t-test α as a parameter), `calculate_cv_rmse` aggregation (already in core `cv_metrics`); the fold loop is our compiler + scheduler; `MISSING_INPUT` if `pengoo/` is absent on the machine
- **Files:** `vibechem_engine/runners/`; core `lv_rules.py` (the t-test needs SciPy, which the engine may not import), `data/results.py`, `blocks/validate/cv.py`
- **Do:** METHODS.md entries for CV and LV rules (new: Quan approves them, hence 👤); classification metric names proposed (R36); a runner that executes a compiled pipeline on the scheduler and expands fold plans; `validate.cv` (PLS1) with LV curve, per-fold SD/SE, repeated-CV aggregation, `VALIDATION_GROUPS_IGNORED` from `Folds.groups_respected`.
- **Done when:** gasoline LOO RMSECV matches Mevik & Wehrens 2007 and a 5-fold curve matches a hand-written scikit-learn CV; the CV runner selects fold rows by `row_index` through the T2.04 helper (not positions), tested on an offset `row_index` dataset, and asserts one out-of-fold prediction per row per repeat (R40, R41). 👤 Quan: approve METHODS.md §9 and N17–N24, merge.

### T2.10b · CV of PLS2 and PLS-DA, `model` output 👤 · Size M *(split from T2.10; T2.10b split into T2.10b/c/d in T2.10b's PR, Quan 2026-11-28)*
- **Read:** PRD.md F-43; METHODS.md §8 (#classification-metrics, N22, N27), §9; `runners/`; RISKS.md R34
- **Reuse:** core `metrics` (confusion matrix, sensitivity, specificity, ROC-AUC), `predict_sweep`, `lv_rules`
- **Files:** core `blocks/validate/cv.py`; `vibechem_engine/runners/`
- **Do:** `validate.cv` for PLS2 and PLS-DA models: classification metrics of N22/N27 (macro `sensitivity_*`, `specificity_*`, `auc_*`, weighted `*_w_*`, `accuracy_*`, `class_ratio_*` always; `*_micro_*` only with `micro_metrics` = true, default false; warning `METRIC_CLASSES_SEVERELY_UNBALANCED` only when `class_ratio` > `severe_imbalance_ratio`, default 20), `predictions` with `class_true`/`class_pred`/`score_<class>`; `model` output refit at the chosen LV count; R34's fixed 16 LV replaced by a CV-chosen LV.
- **Done when:** PLS-DA CV metrics match a hand-written scikit-learn loop on a small set; the `model` output predicts like a separate fit at n_lv; the olive-oil PLS-DA check uses a CV-chosen LV count. 👤 Quan: approve METHODS.md N28, N29 and the proposed codes `VALIDATION_CLASS_MISSING_IN_FOLD`, `VALIDATION_Y_SCALES_DIFFER`, merge (new choices, Quan 2026-11-28).

### T2.10c · Preprocessing grid search 👤 · Size M *(split from T2.10b)*
- **Read:** PRD.md F-43; METHODS.md §9; DATA_MODEL.md §4.5–§4.6; `runners/`
- **Reuse:** scikit-learn `ParameterGrid`; pengoo grid search from `grid_search.py` — fixed-order product, dedup (`_step_identity` → our content hash), deterministic order, shared folds, LV sweep per fold, Excel pipeline list with JSON params (TECH_STACK.md §11.2). No pickle checkpoints, no joblib (our executor), `Generator` for random subsampling; `MISSING_INPUT` if `pengoo/` is absent on the machine
- **Files:** `vibechem_engine/runners/`; core search block in `blocks/validate/`
- **Do:** a `search_space` param on the search block (decision by Quan, 2026-11-28, option A): ordered step slots, each a list of `{block_id, params}` options, "none" allowed; the engine builds each candidate chain between the fold source and the model block (pengoo style); options validated against the block registry; `Results.kind = search` with a `candidates` table listing each candidate chain and its metrics; default search space as a JSON file from registered blocks; METHODS.md entry for the search (new → 👤 Quan approves it).
- **Done when:** on a small set, every candidate's CV metrics equal a separate `validate.cv` run of that chain; candidates are deduplicated and in a deterministic order; an unknown `block_id` in `search_space` is a node error. 👤 Quan: approve the METHODS entry, merge.

### T2.10d · Nested CV 👤 · Size M *(split from T2.10b)*
- **Read:** PRD.md F-43; METHODS.md §9; DATA_MODEL.md §4.6; `runners/`
- **Reuse:** our CV runner and T2.10c search; scikit-learn nested CV only as the test reference
- **Depends on:** T2.10c
- **Files:** `vibechem_engine/runners/`; core nested-CV block in `blocks/validate/`
- **Do:** nested CV (inner tuning of LVs, preprocessing chains, selection params); inner folds as a scheme parameter `inner_folds` = `{block_id, params}` of a fold block, run on each outer training set, never a `Folds` input made on all rows (decision by Quan, 2026-11-28); `Results.kind = nested_cv`; METHODS.md entry for nested CV (new → 👤 Quan approves it).
- **Done when:** results match a hand-written scikit-learn nested CV on the reference dataset. 👤 Quan: approve the METHODS entry, merge.

### T2.11 · Python API and CLI · Size S
- **Read:** TECH_STACK.md §7; `graph/`, `runners/`
- **Reuse:** `argparse` or a small CLI library already in the stack (no new dependency without approval)
- **Files:** `vibechem_engine/cli/`, public `vibechem.Pipeline`
- **Done when:** `vibechem run pipeline.vcp.json` produces metrics; `vibechem validate`, `vibechem blocks list` work.

### T2.12 · Benchmarks and profiling report · Size S
- **Read:** ARCHITECTURE.md §1.2, §4; `scripts/`
- **Reuse:** `pytest-benchmark` or `cProfile`/`py-spy` (evaluate)
- **Done when:** `scripts/bench.py` reports speed-up (target ≥ 4× on 8 cores, measured on CI runners and noted with core count) and determinism; profiling report lists C++ candidates for Phase 3 and any pure-Python/NumPy fixes that would make a kernel unnecessary.

### T2.13 · Golden pipeline · Size S
- **Read:** QA.md §3 (golden), §5
- **Reuse:** golden-file helper from T0.07
- **Done when:** golden test stores per-node hashes + metrics; a deliberate change shows the first divergent node.

### T2.15 · Dataset transfer by memory map · Size M · *proposed (T2.14)*
*(Proposed at the Phase 2 gate for R65: the ≥ 4× exit criterion is not met. Runs on `phase-2` after the gate PR, before `phase-2 → main`. Approve by merging the gate PR; to reject, delete this block and its status row and record the accepted speed-up in PROGRESS.md.)*
- **Read:** `docs/spikes/profiling.md`; ARCHITECTURE.md §3.4, ADR-004; RISKS.md R57, R65, R69 (b, c), R71 (a, d, g); `vibechem_engine/executor/`, `scheduler/`, `runners/`, `pipeline.py`; `scripts/bench.py`
- **Reuse:** `ProcessExecutor.share()` (T2.07, `np.load(mmap_mode="r")`), `SpectralDataset.rows(row_index)` (T2.04); no new dependency
- **Files:** `vibechem_engine/executor/`, `runners/`, `pipeline.py` (default worker count); ARCHITECTURE.md §3.4 (+ D-row: how datasets reach workers); `scripts/bench.py` only if its output must change
- **Do:** each source dataset's arrays are shared once per run (memory-mapped file, keyed per array) and fold and select tasks carry row indices instead of datasets; `share()` gets a `release()` so spill files do not grow (R57 b); default worker count reviewed against physical cores (profiling: SMT adds little); the Ctrl-C wait and traceback of R71 (a) fixed; a pipeline-level test that 1 and 4 workers give identical nested-CV and grid-search results (R69 c).
- **Done when:** `scripts/bench.py --workers 1,8` on a machine with ≥ 8 cores shows ≥ 4× at 8 workers with one result hash, numbers and core count in the PR (if below 4×: the remaining gap measured and named, and Quan decides); bytes sent per task (probe in the PR) at most a few kB for fold tasks; spill folder empty after a run; golden test unchanged (no node hash changes); determinism tests still bit-identical.

### T2.14 · Phase 2 gate 👤 · Size S
- **Read:** docs/rules/WORKFLOW.md#phase-end; QA.md §9.1; PROGRESS.md
- **Do:** gate report; detail **Phase 3 and Phase 4** steps in TASKS.md (same format, sizes, reuse lines; Phase 3 kernels chosen from the T2.12 profiling report); propose UI_GUIDE.md updates from research studies S3/S4 if Quan has added findings to `docs/research/`.
- **Done when:** phase PR ready. 👤 Quan: gate review (QA §9.1 items 2–4), approve the Phase 3–4 detail, freeze format v1, merge `phase-2 → main`.

---

## Phase 3 — Native kernels
*(Detailed at the Phase 2 gate, T2.14. The T2.12 profiling report measured one kernel candidate, Kennard–Stone/SPXY; everything else is under 0.1 s per call at v1 sizes, and CARS, SPA and PDS do not exist yet — their kernels are judged when their Phase 6 steps profile them. The planned T3.03–T3.06 "one step per hotspot" therefore shrink to T3.03–T3.04.)*
**Exit:** the native template is safe to copy (R45 closed); native CI gates sanitizers incl. TSan, clang-tidy and clang-format; a 5,000-row Kennard–Stone/SPXY split takes ≤ 1 s, in NumPy or with a kernel that has a Python reference, equivalence tests and an automatic fallback; `vibechem-native` 0.1 wheels build on 3 OS.

### T3.01 · Native template hardening · Size S
- **Read:** RISKS.md R45; TECH_STACK.md §5; `packages/native/README.md`; `packages/native/bindings/`, `src/`, `python/vibechem_native/`
- **Reuse:** nanobind `.noconvert()` and `nb::call_guard<nb::gil_scoped_release>`; `std::exception_ptr` to carry worker exceptions; no new dependency
- **Files:** `packages/native/` (bindings, `src/`, `CMakeLists.txt`, `tests/`)
- **Do:** `out` arrays bound with `.noconvert()`; exceptions inside `std::jthread` workers captured and rethrown in the calling thread; `_GLIBCXX_ASSERTIONS` in debug and sanitizer builds; Catch2 fetched by commit SHA; repo `.clang-format` and `.clang-tidy` configs (checks run in T3.02).
- **Done when:** a float32 or strided `out` raises `TypeError` instead of writing into a copy (pytest); an exception thrown in a worker thread reaches Python as an exception, not `std::terminate` (Catch2 + pytest); Catch2 pinned by SHA; cpp-reviewer pass with no open *Must fix*; R45 closed or its rest named.

### T3.02 · Native CI gating: TSan, clang-tidy, clang-format 👤 · Size S · depends T3.01
- **Read:** `.github/workflows/ci.yml` (`sanitizer` job), TECH_STACK.md §5, §8; RISKS.md R42 (`REQUIRED_CHECKS` note)
- **Reuse:** the existing `sanitizer` job; clang-tidy / clang-format from the runner image or a SHA-pinned action
- **Files:** `.github/workflows/ci.yml`, `packages/native/.clang-tidy`, `.clang-format`
- **Do:** a TSan job that runs the native tests with `n_threads > 1`; clang-tidy and clang-format checks with warnings as errors; ASan/UBSan job unchanged.
- **Done when:** each new check fails on a deliberate violation (shown in a throwaway commit, then reverted) and passes on the branch; the new job names are listed in the PR. 👤 Quan: add the new jobs to the ruleset's required checks and to `REQUIRED_CHECKS` in `merge_step.py` (Quan-only files and settings), merge.

### T3.03 · Kennard–Stone and SPXY without the n × n matrix · Size S
- **Read:** METHODS.md (Kennard–Stone, SPXY); `vibechem_core/blocks/split/kennard_stone.py`, `spxy.py` (their `shortcut:` markers); `docs/spikes/profiling.md`
- **Reuse:** NumPy incremental max–min update (one distance row per selected sample, running minimum per candidate); `kennard-stone` package (§11 candidate) as a cross-check only
- **Files:** `blocks/split/kennard_stone.py`, `spxy.py`, their tests; `docs/spikes/profiling.md` (new timings)
- **Do:** replace the full distance matrices by the incremental update (memory O(n·p) instead of O(n²)); keep the selection rule, tie handling and group means of METHODS.md; remove the two `shortcut:` markers.
- **Done when:** selections identical to the current code on the reference datasets and on property cases (random data, ties, groups); 5,000 × 1,000 timing recorded before/after (target ≤ 1 s on the laptop); peak memory for 5,000 rows below 50 MB (was ≈ 300 MB); reference tests unchanged.

### T3.04 · Kennard–Stone / SPXY native kernel · Size M · depends T3.01, T3.03 · *conditional*
*(Runs only if T3.03 misses ≤ 1 s at 5,000 × 1,000 or the 5,000 × 4,000 time is still above 3 s. Otherwise the step is closed with the T3.03 numbers in PROGRESS.md and Quan's agreement at the Phase 3 gate.)*
- **Read:** TECH_STACK.md §5; `packages/native/README.md`; T3.03 code (the Python reference); ARCHITECTURE.md §3.4 (core budget: a kernel with `n_threads > 1` is one wide task)
- **Reuse:** Eigen (§1.4) for the distance rows; the T3.01 template and the existing fallback dispatch (`vibechem_native.BACKEND`)
- **Files:** `packages/native/` (kernel, binding, wrapper, tests); `blocks/split/kennard_stone.py`, `spxy.py` (dispatch)
- **Do:** max–min selection kernel with `n_threads`, GIL released; the blocks call it when `BACKEND == "native"` and fall back to the T3.03 NumPy code otherwise or when the kernel raises (fallback recorded in the block log).
- **Done when:** equivalence tests (same selection order) against the Python reference on reference data and property cases; fallback test with the extension hidden; sanitizer jobs (ASan/UBSan, TSan) clean; timing in the PR; cpp-reviewer pass, open findings in RISKS.md.

### T3.05 · Phase 3 gate 👤 · Size S
- **Read:** docs/rules/WORKFLOW.md#phase-end; QA.md §9.1; PROGRESS.md
- **Do:** gate report (cpp-reviewer over `packages/native`, ponytail-audit, ponytail-debt, mle-reviewer on the split change); `vibechem-native` 0.1 wheels on 3 OS (cibuildwheel job); check Phase 4 detail still holds.
- **Done when:** phase PR ready. 👤 Quan: gate review, merge `phase-3 → main`.

---

## Phase 4 — Engine API + UI
*(Detailed at the Phase 2 gate, T2.14, from PRD F-01…F-08, F-42, F-83, F-84 and DATA_MODEL §2–§3. Every `app/` step has its visual check (docs/TOOLS.md#51-visual-check-by-step-type).)*
**Exit:** a dev build of the app: import a CSV, build a nested-CV pipeline on the canvas, run it on all cores with live states and progress, inspect any block, cancel, close and reopen the project; QA §9.1 items 5–9 pass.

### T4.01a · Engine server: system, settings, blocks, port types, projects · Size M
- **Read:** DATA_MODEL.md §1, §2.1–§2.4, §6.2, §7; ARCHITECTURE.md §3.6–§3.7; RISKS.md R43, R46, R50, R56; `vibechem_engine/api/`
- **Reuse:** FastAPI + pydantic (installed), the block registry and `parameter_schema` export (T1.03), `formats/` project loaders (T2.03)
- **Files:** `vibechem_engine/api/` (routes, error handlers), `packages/engine/tests/api/`
- **Do:** `/health`, `/system`, `/settings`, `/blocks`, `/blocks/{id}`, `/port-types`, project create/open/get/close; problem+json handlers for `RequestValidationError`, `VibeChemError`, `Exception` (R43); `__main__` exits non-zero when start-up fails; R46 clean-up (drop the duplicate validators in `api/schemas.py`, delete `wrap.TransformerBlock` and its test, spike workflows → `workflow_dispatch`).
- **Done when:** one test per route against the DATA_MODEL §2 examples; every error body carries `code` and `message_key`; R43 closed; R46 closed except the skeleton SNV (goes in T4.01b).

### T4.01b · Engine server: imports, datasets, pipelines, validate · Size M · depends T4.01a
- **Read:** DATA_MODEL.md §2.5–§2.6, §4.4, §6.3, §7; RISKS.md R44, R47, R50, R71 (b, c); `vibechem_core/io/`, `vibechem_engine/formats/`, `pipeline.py`
- **Reuse:** core readers and role detection (T1.05–T1.06b), `vibechem.Pipeline.validate`, `formats.load_pipeline`/`save`
- **Files:** `vibechem_engine/api/`, `packages/engine/tests/api/`; DATA_MODEL §7 (proposed codes)
- **Do:** two-step import (inspect → commit), dataset list/get/delete, pipeline CRUD + `validate` (graph, types, leakage, implicit conversions reported until executed — R71 b), `block_version` compared with the installed block (code proposed in DATA_MODEL §7 first — R71 c), codes for unknown `block_id`/port (R50); remove `/skeleton/run`, the skeleton SNV and `testdata/` from `extraResources` (R48).
- **Done when:** import → commit → pipeline → validate round trip tested on the gasoline CSV; a leaky pipeline gives `PIPELINE_LEAKAGE` with `node_id`/`port_id` through `validate`; an edge needing an implicit conversion is an error issue, not "valid"; skeleton endpoint and its e2e test replaced.

### T4.02 · Runs, results, cache and WebSocket events · Size M · depends T4.01b
- **Read:** DATA_MODEL.md §2.7–§2.8, §2.11, §3; ARCHITECTURE.md §3.3–§3.6; RISKS.md R55, R58, R60 (b), R70, R71 (e, f); `scheduler/`, `cache/`, `runners/`
- **Reuse:** `run_pipeline` + scheduler progress events (T2.08), `ResultCache` (T2.06), FastAPI WebSocket
- **Files:** `vibechem_engine/api/`, `runners/` (cache and memory budget wiring), `packages/engine/tests/api/`
- **Do:** start/list/get/cancel runs; results summary and data; `/events` with `run.*`, `node.state`, `progress`, warnings merged into the node log (R60 b); the result cache wired into the run path and a memory budget with per-job estimates (R70); `node.state` `idle`/`stale` after cancel and failed dependants (R58 a); cache endpoints.
- **Done when:** a second identical run starts zero tasks (cache test); changing one parameter re-runs only that node and its dependants (F-04, QA §9.1 item 6 automated); cancel leaves no `queued`/`running` node state; event sequence for one run matches DATA_MODEL §3 (recorded test); R70 closed.

### T4.03 · OpenAPI → TypeScript client · Size S · depends T4.02
- **Read:** TECH_STACK.md §1.5, §6; `app/renderer/src/api/`
- **Reuse:** `openapi-typescript` (approved, T0.10) + the small typed `fetch` client already in `api/`; TanStack Query
- **Files:** `app/renderer/src/api/`, `scripts/` (schema export), CI check
- **Do:** export the engine's OpenAPI schema; generate TS types; typed client and WebSocket event types; a check that fails when the generated file is stale.
- **Done when:** the renderer compiles against generated types only (no hand-written API types left); the stale-schema check fails on a deliberate route change.

### T4.04 · Preview service · Size M · depends T4.02
- **Read:** DATA_MODEL.md §2.8 (`/preview`); ARCHITECTURE.md §1.2 (preview < 300 ms, redraw < 100 ms); `vibechem_engine/api/arrow.py`
- **Reuse:** pyarrow IPC (engine, approved), NumPy min/max decimation; density mode as a 2-D histogram (`numpy.histogram2d`)
- **Files:** `vibechem_engine/api/` (preview), `packages/engine/tests/api/`
- **Do:** plot-ready previews per port type (spectra: decimated lines or density, tables, metrics); size caps.
- **Done when:** 2,000 × 2,000 spectra preview in < 300 ms on the laptop (timed test, marked slow); decimation keeps every local min/max per pixel bin (property test).

### T4.04g · Glyph set and block widget 👤 · Size M
- **Read:** UI_GUIDE.md §2, §4 (incl. §4.0 Quan's preferences), §6, §6.1; FUNCTION_CATALOG.md (P0 blocks)
- **Reuse:** Impeccable `prototype`/`critique`; existing `app/renderer/src/canvas/` node
- **Files:** `app/renderer/src/canvas/glyphs/`, a contact-sheet page, UI_GUIDE.md §4/§6
- **Do:** glyphs for all P0 blocks and the block node at three zoom levels as a contact sheet with variants; S3 recognition study 👤; decide DATA_MODEL §4.7.1 (`Transform` shape).
- **Done when:** contact sheet renders (screenshots in the PR); 👤 Quan picks the variants and runs S3; UI_GUIDE §4 loses its *draft* mark; §4.7.1 decided.

### T4.05 · Block library panel · Size S · depends T4.03, T4.04g
- **Read:** UI_GUIDE.md §5, §6, §7; PRD F-01, F-08; `app/renderer/src/library/`
- **Reuse:** `/blocks` metadata (class, icon, references, tier); shadcn components already in the app
- **Files:** `app/renderer/src/library/`
- **Done when:** blocks grouped by class with search; drag onto the canvas creates a node; tooltip text from i18n keys (F-08); visual check + e2e drag test.

### T4.06 · Canvas with typed ports and run states · Size M · depends T4.05
- **Read:** PRD F-01, F-02, F-07, F-42; DATA_MODEL.md §4.3–§4.4; UI_GUIDE.md §2.3, §6, §8; `app/renderer/src/canvas/`
- **Reuse:** `@xyflow/react` (approved); `/port-types` compatibility from the engine (no rules duplicated in TS); zustand store
- **Files:** `app/renderer/src/canvas/`, `state/`
- **Do:** typed multi-port nodes, connection checks with the refusal reason, node states `idle · queued · running · done · stale · error` from events, "data here" marker, "Leakage-safe ✓" badge from `validate` (and not shown when `VALIDATION_GROUPS_IGNORED` is raised, R69 d).
- **Done when:** an incompatible connection is refused with the engine's reason (e2e); states follow a recorded event stream (unit test); pipeline saved and reloaded unchanged (e2e).

### T4.07 · Auto-generated inspector · Size M · depends T4.06
- **Read:** DATA_MODEL.md §5 (parameter schema, `visible_if`, `search_space`, `block_ref`, `wavelength_ranges`); ADR-005; PRD F-03; `app/renderer/src/inspector/`
- **Reuse:** evaluate JSON-schema form libraries first (e.g. `@rjsf/core`, JSON Forms) against our §5 schema in the plan — add a §11 row either way; own small form only if none fits §5 without heavy adapters
- **Files:** `app/renderer/src/inspector/`; TECH_STACK.md §11 (row)
- **Do:** form from `/blocks/{id}` schema with units, constraints, `visible_if`; output preview of the selected node (T4.04); parameter errors from `validate` shown on the field.
- **Done when:** every P0 block's parameters render and validate (generated test over the registry); `visible_if` hides/shows fields (unit test); a bad value shows the engine's `BLOCK_PARAM_INVALID` reason on its field.

### T4.08 · Spectra viewer · Size S · depends T4.04
- **Read:** UI_GUIDE.md §2.4, §8; ARCHITECTURE.md §1.2; `app/renderer/src/plots/`
- **Reuse:** uPlot (approved) + Arrow decoding (`apache-arrow`)
- **Files:** `app/renderer/src/plots/`
- **Done when:** 2,000 spectra redraw in < 100 ms (timed in the visual check); zoom, hover read-out with axis unit, density mode switch; screenshots in the PR.

### T4.09 · Jobs panel · Size S · depends T4.02
- **Read:** PRD F-83; DATA_MODEL.md §3 (progress events); `app/renderer/src/jobs/`
- **Reuse:** TanStack Query + the WebSocket store
- **Files:** `app/renderer/src/jobs/`
- **Done when:** running jobs show progress and ETA from events; cancel works and the app stays responsive (QA §9.1 item 7 as an e2e test); "CPU cores to use" setting (default all but one) sent to `/settings`.

### T4.10 · i18n completeness · Size S
- **Read:** UI_GUIDE.md §7; PRD F-80; `app/renderer/src/i18n/`
- **Reuse:** i18next; `break-ui` skill with long JA/VI strings
- **Files:** `app/renderer/src/i18n/`, a check script in `app/scripts/`
- **Done when:** a check fails on a missing or unused key in EN/JA/VI and on literal UI strings; break-ui findings fixed or in RISKS.md; QA §9.1 item 9 passes.

### T4.11 · Engine restart handling · Size S · depends T4.02
- **Read:** PRD F-84; ARCHITECTURE.md §3.6; `app/main/engine.ts`
- **Reuse:** existing engine supervisor in `app/main`; `/projects/open` (T4.01a)
- **Files:** `app/main/`, `app/renderer/src/state/`
- **Done when:** killing the engine process during a run shows a notice, restarts the engine and reopens the project with the pipeline intact (e2e); QA §9.1 item 8 passes.

### T4.11b · App dependency major upgrades · Size M
- **Read:** TECH_STACK.md §1.5–§1.6; RISKS.md R11; `app/package.json`
- **Reuse:** each tool's migration guide (Context7)
- **Files:** `app/package.json`, `pnpm-lock.yaml`, config files; TECH_STACK.md §1.5–§1.6
- **Do:** TypeScript 7, ESLint 10, Vite 8, Vitest 5, electron-vite 6, React 19.3 (Dependabot #27 closed by Quan), one tool per checkpoint.
- **Done when:** `check.py --fast --only app` and the e2e tests pass after each upgrade; TECH_STACK pins updated; R11 closed.

### T4.12 · Phase 4 gate 👤 · Size S
- **Read:** docs/rules/WORKFLOW.md#phase-end; QA.md §9.1; PROGRESS.md
- **Do:** gate report; UI review (Impeccable `audit` + `accessibility-review` over every changed screen); ADR-005 review; detail Phase 5 in TASKS.md.
- **Done when:** phase PR ready. 👤 Quan: QA §9.1 items 1–9, approve the Phase 5 detail, merge `phase-4 → main`.

## Phase 5 — Desktop hardening · Alpha (outline; detailed at the Phase 4 gate)
T5.01 production Electron shell + supervision · T5.02 engine bundle size budget · T5.03 installers + first-launch guide (EN/JA/VI) · T5.04 update check + diagnostics · T5.05 e2e tests (Playwright) for core flows · T5.06 S5 usability test 👤 · T5.07 phase gate 👤 (= Alpha; details Phase 6).

## Phase 6 — P0 breadth · Beta = demo v0 (outline; detailed at the Phase 5 gate)
One step per catalog P0 group (≈ 15–20 steps: remaining preprocessing — reuse chemotools/pybaselines first, then **port from Quasar** (TECH_STACK.md §11.1): Gaussian smoothing (wrap SciPy), `Despike`, `EMSC`, `Absorbance`/`Transmittance`, `PCADenoising`, `ShiftAndScale`, `Integrate` (band integration, *proposed* catalog row); baselines — `pybaselines` for ALS/airPLS/polynomial, port osp `RubberbandBaseline` + `LinearBaseline`; normalisations — port osp `Normalize` + `NormalizeReference`; data handling — port osp `Interpolate` + NaN helpers, `owaverage`; exploration — scikit-learn PCA, port osp `owsnr` (SNR, *proposed* catalog row); diagnostics — port o3 `regression/pls.py` DModX; splits; validation extras — port o3 `owpermutationplot.permutation()` logic for the permutation test; variable selection; regression models — reuse scikit-learn; classification; statistics — reuse SciPy/statsmodels if approved; plots; model package + predict mode; reports + citations; Python export; templates; guided mode; tooltip content) · S6/S7 studies 👤 · **demo v0 gate 👤**: Beta release build + **risk review** (`docs/RISKS.md` grouped by area, open ADRs, architecture changes since Phase 0, native kernels from Phase 3).

## Phase 7 — v1.0 release (outline)
T7.01 release workflow + Zenodo · T7.02 docs site · T7.03 feedback channels · T7.04 JOSS paper draft 👤 · T7.05 SignPath application 👤 · T7.06 release checklist (QA §9.2) 👤 · S8 analysis.
