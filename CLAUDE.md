# CLAUDE.md — rules for working on VibeChem

> Place this file at the repository root. Claude Code reads it automatically at the start of every session.
> v0.8 · 2026-11-22 · Part A (how to think and work) is adapted from the four principles in `multica-ai/andrej-karpathy-skills` (MIT), based on Andrej Karpathy's observations of common LLM coding mistakes. Part B (§1–§15) holds VibeChem's own rules; other docs cite these as "CLAUDE.md §N". When Part B is more specific, Part B wins.
> v0.9: UI steps get a visual check with Playwright CLI and design review (Impeccable critique/audit, break-ui); Humanizer for human-facing prose; GitHub and Playwright MCP servers removed to save tokens (§13).
> v0.8: **phase mode** (§3, §14): `/phase N` runs a whole phase step by step; steps auto-merge into a `phase-N` branch; plans proceed unless a stop condition fires (§14.3); `docs/PROGRESS.md` log; K deferred until demo v0 (§15); two-machine rules (§8.4).

---

# Part A — How to work (always applies)

These rules trade speed for care. For a trivial change (typo, one-line doc fix) use judgment and skip the ceremony, but never skip tests or the "never do" list (§4).

## A1. Think before coding
- **State your assumptions** explicitly in the plan. If an assumption changes behaviour, results or the architecture, it is a stop condition (§14.3) — don't pick silently.
- **Show alternatives** when a request can be read more than one way, and say which one you'd choose and why.
- **Push back** when a simpler approach exists or a request conflicts with the docs. Say so before writing code.
- **When something is unclear, stop.** Name exactly what is confusing and ask one short question. A question costs the user seconds; a wrong guess costs a review and a rewrite.
- **Never invent facts:** field names, error codes, port types, file formats, library APIs or paper equations. Look them up (DATA_MODEL.md, METHODS.md, and **Context7 for library APIs at the pinned version** — §13) or ask.
- List any assumptions still open at the end of the plan and of the PR description.

## A2. Simplicity first
- Write the **minimum code that meets the step's "Done when"** — nothing speculative.
- No features nobody asked for, no abstraction used once, no configurability nobody asked for, no error handling for situations that cannot happen. (Validating real external input — files, API requests, user parameters — is required, not speculative.)
- **The cheapest code is code we don't write:** prefer an existing library or our own existing code (reuse first, §12) over new code.
- Test: would a senior engineer call this overcomplicated? If yes, simplify before marking ready.
- Simple and readable beats clever: explicit steps that match the paper (§5) are preferred over dense one-liners.

## A3. Surgical changes
- **Touch only what the step needs.** Every changed line must trace back to the step in TASKS.md or the user's request.
- Don't "improve" nearby code, comments or formatting; don't refactor what isn't broken; match the existing style.
- Clean up only your own mess: remove imports, variables and functions that *your* change made unused.
- Pre-existing dead code or a bug outside the step: **mention it** in the PR and in PROGRESS.md notes — don't delete or fix it silently.
- If the docs are wrong or incomplete, stop and propose a doc change; don't work around them in code.

## A4. Goal-driven execution
- Turn every task into **checkable goals** before coding. "Fix the bug" → write a test that reproduces it, then make it pass. "Add MSC" → reference test against an independent value passes, `check.py` is green.
- For multi-step work, write a short plan where **each checkpoint has its own check** (which test or command proves it is done).
- Loop until the checks pass. Don't declare success on reasoning alone — run the tests.
- The step's **"Done when"** in TASKS.md is the success criterion. If it is too vague to check, that is a stop condition.

**Signs these rules are working:** small diffs, simple first drafts, questions asked before implementing rather than after a mistake, few rewrites in review.

---

# Part B — VibeChem specifics

## 1. What VibeChem is
A free, open-source (GPL-3.0-or-later) desktop app for chemometrics on vibrational and hyperspectral spectra. Python engine and blocks, C++20 kernels, React/TypeScript UI, Electron shell. Built mostly by AI; owner and reviewer is **Quan** (algorithms, product). **K** (architecture, infrastructure, C++, packaging) joins at demo v0 — until then see §15.

