# VibeChem — Tasks

> Status: v0.9 · Last updated: 2026-11-27
> v0.9: Phase 1 gate (Quan, 2026-11-27) — new first Phase 2 step **T2.00 CI false-pass guards** (R42); leakage and row_index guards in the T2.04, T2.05 and T2.10a "Done when" (R39, R40); Phase 4 outline gains app dependency major upgrades (Dependabot #27).
> v0.8: tooling v0.5 — K removed from the workflow: the `· K ·` / `· Q ·` area tags are gone from the step headings, Quan reviews everything (CLAUDE.md §10), risks go to `docs/RISKS.md`.
> v0.7: T1.00b pengoo port inventory (Quan's request) — Phase 1 and T2.10 reuse lines name the pengoo function to port and the defect to fix (TECH_STACK.md §11.2); Duplex in T1.10 *proposed (T1.00b)*.
> v0.6: T1.00 Quasar port inventory — Phase 1 and Phase 6 reuse lines name the Quasar/Orange module to port or the library to wrap (TECH_STACK.md §11.1); **T1.06b vendor readers** *proposed (T1.00)* — Quan approves by merging the T1.00 PR, or deletes the T1.06b row and block.
> v0.5: Playwright CLI + design skills installed in T0.04; first Electron e2e test in T0.10; every `app/` step has a visual check (CLAUDE.md §13.1); 👤 glyph-set step added to Phase 4.
> v0.4: **phase mode** — Quan types `/phase N`; Claude Code runs the steps below in order, each step = one PR merged into branch `phase-N`, until the gate or a stop condition (CLAUDE.md §14). Phases run in numeric order. 👤 steps are prepared by Claude Code and finished/merged by Quan.
> Phases 0–2 are detailed. Later phases are outlines, detailed at the previous phase gate.
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

**Size** (planning estimate; Claude Code re-estimates in its plan): **S** = 1–2 checkpoints · **M** = 3–4 checkpoints · **L** = split into a/b steps when starting (CLAUDE.md §12.4).
**Reuse** = candidates to evaluate first (TECH_STACK.md §11). "—" means nothing obvious; still do the §12 search if the step is M.
Legend: 👤 = Claude Code prepares, Quan acts and merges (stop `HUMAN_STEP`). Quan reviews every step (CLAUDE.md §10); the agents per area are in TOOLS.md §3.

## Status overview
| Phase 0 | Phase 1 | Phase 2 |
|---|---|---|
| [x] T0.01 CI smoke 👤 | [x] T1.00 Quasar port inventory 👤 | [ ] T2.00 CI false-pass guards 👤 |
| | [x] T1.00b pengoo port inventory | [ ] T2.01 Port types |
| [x] T0.02 Repo skeleton + legal + labels 👤 | [x] T1.01 SpectralDataset | [ ] T2.02 Pipeline graph |
| [x] T0.03 Python workspace + check.py | [x] T1.02a Block contract: base + registry | [ ] T2.03 Pipeline file format |
| [x] T0.04 App workspace | [x] T1.02b Block contract: state + sklearn wrapper | [ ] T2.04 Graph compiler |
| [x] T0.05 Native skeleton | [x] T1.03 Parameter schema | [ ] T2.05 Leakage rules + suite |
| [x] T0.06 Full CI + rulesets 👤 | [x] T1.04 METHODS.md part 1 👤 | [ ] T2.06 Cache |
| [x] T0.07 QA tooling | [x] T1.05 CSV/Excel readers | [ ] T2.07 Executor + seeds |
| [x] T0.08 Reference datasets 👤 | [x] T1.06 JCAMP/SPC readers | [ ] T2.08 Scheduler |
| [x] T0.09 Skeleton engine | [x] T1.06b Vendor readers | [ ] T2.09 Crash recovery |
| [x] T0.10 Skeleton UI | [x] T1.07 SNV, MSC, detrend, cut | [ ] T2.10 CV / nested CV / search |
| [x] T0.11 Skeleton shell + installers | [x] T1.08 Savitzky–Golay | [ ] T2.11 Python API + CLI |
| [x] T0.12 Spike: transport | [x] T1.09 Scaling blocks | [ ] T2.12 Benchmarks + profiling |
| [x] T0.13 Spike: parallel | [x] T1.10 KS, SPXY, random split | [ ] T2.13 Golden pipeline |
| [x] T0.14 Port-type design 👤 | [x] T1.11 CV fold generators | [ ] T2.14 Phase gate 👤 |
| [x] T0.15 Phase gate 👤 | [x] T1.12a PLS: NIPALS wrap + LV sweep | |
| | [x] T1.12b PLS: SIMPLS + VIP | |
| | [x] T1.13 PLS-DA | |
| | [x] T1.14 Metrics | |
| | [x] T1.15 Reproduce published result + gate 👤 | |

Phases 3–7: outlines at the end of this file; their status rows are added when they are detailed.

---

## Phase 0 — Foundations + walking skeleton
**Exit:** CI green on 3 OS; skeleton installers run SNV from the canvas; spikes reported with numbers; conventions, legal files and merge tooling merged.

### T0.01 · Verify GitHub Actions 👤 · Size S
- **Read:** TECH_STACK.md §8
- **Reuse:** GitHub's starter workflow; `actions/checkout`, `actions/setup-python`
- **Do:** create `phase-0` from `main` (CLAUDE.md §14.1); add a 3-OS "hello" workflow triggered on pull requests to `main` and `phase-*`; push on a branch; open a PR into `phase-0`. If no run appears: tell Quan to allow Actions (repo Settings → Actions → General).
- **Files:** `.github/workflows/ci-smoke.yml`
- **Done when:** PR shows 3 green jobs (ubuntu, windows, macos). 👤 Quan merges (no merge script yet). The workflow is deleted in T0.06.

### T0.02 · Repository skeleton, legal files, labels, merge script 👤 · Size M
- **Read:** TECH_STACK.md §3, §4 (SPDX), §8.1 (branches), §13 (legal and citation files); ARCHITECTURE.md §8 (D-016); CLAUDE.md §14.2
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
- **Do (also):** visual check (CLAUDE.md §13.1); first `@playwright/test` e2e test in Electron mode (launch → Run → spectra visible), added to `nightly.yml`. The SNV glyph is a placeholder until the Phase 4 glyph-set step.
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
- **Read:** CLAUDE.md §14.4; QA.md §9.1; PROGRESS.md
- **Do:** gate report (CLAUDE.md §14.4); list ADR-003…009 with a recommendation each; estimate-vs-actual for Phase 0 and proposed size changes for Phase 1.
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
  2. Port recipe (TECH_STACK.md §11): `Orange.data.Table` → NumPy + `SpectralDataset`; source header with upstream path + commit; `THIRD_PARTY.md` row; block template (CLAUDE.md §5).
  3. Reference-test rule: Quasar's own test values are not an independent reference for code ported from Quasar (CLAUDE.md §4); they are kept as extra regression checks only.
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
- **Read:** ARCHITECTURE.md §3.1, §7 ADR-005/007; CLAUDE.md §5 (block template)
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
- **Read:** METHODS.md (these entries); CLAUDE.md §5; `block.py`; TECH_STACK.md §11
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
- **Read:** `testdata/datasets/PROVENANCE.md`; QA.md §4, §9.1; CLAUDE.md §14.4
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

### T2.10 · CV, nested CV and grid search runners · Size L → split into T2.10a (CV + LV rules) and T2.10b (nested CV + preprocessing grid search)
- **Read:** PRD.md F-43; METHODS.md (CV, LV rules); `compiler/`, `scheduler/`
- **Reuse:** scikit-learn `ParameterGrid`; pengoo (TECH_STACK.md §11.2): LV rules from `select_n_components`/`find_knee` (T2.10a); grid search from `grid_search.py` — fixed-order product, dedup, shared folds, LV sweep per fold, Excel pipeline list (T2.10b). No pickle checkpoints, no joblib (our executor), `Generator` for random subsampling; `MISSING_INPUT` if `pengoo/` is absent on the machine
- **Files:** `vibechem_engine/runners/`
- **Do:** CV runner, nested CV (inner tuning of LVs, preprocessing chains, selection params), grid search, LV selection rules. METHODS.md entries for CV and LV rules must exist (add them in T2.10a and stop `HUMAN_STEP` for Quan's approval if they are new).
- **Done when:** results match a hand-written scikit-learn nested CV on the reference dataset. T2.10a also: the CV runner selects fold rows by `row_index` through the T2.04 helper (not positions), tested on an offset `row_index` dataset, and asserts one out-of-fold prediction per row per repeat (R40, R41).

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

### T2.14 · Phase 2 gate 👤 · Size S
- **Read:** CLAUDE.md §14.4; QA.md §9.1; PROGRESS.md
- **Do:** gate report; detail **Phase 3 and Phase 4** steps in TASKS.md (same format, sizes, reuse lines; Phase 3 kernels chosen from the T2.12 profiling report); propose UI_GUIDE.md updates from research studies S3/S4 if Quan has added findings to `docs/research/`.
- **Done when:** phase PR ready. 👤 Quan: gate review (QA §9.1 items 2–4), approve the Phase 3–4 detail, freeze format v1, merge `phase-2 → main`.

---

## Phase 3 — Native kernels (outline; detailed at the Phase 2 gate)
T3.01 production native build hardening · T3.02 sanitizer + clang-tidy gating · T3.03–T3.06 one step per hotspot kernel from the T2.12 profiling report (likely KS/SPXY, CARS, SPA, PDS windows), each with a Python reference, equivalence tests and automatic fallback — **only if no existing fast implementation can be reused** and NumPy/SciPy vectorisation is not enough · every step gets a cpp-reviewer pass (TOOLS.md §3) · T3.07 phase gate 👤.

## Phase 4 — Engine API + UI (outline; detailed at the Phase 2 gate)
T4.01 full engine server (DATA_MODEL §2; remove the skeleton endpoint) · T4.02 WebSocket events (§3) · T4.03 OpenAPI → TS client · T4.04 preview service (decimation, density) · **T4.04g glyph set and block widget 👤** (Claude Code drafts glyphs for all P0 blocks and the block node at three zoom levels per UI_GUIDE §4/§6 and Quan's preferences in §4.0, as a contact-sheet page with variants via `prototype`; S3 recognition study 👤; Quan picks, UI_GUIDE §4 loses its *draft* mark) · T4.05 block library panel · T4.06 canvas with typed ports and states · T4.07 auto-generated inspector (evaluate JSON-schema form libraries first) · T4.08 spectra viewer QoL · T4.09 jobs panel · T4.10 i18n completeness check (+ break-ui with long JA/VI strings) · T4.11 engine restart handling in UI · T4.11b app dependency major upgrades (TypeScript 7, ESLint 10, Vite 8, Vitest 5, electron-vite 6, React 19.3; R11, Dependabot #27 closed by Quan) · T4.12 phase gate 👤 (details Phase 5).

## Phase 5 — Desktop hardening · Alpha (outline; detailed at the Phase 4 gate)
T5.01 production Electron shell + supervision · T5.02 engine bundle size budget · T5.03 installers + first-launch guide (EN/JA/VI) · T5.04 update check + diagnostics · T5.05 e2e tests (Playwright) for core flows · T5.06 S5 usability test 👤 · T5.07 phase gate 👤 (= Alpha; details Phase 6).

## Phase 6 — P0 breadth · Beta = demo v0 (outline; detailed at the Phase 5 gate)
One step per catalog P0 group (≈ 15–20 steps: remaining preprocessing — reuse chemotools/pybaselines first, then **port from Quasar** (TECH_STACK.md §11.1): Gaussian smoothing (wrap SciPy), `Despike`, `EMSC`, `Absorbance`/`Transmittance`, `PCADenoising`, `ShiftAndScale`, `Integrate` (band integration, *proposed* catalog row); baselines — `pybaselines` for ALS/airPLS/polynomial, port osp `RubberbandBaseline` + `LinearBaseline`; normalisations — port osp `Normalize` + `NormalizeReference`; data handling — port osp `Interpolate` + NaN helpers, `owaverage`; exploration — scikit-learn PCA, port osp `owsnr` (SNR, *proposed* catalog row); diagnostics — port o3 `regression/pls.py` DModX; splits; validation extras — port o3 `owpermutationplot.permutation()` logic for the permutation test; variable selection; regression models — reuse scikit-learn; classification; statistics — reuse SciPy/statsmodels if approved; plots; model package + predict mode; reports + citations; Python export; templates; guided mode; tooltip content) · S6/S7 studies 👤 · **demo v0 gate 👤**: Beta release build + **risk review** (`docs/RISKS.md` grouped by area, open ADRs, architecture changes since Phase 0, native kernels from Phase 3).

## Phase 7 — v1.0 release (outline)
T7.01 release workflow + Zenodo · T7.02 docs site · T7.03 feedback channels · T7.04 JOSS paper draft 👤 · T7.05 SignPath application 👤 · T7.06 release checklist (QA §9.2) 👤 · S8 analysis.
