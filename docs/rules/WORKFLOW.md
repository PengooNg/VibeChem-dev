# Workflow: steps, stops, resuming, commands, phase mode

> Read this when you start a session, run, stop, resume or merge a step, or run a phase (phase, step, resume, status skills; step-runner). Moved verbatim from the old CLAUDE.md (how a step runs, status and resuming, commands, phase mode) on 2026-11-27.

## How a step runs
A step runs either inside `/phase N` (normal) or alone via `/step <ID>`. In phase mode the main session is the **phase runner** and each step is executed by the **step-runner** subagent (`.claude/agents/step-runner.md`) so every step starts with a fresh context.

1. **Prepare:** read the step in `docs/TASKS.md`, its row in `docs/TOOLS.md` §3, and only the files/sections the step lists. Check dependencies are ticked; if not → stop (docs/rules/WORKFLOW.md#stop-conditions `DEPENDENCY`).
2. **Already started?** `gh pr list --search "[T<x>]" --state open`. If a PR exists, follow **Resuming** (docs/rules/WORKFLOW.md#resuming).
3. **Plan** (written, not waited on): assumptions and open questions (A1) · reuse scan and estimate (docs/rules/CODING.md#reuse-first-and-estimate-before-committing) · tools for this step (docs/TOOLS.md#5-rules-for-the-tools) · files to create/change (only those listed, plus tests) · checkpoints, each with the command that proves it done (A4). Put the plan in `docs/handoff/<step-id>.md` and in the draft PR description.
   - **In phase mode do not wait for approval.** Proceed unless a stop condition in docs/rules/WORKFLOW.md#stop-conditions applies. If one applies, stop *before* writing code.
   - With `/step` and an explicit "wait for my approval", wait.
4. **Branch** from the current phase branch: `git switch phase-<N> && git pull && git switch -c t<step>-<short-name>` (e.g. `t1-07-snv-msc`). Never commit to `main` or directly to `phase-*`.
5. **Checkpoints, one at a time.** After each: `check.py --fast --only <area>` → commit (`T1.07 cp2: MSC block + tests`) → push → update the handoff note and the PR **Status** line.
6. **After the first checkpoint** open a **draft PR** with base `phase-<N>`:
   - Title `[T1.07] <step title>` · label `in-progress` · description starts with the Status line (docs/rules/WORKFLOW.md#status-line).
7. If the work grows beyond ~1.5× the planned checkpoints → stop (docs/rules/WORKFLOW.md#stop-conditions `ESTIMATE`).
8. **Finish:** quality duties (docs/QA.md#7-per-step-duties), then merge (docs/rules/WORKFLOW.md#merging-a-step). In phase mode return a one-paragraph DONE report to the phase runner.

## Status, context limits and resuming
### Status line
_(first line of every step PR description)_
`Status: <state> · next: <action> · machine: <$VIBECHEM_MACHINE> · updated <YYYY-MM-DD HH:MM>`
States: `cp2/4 done` · `PAUSED at cp2/4` · `STOPPED: <CODE>` · `complete — merging`.

### Stop safely, never mid-section
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

### Resuming
Read CLAUDE.md, the step in TASKS.md and the handoff note; check out the branch; `git pull`; run the tests; apply Quan's answer if the stop was a question; switch the label back to `in-progress`; continue from "Next action". Do not redo finished checkpoints. If the session was cut off without a note, rebuild the note from the commit history first.

### Two machines
_(work PC on weekdays, laptop on weekends)_
- Every session starts with the **session preflight** (docs/rules/WORKFLOW.md#session-preflight): fetch, clean tree, pull the phase branch, sync environments.
- Never leave work only on one machine: every stop ends with commit + push (docs/rules/WORKFLOW.md#stop-safely-never-mid-section).
- `$VIBECHEM_MACHINE` (set once per machine: `work-pc` / `laptop`) goes in the Status line and handoff note.
- If an open step PR is labelled `in-progress` (not `paused`) when a session starts, it may be running on the other machine or was cut off: ask Quan before touching it.

### Status request
_(`/status`, or "where are we?")_
Follow `.claude/skills/status/SKILL.md` (read-only; change nothing).

## Commands
| Command | Use |
|---|---|
| `uv run python scripts/check.py --fast --only <area>` | After each checkpoint (`core`, `engine`, `native`, `app`) |
| `uv run python scripts/check.py --fast` | Before marking a PR ready (must be all PASS) |
| `uv run pytest <test file>` | One test file |
| `pnpm --dir app dev` | Run the app in development |
| `gh pr list --state open` | Steps in progress, paused, stopped |
| `gh pr checks <n> --watch` | Wait for CI on a PR |
| `uv run python scripts/merge_step.py <pr>` | The only way to merge a step PR (docs/rules/WORKFLOW.md#merging-a-step) |
Full list: `docs/TECH_STACK.md` §7.

Test and check output is shortened by a hook. If you need the full output, read `.cache/test-logs/latest.log` — don't re-run with pipes.

## Phase mode
### Session preflight
_(every session, every machine)_
1. `git fetch --all --prune`. If the working tree has uncommitted changes → stop and ask Quan (never discard them).
2. Find the active phase: the lowest phase in TASKS.md "Run order" with unticked steps. Its branch `phase-<N>` exists? If not, create it from `main`: `git switch main && git pull && git switch -c phase-<N> && git push -u origin phase-<N>`.
3. `git switch phase-<N> && git pull`. If `main` has commits the phase branch lacks (e.g. Dependabot), open a small PR `[SYNC] main → phase-<N>` and merge it with `merge_step.py` first.
4. Sync environments when they exist: `uv sync` (if `uv.lock` exists), `pnpm --dir app install --frozen-lockfile` (if `app/pnpm-lock.yaml` exists).
5. Open PRs: a `paused` or `needs-quan` step PR in this phase is handled first (docs/rules/WORKFLOW.md#resuming; for `needs-quan` check whether Quan answered in the PR comments or the chat — if not, report it and stop). An `in-progress` PR → ask Quan (docs/rules/WORKFLOW.md#two-machines).

### Merging a step
`uv run python scripts/merge_step.py <pr>` (created in T0.02) refuses unless: base is `phase-*`; PR is not draft; all CI checks are green; the step is not 👤; title starts with `[T`, `[BUG` or `[SYNC]`. It squash-merges with the PR title as the commit message and deletes the step branch. Before the script exists (T0.01–T0.02), stop with `HUMAN_STEP` and ask Quan to merge.
After the merge, update the **phase PR** (`phase-<N> → main`, draft, title `[PHASE N] <name>`; open it after the first merged step): its description is the live dashboard — steps done, current step, open stops, link to PROGRESS.md on the phase branch. Edit it with `gh pr edit`.

### Stop conditions
_(stop the step *and* the phase loop)_
| Code | When | What Quan gets |
|---|---|---|
| `HUMAN_STEP` | A 👤 step: do Claude Code's part, mark the PR ready, don't merge | What to check / do, and "merge the PR, then `/phase N`" |
| `REUSE` | Any docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.5) condition | The options table and the recommended answer (drafted with `council`) |
| `ESTIMATE` | Work > 1.5× plan, or a split would change scope | Why, and a re-plan or split proposal (drafted with `council`) |
| `QUESTION` | An assumption that changes behaviour, results, defaults or the architecture; vague "Done when" (first try `intent-driven-development` to turn it into AC lines) | One short question with the recommended answer (drafted with `council`) |
| `DOC_CONFLICT` | Docs contradict each other or the code; a field/code/type is missing in DATA_MODEL/METHODS | The conflict and a proposed doc change |
| `CI_RED` | Checks still red after 2 fix attempts, or flaky | Failing job, cause found so far |
| `RED_FLAG` | A QA.md §4 red flag you can't avoid (tolerance, deleted test, golden regeneration, files outside step) | The reason and the recommended answer (drafted with `council`), for Quan to accept or reject; a `docs/RISKS.md` row |
| `S1_BUG` | Suspected silent wrong result or leakage, anywhere | Evidence (test, numbers); a `docs/RISKS.md` row |
| `MISSING_INPUT` | Dataset, pengoo file, credential, tool or account needed and absent | Exactly what is needed and where to put it |
| `DEPENDENCY` | The step depends on an unticked step | Which step |
| `CONTEXT` | docs/rules/WORKFLOW.md#stop-safely-never-mid-section limits | Resume with `/resume` |
| `DESTRUCTIVE` | The step seems to need deleting data, rewriting history or changing settings/rulesets | What and why |
Never stop for something you can answer from the docs. Never continue past a stop by guessing.

### Phase end
When only the phase-gate step is left: run it (it is 👤):
1. Prepare the gate report in PROGRESS.md "Phase gates": exit criteria with evidence, health summary on the phase branch, estimate-vs-actual per step, reuse ratio, ADRs to accept, QA.md §9.1 items for this phase, open issues.
2. Audits, each read by path from `.claude/skills/` or run as an agent: `ponytail-audit` (whole repo), `ponytail-debt` (`shortcut:` ledger), **mle-reviewer**, `production-audit` (from Phase 5), and the infrastructure checklist (QA.md §8, with cpp-reviewer / silent-failure-hunter). Findings go into `docs/RISKS.md`.
3. A `council` go/no-go note (≤ 5 lines) in the gate report.
4. Detail the next phase's steps in TASKS.md if they are only an outline, with `product-capability` (from PRD F-xx) and `intent-driven-development` (checkable "Done when" lines).
5. Merge that PR into the phase branch, mark the phase PR **ready**, and stop with `HUMAN_STEP`. Quan does the manual gate and merges the phase PR into `main` (merge commit). The next `/phase` starts the next phase in Run order.