## 2. Doc map — read only what the step tells you
| Need | File |
|---|---|
| The step you are doing (what to read, files, size, reuse candidates, done criteria) and the phase run order | `docs/TASKS.md` |
| What happened so far, open stops, K review backlog | `docs/PROGRESS.md` |
| What the product does, feature IDs (F-xx) | `docs/PRD.md` |
| Every function, its priority and likely reuse source | `docs/FUNCTION_CATALOG.md` |
| System design, ADRs, technical decisions | `docs/ARCHITECTURE.md` |
| Versions, folder layout, package boundaries, conventions, commands, CI, branches, **reuse register**, legal files | `docs/TECH_STACK.md` |
| Exact field names, endpoints, events, error codes, formats | `docs/DATA_MODEL.md` |
| Algorithm definitions, references, tolerances | `docs/METHODS.md` (from T1.04) |
| Colours, type, layout, components, tooltips | `docs/UI_GUIDE.md` |
| Tests, quality levels, bug protocol, definition of done, phase-gate checklist | `docs/QA.md` |
| Which skills, plugins and MCP tools to use for this step | `docs/TOOLS.md` (§3 row for your step) |
Before editing a package, also read that package's `README.md`. The owner's manual and project plan are kept outside the repo; you don't need them.

## 3. How a step runs
A step runs either inside `/phase N` (normal) or alone via `/step <ID>`. In phase mode the main session is the **phase runner** and each step is executed by the **step-runner** subagent (`.claude/agents/step-runner.md`) so every step starts with a fresh context.

1. **Prepare:** read the step in `docs/TASKS.md`, its row in `docs/TOOLS.md` §3, and only the files/sections the step lists. Check dependencies are ticked; if not → stop (§14.3 `DEPENDENCY`).
2. **Already started?** `gh pr list --search "[T<x>]" --state open`. If a PR exists, follow **Resuming** (§8.3).
3. **Plan** (written, not waited on): assumptions and open questions (A1) · reuse scan and estimate (§12) · tools for this step (§13) · files to create/change (only those listed, plus tests) · checkpoints, each with the command that proves it done (A4). Put the plan in `docs/handoff/<step-id>.md` and in the draft PR description.
   - **In phase mode do not wait for approval.** Proceed unless a stop condition in §14.3 applies. If one applies, stop *before* writing code.
   - With `/step` and an explicit "wait for my approval", wait.
4. **Branch** from the current phase branch: `git switch phase-<N> && git pull && git switch -c t<step>-<short-name>` (e.g. `t1-07-snv-msc`). Never commit to `main` or directly to `phase-*`.
5. **Checkpoints, one at a time.** After each: `check.py --fast --only <area>` → commit (`T1.07 cp2: MSC block + tests`) → push → update the handoff note and the PR **Status** line.
6. **After the first checkpoint** open a **draft PR** with base `phase-<N>`:
   - Title `[T1.07] <step title>` · label `in-progress` · description starts with the Status line (§8.1).
7. If the work grows beyond ~1.5× the planned checkpoints → stop (§14.3 `ESTIMATE`).
8. **Finish:** quality duties (§6), then merge (§14.2). In phase mode return a one-paragraph DONE report to the phase runner.

## 4. Never do
- Never invent API fields, file-format fields, error codes or port types — use `docs/DATA_MODEL.md`; propose additions there first.
- Never add a dependency that is not in `docs/TECH_STACK.md` §1 or approved from its reuse register (§11 there).
- Never build from scratch something the reuse register or §12 search shows already exists, without Quan's explicit approval.
- Never copy code from another project unless its licence is GPL-3.0-compatible; ported code keeps the original copyright, gets a source header, and is listed in `THIRD_PARTY.md`.
- Never trust an external library's numbers blindly: every reused algorithm gets the same reference tests as our own code, with expected values from an independent source.
- Never use pickle (or `allow_pickle=True`) for anything saved or shared.
- Never loosen a test tolerance, delete/skip a test, or regenerate golden files without saying so explicitly in the PR — in phase mode this is a stop condition (`RED_FLAG`).
- Never bypass the block contract (`vibechem_core/block.py`) or import across forbidden package boundaries (TECH_STACK.md §3.1).
- Never fit anything on validation/test data; fitted steps use `fit` on training rows only.
- Never use global random state; accept a `numpy.random.Generator`.
- Never hard-code user-visible text; use i18n keys (EN/JA/VI).
- Never make network calls from the app or engine (except the update check in the Electron main process).
- Never introduce a new architectural pattern without an ADR in `docs/ARCHITECTURE.md` §7.
- Never stop in the middle of an edit, leaving a file half-written or the branch uncommitted (§8).
- Never commit tokens or secrets; credentials come from environment variables only.
- **Never merge into `main`, push to `main` or `phase-*` directly, force-push, rewrite history, delete branches other than your own merged step branch, or change repository settings, rulesets or labels' meaning.** Merging a step PR into its phase branch goes only through `scripts/merge_step.py` (§14.2). Merging `phase-N → main` is always Quan's action.
- Never merge a step marked 👤 — prepare it and stop (§14.3 `HUMAN_STEP`).

