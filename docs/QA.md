# VibeChem — Quality Assurance & Testing

> Status: v0.3 · Last updated: 2026-11-22 · Owners: Quan (scientific correctness), K (test infrastructure, from demo v0)
> v0.3: phase mode — step PRs merge automatically into `phase-N` when every check passes, so the automated checks and red-flag stops carry more weight; Quan's full review moves to the phase gate. Nightly also runs on the active phase branch. DoD aligned with CLAUDE.md §6.
> Purpose: (1) tell Quan, without deep coding knowledge, whether the project is healthy; (2) let Claude Code find and fix bugs inside a small area of the code.

## 1. What QA protects (in priority order)
1. **Correct numbers** — every algorithm (ours or reused) matches its definition (METHODS.md) and a reference implementation.
2. **No leakage** — validation results are never optimistic because of the pipeline design.
3. **Reproducibility** — same input + seed → same result, on any core count and OS (within tolerance).
4. **Stability** — the app never loses work; crashes are contained.
5. **Installability** — installers work on clean Windows, macOS, Linux.
6. **Usability** — measured in the user-research studies (owner's project plan).

## 2. Quality levels (when each check runs)
| Level | When | What runs | Who looks |
|---|---|---|---|
| **L1a Checkpoint** | After each checkpoint, before its commit | `check.py --fast --only <area>` | Claude Code |
| **L1b Ready** | Before a step PR is marked ready | Full `check.py --fast`: format, lint, types, boundaries, unit/property/reference/leakage tests, golden pipeline, app unit tests; code-review (+ security/a11y where required) | Claude Code (must be all PASS) |
| **L2 Step PR CI** | Every push to a step PR (base `phase-N`) | `ci.yml` on Windows, macOS, Linux + native wheels + sanitizer; `installers.yml` when packaging paths change. `merge_step.py` merges only when all are green | Automatic |
| **L2b Phase PR CI** | Every merge into `phase-N` | `ci.yml` on the phase branch (the phase PR shows it) | Quan glances at the phase PR |
| **L3 Nightly** | Every night on `main` and the active `phase-*` branch | Slow tests, nested-CV benchmark, determinism (1 vs N cores), e2e app tests, installers incl. macOS Intel | Failure opens an `S2` issue automatically |
| **L4 Phase gate** | End of each phase | Gate report (CLAUDE.md §14.4), manual checklist (§9.1), spot-review of algorithms, risk review, estimate review | Quan (+ K from demo v0) |
| **L5 Release** | Before each release | Release checklist (§9.2) on clean machines | Quan + K |

## 3. Test types
| Type | Purpose | Location | Example |
|---|---|---|---|
| Unit | One function behaves as specified | `packages/*/tests/` mirroring `src/` | SNV of a known 3-point spectrum |
| Property | Invariants hold for random inputs (hypothesis) | same | SNV rows have mean 0, std 1 |
| Reference | Matches an independent implementation or published values within METHODS.md tolerance — **also for wrapped libraries** | `.../tests/reference/` | PLS RMSECV on the public dataset |
| Equivalence | C++ kernel = Python reference | `packages/native/tests/python/` | Kennard–Stone selections identical |
| Leakage | Pipeline design cannot inflate scores | `packages/engine/tests/leakage/` | Random-noise X: nested CV R² ≈ 0 |
| Golden pipeline | End-to-end regression sentinel | `packages/engine/tests/golden/` + `testdata/expected/` | Every node's output hash and final metrics unchanged |
| Determinism | Same results for 1 and N workers | nightly | Nested CV on 1 vs 8 workers |
| API contract | Engine responses match DATA_MODEL.md / OpenAPI | `packages/engine/tests/api/` | `/blocks` schema validation |
| UI unit | Components behave | `app/renderer/src/**/*.test.tsx` | Inspector renders int param with min/max |
| End-to-end | Real user flows in the desktop app (`@playwright/test`, from T0.10) | `app/e2e/` | Import CSV → build PLS → run → see metrics |
| Visual check | Changed screens look right in all states and with worst-case data | PR screenshots (not committed) | CLAUDE.md §13.1: Playwright CLI + Impeccable critique/audit + break-ui |
| Installer smoke | App starts after install | `installers.yml`, nightly | Install, launch, `/health` = ready, quit |
| Performance | No speed regressions | `scripts/bench.py`, nightly | Preview < 300 ms; speed-up ≥ 4× on 8 cores |

**Reference tests for reused code:** when a block wraps a library (e.g. chemotools, pybaselines, scikit-learn), the reference value must come from somewhere *other* than that same library — a published value, a hand calculation, or a second implementation — otherwise the test only proves the library agrees with itself.

**Coverage targets** (enforced from Phase 1; Phase 0 only needs the smoke tests): `vibechem_core` ≥ 90 % · `vibechem_engine` ≥ 85 % · renderer ≥ 70 % · every block has ≥ 1 reference or property test (mandatory, regardless of coverage).

## 4. Health signals and red flags
`scripts/check.py` prints this summary; Claude Code pastes it into every step PR and the gate report:
```
VibeChem health summary
format/lint ........ PASS
types .............. PASS
boundaries ......... PASS
tests .............. PASS  (412 passed, 0 failed)
reference report ... PASS  (23/23 within tolerance)
leakage suite ...... PASS
golden pipeline .... PASS  (no node changed)
coverage ........... core 93% | engine 87% | app 74%
```
The **reference report** (`reports/reference_report.md`, regenerated by every check) lists: method · dataset · expected value · VibeChem value · difference · tolerance · source of expected value · PASS/FAIL. If a number looks wrong to Quan, it is a bug even if it says PASS.

**Red flags** — in phase mode each one is a stop (`RED_FLAG`, CLAUDE.md §14.3) unless the step's own text requires it:
- A tolerance in a test or METHODS.md was loosened.
- A test was deleted, skipped, or marked "expected failure".
- The golden pipeline expected values were regenerated.
- Files outside the step's listed files were changed (beyond tests, docs, CHANGELOG, TASKS.md, PROGRESS.md).
- Something was built from scratch although the step's Reuse line or TECH_STACK.md §11 listed a candidate, without an options table.
- A new dependency appears without a TECH_STACK.md row.
- Coverage of a package dropped.

## 5. Designed so bugs are easy to locate
| Mechanism | How it narrows the search |
|---|---|
| **Mirror test layout** | `src/vibechem_core/blocks/preprocess/snv.py` ↔ `tests/blocks/preprocess/test_snv.py`. A failing test names the module |
| **Package boundaries** (import-linter) | A bug in `core` can only come from `core`; engine bugs can't hide in blocks |
| **External libraries only inside block files** | A bug from a reused library is always in one wrapped block (TECH_STACK.md §3.1) |
| **Package READMEs** | Each package states purpose, public API and dependencies — Claude Code reads one README, not the whole repo |
| **Error codes** | Every error carries a code (DATA_MODEL.md §7) defined in exactly one module; search for the code → origin |
| **Trace IDs + structured logs** | Each run/node/task logs `run_id`, `node_id`, `block_id`; a failing node points to one block file |
| **Golden node snapshots** | The golden test stores each node's output hash; on failure it reports the **first node whose output changed** |
| **Small steps, squash-merged** | One TASKS.md step = one commit on the phase branch; if the phase branch turns red, the cause is the last squash commit |
| **Last green commit** | Nightly records the last green commit; `git bisect` between it and the failing commit finds the exact change |

## 6. Bug protocol
Short form and order of work: CLAUDE.md §7 (`/bug <issue>`). Additional rules:
- Bug fixes branch from and merge into the **active phase branch**. A bug that must reach `main` before the gate (e.g. it breaks the last released build) → Quan decides; Claude Code stops with `QUESTION`.
- If the cause is in a reused library: pin a working version, work around it in our wrapper, and draft an upstream issue for Quan to post — don't patch the library's code inside our repo unless it is vendored.
- Scientific logic → Quan; engine/infra/C++/packaging → K backlog row until demo v0.

**User bug reports** use the GitHub issue form: steps to reproduce, expected vs actual, "Copy diagnostics" output (versions, OS, last errors, run/node IDs — no user data), and optionally the pipeline file.

## 7. Definition of Done (every TASKS.md step) — same list as CLAUDE.md §6
- [ ] Only the step's files (plus tests, docs, CHANGELOG, TASKS.md tick, PROGRESS.md) changed.
- [ ] Plan as executed and reuse decision recorded in the PR; TECH_STACK.md §11 updated if a candidate was evaluated.
- [ ] New/changed behaviour has tests (unit + reference/property for algorithms, incl. wrapped libraries).
- [ ] Full `scripts/check.py --fast` PASS locally; CI green on 3 OS.
- [ ] Docs updated if behaviour, fields or dependencies changed (DATA_MODEL, TECH_STACK, METHODS); `THIRD_PARTY.md` if code was copied; CHANGELOG entry if user-visible.
- [ ] PR template complete (incl. estimate vs actual checkpoints), health summary pasted, code-review run.
- [ ] PROGRESS.md updated (Now, Step log, K backlog row if applicable).
- [ ] Handoff note deleted; labels set; merged with `merge_step.py` (👤 steps: Quan merges).

## 8. Review checklists
**Quan — algorithm spot-check (at the phase gate, or any time on a merged step PR)**
1. Do the `# Step N:` comments match the method in the cited paper / METHODS.md?
2. If a library is wrapped: does its definition match METHODS.md (e.g. MSC reference = mean spectrum, SG edge mode)?
3. Are defaults sensible for NIR/Raman/FTIR?
4. Does the reference test use a trusted expected value from an independent source?
5. Is the block marked `fitted` correctly (does it learn anything from data)?
6. Edge cases: constant spectra, one sample per group, missing values, tiny datasets?
A problem found after merge → open an issue (`S1` if a number is wrong) and `/bug` it.

**K — infrastructure review (from demo v0; until then each item goes into the PROGRESS.md backlog)**
1. Does the change respect package boundaries and the block contract?
2. Error handling: typed errors with codes; no silent failures?
3. Resource safety: memory, threads, file handles, GIL release in C++?
4. API/format changes reflected in DATA_MODEL.md with migrations?
5. Cross-platform: paths, line endings, Windows spawn behaviour, frozen-bundle behaviour?
6. New dependency: licence, maintenance, wheels for all OS on Python 3.14, size impact; was reuse actually considered?

## 9. Manual QA checklists
### 9.1 Phase gate (≈ 30 minutes, on Quan's own machine)
Use the items that exist at that phase:
| Item | From phase |
|---|---|
| 1. Install from the latest CI installer artifact of the phase branch; app starts within 5 s | 0 (skeleton) |
| 2. Run the skeleton/reference pipeline; result matches the reference report | 0 (skeleton), 2 (CLI) |
| 3. Run with 1 core and with all cores; same metrics | 2 |
| 4. Try a leaky pipeline; it is blocked with a clear message | 2 |
| 5. Import the reference CSV; roles suggested correctly | 4 |
| 6. Change one parameter; only downstream blocks re-run | 4 |
| 7. Cancel a long run; app stays responsive | 4 |
| 8. Close and reopen the project; everything is restored | 4 |
| 9. Switch language EN → JA → VI; no missing strings | 4 |
| 10. Export a report; numbers and references are correct | 6 |
Write findings as GitHub issues labelled `qa-gate`. S1/S2 findings block the phase merge.

### 9.2 Release (on clean machines/VMs for each OS)
All §9.1 items, plus: first-launch guide works (unsigned app warnings), update check shows the new version, uninstall leaves no running processes, checksums match, macOS Intel and Apple Silicon both tested.

## 10. Severity and triage
| Severity | Definition | Response |
|---|---|---|
| **S1 — Silent wrong result** | Numbers wrong without an error, or leakage | Stop all feature work (`S1_BUG`); fix first; add reference/leakage test; note in release notes |
| **S2 — Crash / data loss** | App or engine crash, project not restorable, nightly red | Fix before the next step in the phase |
| **S3 — Broken feature** | Feature fails with an error | Fix within the current phase |
| **S4 — Cosmetic / UX** | Layout, wording, minor annoyance | Backlog; batch with UI work |

## 11. Health metrics tracked per phase (in the gate report)
Tests passing on 3 OS · coverage per package · blocks with reference tests / total blocks · open S1/S2 bugs (target 0) · nightly pass rate · speed-up on 8 cores · installer size · **estimate accuracy** (planned vs actual checkpoints per step) · reuse ratio (steps that reused/wrapped vs built) · stops per phase by code.