## 5. Block template and comment style
Every block is one file. Header docstring, typed parameters, numbered `# Step N:` comments that match `docs/METHODS.md`, so a reviewer can check each line against the paper. When a block wraps an external library, the `# Step` comments describe what the library call does and the header names the library (the `Implementation:` line). Keep blocks as simple as the method allows (A2).

```python
# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/snv.py
"""
Block:          Standard Normal Variate (SNV)
Class:          preprocess
Ports:          in  -> spectra : Spectra
                out -> spectra : Spectra
Reference:      Barnes, Dhanoa & Lister (1989), Appl. Spectrosc. 43(5), 772-777
METHODS:        docs/METHODS.md#snv
Implementation: own NumPy code (simpler than wrapping; see TECH_STACK.md §11)
Fitted:         No (row-wise transform; safe inside CV without refitting)
Reviewers:      algorithm -> Quan | structure -> K
"""
from dataclasses import dataclass

import numpy as np

from vibechem_core.block import Block, Param, port
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError


@dataclass(frozen=True)
class SNVParams:
    ddof: int = Param(1, choices=(0, 1), tooltip_key="blocks.preprocess.snv.params.ddof.tip")


class SNV(Block):
    block_id = "preprocess.snv"
    version = "1.0.0"
    icon = "glyph-snv"
    references = ("barnes1989snv",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = SNVParams

    def apply(self, spectra: SpectralDataset, params: SNVParams) -> SpectralDataset:
        X = spectra.X

        # Step 1: Mean of each spectrum over all wavelengths (one value per row)
        row_mean = X.mean(axis=1, keepdims=True)

        # Step 2: Standard deviation of each spectrum
        row_std = X.std(axis=1, ddof=params.ddof, keepdims=True)

        # Step 3: Reject flat spectra (std = 0 would divide by zero)
        flat_rows = np.flatnonzero(row_std.ravel() == 0)
        if flat_rows.size > 0:
            raise BlockInputError(
                code="BLOCK_CONSTANT_SPECTRA",
                params={"rows": flat_rows.tolist()},
            )

        # Step 4: Centre and scale each spectrum individually
        X_snv = (X - row_mean) / row_std

        return spectra.with_X(X_snv, history=f"SNV(ddof={params.ddof})")
```
Other conventions (typing, docstrings, C++, TypeScript, SPDX headers): `docs/TECH_STACK.md` §4–6.

## 6. Quality duties before merging a step (QA.md §7)
1. Every new or changed function has tests in the mirrored test file: unit tests, plus reference or property tests for algorithms (including wrapped libraries). Bugs get a regression test.
2. Run the **full** `uv run python scripts/check.py --fast` until everything is PASS.
3. Regenerate `reports/reference_report.md` (done by `check.py`) and check that new methods appear in it.
4. Paste the **health summary** printed by `check.py` into the PR description.
5. Fill every section of the PR template: TASKS step, files changed, tests added, docs updated, **plan as executed**, **reuse decision** (§12), **tools used** (§13), estimate vs actual checkpoints, assumptions, anything you were unsure about, unrelated issues noticed but not touched (A3).
6. **Diff self-review (A2, A3):** run the **code-review** plugin (or `/review` if missing) on the branch diff; for steps marked 🔒 in TOOLS.md §3 also run **`/security-review`**; for UI steps also do the **visual check** (§13.1). Fix what is in scope and list the rest. Then check the red flags in QA.md §4. Any red flag you cannot undo → stop (`RED_FLAG`).
7. If a dependency was added: update TECH_STACK.md §1 and §11 and `THIRD_PARTY.md` (if code was copied) in the same PR. Update `CHANGELOG.md` if behaviour changed.
8. Tick the step in `docs/TASKS.md` (status overview) in the same PR.
9. **Update `docs/PROGRESS.md`** in the same PR: "Now" table, one Step-log row, and — if the step's reviewer tag includes K or a dependency/ADR changed — one **K review backlog** row (§15).
10. Delete `docs/handoff/<step-id>.md`, set the Status line to `Status: complete — merging`, remove `in-progress`/`paused` labels (add `k-review` if a backlog row was written), mark the PR **ready for review**.

## 7. When something fails — bug protocol (A4 applied; full version: QA.md §6)
Use the **debug** skill alongside this protocol; this order wins if they differ.
1. **Reproduce**: write the smallest failing test that shows the bug; commit it first. This test is the success criterion.
2. **Locate**, in this order, and stop at the first that points somewhere:
   failing test path (tests mirror source paths) → error code origin (DATA_MODEL.md §7 lists the defining module) → `node_id`/`block_id`/`trace_id` in logs → golden test's first divergent node → `git bisect` between the last green commit and now.
3. **Read only** that module, its package README, its tests and the relevant METHODS.md / DATA_MODEL.md section. If the failure involves a library call, check its documented behaviour for our pinned version with Context7 before assuming a bug.
4. **Explain** the root cause in 2–3 sentences in the PR before changing code. If the cause is inside a reused library, say so; prefer pinning a version, a documented workaround or an upstream issue over patching vendored code.
5. **Fix** in the smallest scope (A3); no unrelated refactoring.
6. **Verify**: the new test passes, then the module's tests, then `check.py --fast`. The new test stays as a regression test.
7. **Report** in the PR: Root cause · Fix · Test added · Possibly affected areas. Bug PR title: `[BUG #<issue>] <short description>`; base = the current phase branch.
- A bug found **during** a step that is inside the step's scope: fix it in the step. Outside the scope: open an issue, note it in PROGRESS.md, continue the step.
- A suspected **S1** (silent wrong number, leakage) anywhere: stop (`S1_BUG`) — Quan decides before any further feature work.
- A bug in your own step that CI keeps showing red: up to **2 fix attempts**, then stop (`CI_RED`).

## 8. Status, context limits and resuming
### 8.1 Status line (first line of every step PR description)
`Status: <state> · next: <action> · machine: <$VIBECHEM_MACHINE> · updated <YYYY-MM-DD HH:MM>`
States: `cp2/4 done` · `PAUSED at cp2/4` · `STOPPED: <CODE>` · `complete — merging`.

### 8.2 Stop safely, never mid-section
You cannot see exactly how much context or usage is left, so work so that an interruption at any moment is harmless.

**Always:** keep every checkpoint small (one block, one module, one test group); after each checkpoint tests pass → commit → push → update handoff note and Status line; never start a new file or large edit unless you expect to finish and commit it.

**Stop and hand off (`CONTEXT`) when:** the system warns that context is low or will be compacted · the step session is long (≈ 3 checkpoints, many large files read, repeated failed attempts) · a usage-limit warning appears · you notice you are re-reading files or losing track of earlier decisions.

**How to stop (any stop code, in this order):**
1. Finish or revert the edit in progress so every file is complete and valid.
2. Run the tests for the finished part; record failures rather than hiding them.
3. Commit (`T1.07 WIP cp3: <what is done>`) and push. If no PR exists yet, open the draft PR now.
4. Write/update `docs/handoff/<step-id>.md`:
   ```
   # Handoff — T1.07
   Branch: t1-07-snv-msc   Base: phase-1   Last commit: <hash>   PR: #<number>
   Stop code: CONTEXT   Machine: work-pc
   Plan: <link to plan section or copy>
   Done: cp1 SNV + tests; cp2 MSC + tests
   Not done: cp3 detrend (not started), cp4 cut
   Failing tests (if any): none
   Decisions made: MSC wraps chemotools
   Question for Quan (if any): —
   Files read that matter: docs/METHODS.md#msc, packages/core/src/vibechem_core/block.py
   Next action: implement detrend per METHODS.md#detrend, then property tests
   ```
5. PR: Status line `PAUSED at cp2/4` (for `CONTEXT`) or `STOPPED: <CODE>`; label `paused` (context) or `needs-quan` (any other code); comment with the question or the required action.
6. Report (to the phase runner, which tells Quan): **"Stopping safely: <reason>."** + step ID, PR, done, remaining, what Quan must do, and that `/resume` continues.

### 8.3 Resuming
Read CLAUDE.md, the step in TASKS.md and the handoff note; check out the branch; `git pull`; run the tests; apply Quan's answer if the stop was a question; switch the label back to `in-progress`; continue from "Next action". Do not redo finished checkpoints. If the session was cut off without a note, rebuild the note from the commit history first.

### 8.4 Two machines (work PC on weekdays, laptop on weekends)
- Every session starts with the **session preflight** (§14.1): fetch, clean tree, pull the phase branch, sync environments.
- Never leave work only on one machine: every stop ends with commit + push (§8.2).
- `$VIBECHEM_MACHINE` (set once per machine: `work-pc` / `laptop`) goes in the Status line and handoff note.
- If an open step PR is labelled `in-progress` (not `paused`) when a session starts, it may be running on the other machine or was cut off: ask Quan before touching it.

### 8.5 Status request (`/status`, or "where are we?")
Run `gh pr list --state open` and read `docs/TASKS.md` and `docs/PROGRESS.md` on the current phase branch. Answer with: current phase and branch · steps done this phase · step in progress (PR, checkpoint, machine) · paused/stopped steps and what Quan must do · open `needs-quan` items · open S1/S2 issues · phase PR link.

## 9. Commands
| Command | Use |
|---|---|
| `uv run python scripts/check.py --fast --only <area>` | After each checkpoint (`core`, `engine`, `native`, `app`) |
| `uv run python scripts/check.py --fast` | Before marking a PR ready (must be all PASS) |
| `uv run pytest <test file>` | One test file |
| `pnpm --dir app dev` | Run the app in development |
| `gh pr list --state open` | Steps in progress, paused, stopped |
| `gh pr checks <n> --watch` | Wait for CI on a PR |
| `uv run python scripts/merge_step.py <pr>` | The only way to merge a step PR (§14.2) |
Full list: `docs/TECH_STACK.md` §7.

## 10. Reviews
- Algorithms, defaults, reference tests, METHODS.md → **Quan** (spot-checks merged steps; full review at the phase gate).
- Engine, ports, scheduler, formats, API, C++, build, packaging, CI, new dependencies → **K** from demo v0; until then Quan approves and the item goes into the K review backlog (§15).
- CODEOWNERS routes everything to Quan until K joins.

## 11. When unsure
See A1 and §14.3: ask before guessing. Prefer a short stop with one clear question over a wrong assumption.

## 12. Reuse first, and estimate before committing (A2 applied)
Writing code we could have reused wastes the owner's time and money. Before planning any implementation:

**12.1 Search (in this order, stop when you find a good fit)**
1. What we already have: this repo, the step's "Reuse" line in TASKS.md, TECH_STACK.md §11 reuse register, FUNCTION_CATALOG.md "Likely source" notes.
2. Libraries already in our stack: NumPy, SciPy, scikit-learn, pyarrow, React Flow, uPlot, etc. (check their current API with Context7, §13).
3. Maintained packages and templates: PyPI, conda-forge, npm, GitHub (search by method name + "python"/"typescript").
4. GPL-compatible code to port: Orange/Quasar (orange-spectroscopy, GPL-3.0), pengoo (only parts Quan provides from his local copy; pengoo itself is never copied wholesale into this repo — if the step needs pengoo files that aren't provided, stop `MISSING_INPUT`).
5. Only then: write our own.
If you cannot search the web in this session, list the candidates you know; if the step is M or larger, stop (`REUSE`) and ask Quan to confirm before building.

**12.2 Judge each candidate**
| Criterion | Acceptable |
|---|---|
| Licence | MIT, BSD, Apache-2.0, LGPL, GPL-3.0 (GPL-compatible) |
| Maintenance | Release or commit in the last ~18 months; issues answered |
| Quality | Has tests; used by others; correct against METHODS.md (we verify with our reference tests) |
| Fit | Covers most of what the step needs without forcing a different architecture |
| Cost | Install size, extra native dependencies, Windows/macOS/Linux wheels available, Python 3.14 support |
| Safety | No network calls, no pickle loading of shared files |

**12.3 Decide: reuse > wrap > port > build**
- **Reuse** as a dependency (add to TECH_STACK.md) when it fits well.
- **Wrap** it behind our block contract when the API differs.
- **Port** (copy + adapt) only for small, stable code from GPL-compatible sources, with header + `THIRD_PARTY.md`.
- **Build** only when nothing fits, or when our own code is clearly smaller and simpler than the dependency (e.g. SNV is 4 lines of NumPy; a 20 MB package for it is not worth it — A2 cuts both ways).

**12.4 Estimate before committing** — put this table in the plan:
| Option | What it covers | Licence / maintenance | Effort (checkpoints, ~files, ~lines) | Risks |
|---|---|---|---|---|
| Reuse/wrap `<package>` | … | … | … | … |
| Port from `<project>` | … | … | … | … |
| Build ourselves | … | — | … | … |
Recommendation: one line. Sizes: **S** = 1–2 checkpoints, **M** = 3–4 checkpoints (one session), **L** = more than 4.
An **L** estimate: split the step into `T<x>a`, `T<x>b` … in TASKS.md (same format, same total scope, dependencies kept) inside the first sub-step's PR and continue with `a`. If splitting would change the scope → stop (`ESTIMATE`).

**12.5 Stop and ask Quan (stop code `REUSE`, before any code) when:**
- A reusable option exists but you recommend building anyway.
- Building would be **M or larger** and no strong reuse option was found — show what you searched.
- The best option has a licence, maintenance or size concern.
- Your estimate is more than double the size given in TASKS.md.
- The reuse decision changes the architecture or adds a native dependency.
Adding a pure-Python dependency that is already listed as a candidate in TECH_STACK.md §11 for this step, with an acceptable licence and no concern above, does **not** need a stop: approve it in the PR and add a K review backlog row.

## 13. Skills, plugins and tools
The full list, rules and **per-step map** are in `docs/TOOLS.md`. Read your step's row there when planning and name the tools in the plan's *Tools* line. Short version:
- **Context7** (MCP) — check library APIs at the pinned version before writing or debugging library calls.
- **code-review** (+ `/security-review` on 🔒 steps) — before every merge (§6.6).
- **Playwright CLI** (`playwright-cli` skill, run through Bash) — open the dev app, click through, screenshot. The project uses the CLI, not the Playwright MCP server (fewer tokens). Automated e2e tests use `@playwright/test`.
- **Design:** **Impeccable** (steer: `typeset`, `layout`, `quieter`, `distill` …; review: `critique`, `audit`; finish: `polish`, `harden`, `clarify`), **ui-ux-pro-max** (checklist), Emil's **break-ui**, **prototype**, **review-animations**, **animation-performance**, plus **accessibility-review** and **ux-copy**. **UI_GUIDE.md wins** over every design skill; conflicts become a proposed UI_GUIDE.md change (stop `DOC_CONFLICT` if it blocks the step).
  - Impeccable limits: never `live` mode, never install its hook, never `init`/`document`/`extract` (they write PRODUCT.md/DESIGN.md — UI_GUIDE.md is the only design doc), never start a "new design" flow that fetches the online catalog; telemetry stays off.
  - Glyphs and the block widget follow UI_GUIDE.md §4/§6; while §4 is marked *draft*, the glyph-set step is 👤 (Quan's taste decides).
- **Humanizer** — on human-facing prose before merge: README, docs site, first-launch guide, EN tooltip/help text, release notes, CHANGELOG entries, paper drafts. Never on METHODS.md formulas, error messages tied to codes, CLAUDE.md, TASKS.md, PR status lines or code comments.
- **testing-strategy, architecture, debug, deploy-checklist, documentation** — QA, ADR, bug, release and doc steps.
- GitHub work uses `gh` only (no GitHub MCP).
These are development tools only: never app/engine dependencies (§4), never a reason to skip the docs. If one is missing, say so in the plan and continue without guessing (A1).

### 13.1 Visual check (every step that changes `app/`)
1. Start the dev app (`pnpm --dir app dev`); with Playwright CLI open each changed screen/state (empty, loading, normal, error, long JA/VI labels); save screenshots and attach them to the PR (not committed).
2. Run Impeccable `critique` and `audit` on the changed components, Emil `break-ui` on the changed views, and `accessibility-review` (WCAG 2.1 AA). Fix in-scope findings; list the rest in the PR.
3. If the step adds a user flow, add or extend an `@playwright/test` e2e test in `app/e2e/`.

## 14. Phase mode
### 14.1 Session preflight (every session, every machine)
1. `git fetch --all --prune`. If the working tree has uncommitted changes → stop and ask Quan (never discard them).
2. Find the active phase: the lowest phase in TASKS.md "Run order" with unticked steps. Its branch `phase-<N>` exists? If not, create it from `main`: `git switch main && git pull && git switch -c phase-<N> && git push -u origin phase-<N>`.
3. `git switch phase-<N> && git pull`. If `main` has commits the phase branch lacks (e.g. Dependabot), open a small PR `[SYNC] main → phase-<N>` and merge it with `merge_step.py` first.
4. Sync environments when they exist: `uv sync` (if `uv.lock` exists), `pnpm --dir app install --frozen-lockfile` (if `app/pnpm-lock.yaml` exists).
5. Open PRs: a `paused` or `needs-quan` step PR in this phase is handled first (§8.3; for `needs-quan` check whether Quan answered in the PR comments or the chat — if not, report it and stop). An `in-progress` PR → ask Quan (§8.4).

### 14.2 Merging a step
`uv run python scripts/merge_step.py <pr>` (created in T0.02) refuses unless: base is `phase-*`; PR is not draft; all CI checks are green; the step is not 👤; title starts with `[T`, `[BUG` or `[SYNC]`. It squash-merges with the PR title as the commit message and deletes the step branch. Before the script exists (T0.01–T0.02), stop with `HUMAN_STEP` and ask Quan to merge.
After the merge, update the **phase PR** (`phase-<N> → main`, draft, title `[PHASE N] <name>`; open it after the first merged step): its description is the live dashboard — steps done, current step, open stops, link to PROGRESS.md on the phase branch. Edit it with `gh pr edit`.

### 14.3 Stop conditions (stop the step *and* the phase loop)
| Code | When | What Quan gets |
|---|---|---|
| `HUMAN_STEP` | A 👤 step: do Claude Code's part, mark the PR ready, don't merge | What to check / do, and "merge the PR, then `/phase N`" |
| `REUSE` | Any §12.5 condition | The options table and your recommendation |
| `ESTIMATE` | Work > 1.5× plan, or a split would change scope | Why, and a re-plan or split proposal |
| `QUESTION` | An assumption that changes behaviour, results, defaults or the architecture; vague "Done when" | One short question with your suggested answer |
| `DOC_CONFLICT` | Docs contradict each other or the code; a field/code/type is missing in DATA_MODEL/METHODS | The conflict and a proposed doc change |
| `CI_RED` | Checks still red after 2 fix attempts, or flaky | Failing job, cause found so far |
| `RED_FLAG` | A QA.md §4 red flag you can't avoid (tolerance, deleted test, golden regeneration, files outside step) | The reason, for Quan to accept or reject |
| `S1_BUG` | Suspected silent wrong result or leakage, anywhere | Evidence (test, numbers) |
| `MISSING_INPUT` | Dataset, pengoo file, credential, tool or account needed and absent | Exactly what is needed and where to put it |
| `DEPENDENCY` | The step depends on an unticked step | Which step |
| `CONTEXT` | §8.2 limits | Resume with `/resume` |
| `DESTRUCTIVE` | The step seems to need deleting data, rewriting history or changing settings/rulesets | What and why |
Never stop for something you can answer from the docs. Never continue past a stop by guessing.

### 14.4 Phase end
When only the phase-gate step is left: run it (it is 👤): prepare the gate report in PROGRESS.md "Phase gates" (exit criteria with evidence, health summary on the phase branch, estimate-vs-actual per step, reuse ratio, ADRs to accept, QA.md §9.1 items for this phase, open issues), detail the next phase's steps in TASKS.md if they are only an outline, merge that PR into the phase branch, mark the phase PR **ready**, and stop with `HUMAN_STEP`. Quan does the manual gate and merges the phase PR into `main` (merge commit). The next `/phase` starts the next phase in Run order.

## 15. K deferred until demo v0
Demo v0 = the **Beta release at the end of Phase 6**. Until K joins:
- Wherever a doc says "K reviews/approves", **Quan approves** (or the stop conditions decide), and you add a row to the **K review backlog** in PROGRESS.md: step, PR, area (engine / CI / packaging / C++ / dependency / ADR), and what K should check (use the K checklist in QA.md §8).
- ADRs can be set to `Accepted (provisional — K to confirm)` by Quan at a phase gate.
- Phases run in numeric order; nothing waits for K. C++ work (Phase 3) follows TECH_STACK.md §5 strictly: every kernel has a Python reference, equivalence tests, sanitizer-clean CI and automatic fallback, and gets a K backlog row.
- When Quan says K has joined: CODEOWNERS and branch rules change (Quan does this), and the backlog is worked through as normal review issues.
