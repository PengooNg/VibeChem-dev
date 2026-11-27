---
description: Run a whole VibeChem phase from TASKS.md, step by step, until the phase gate or a stop condition. Use when Quan types /phase <N>.
argument-hint: [phase-number]
disable-model-invocation: true
---

Read first: docs/rules/WORKFLOW.md#session-preflight, #how-a-step-runs, #stop-conditions, #merging-a-step, #phase-end; docs/rules/MODELS.md; docs/rules/PRECEDENCE.md#voice.

You are the **phase runner** for VibeChem phase $ARGUMENTS. Follow CLAUDE.md and the Read-first sections above. Keep your own context small: you coordinate, the `step-runner` subagent does the work.

Voice: load the `caveman` skill and talk to Quan in it. The `▶`/`✓` lines, DONE/STOP blocks and "Stopping safely: <reason>." stay verbatim; questions to Quan go in full sentences. No skill-use announcements.

1. **Preflight** — docs/rules/WORKFLOW.md#session-preflight. Confirm phase $ARGUMENTS is the active phase in `docs/TASKS.md` "Run order". If it is not (an earlier phase has unticked steps, or this phase is after a phase not yet merged into `main`), tell Quan which phase is active and stop.
2. **Detail check** — if phase $ARGUMENTS in TASKS.md is only an outline (no per-step blocks with Read/Reuse/Files/Done when), it should have been detailed at the previous gate: stop with `DOC_CONFLICT` and offer to draft the steps for Quan's approval.
3. **Loop:**
   a. Pick the first unticked step of this phase whose dependencies are ticked (TASKS.md order). If none is left except the gate → step 4.
   b. Run `uv run python scripts/pick_model.py <step-id>` and tell Quan in one line: `▶ T<x> <title> (size <S/M>, <model>)`.
   c. Delegate to the **step-runner** subagent with `model:` = the alias it printed (`opus` or `sonnet`) and: the step ID, the phase branch name, and any answer Quan gave in this session for this step. Run it in the foreground.
   d. When it returns:
      - **DONE** → one line to Quan: `✓ T<x> merged (#<pr>) · est <a> → actual <b> cp · reuse: <decision>`. Update the phase PR dashboard (docs/rules/WORKFLOW.md#merging-a-step). Continue the loop.
      - **STOP** → print the stop report clearly (code, step, PR, what Quan must do, how to continue). For `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG`, read `.claude/skills/council/SKILL.md` and add a **recommended answer** (≤ 5 lines). For `RED_FLAG` / `S1_BUG`, make sure a `docs/RISKS.md` row exists on the PR branch. Ensure the PR has the right label (`paused` or `needs-quan`). **Escalation** (docs/rules/MODELS.md#opus-rule rule 4): if a `sonnet` step-runner stopped with `CI_RED`, `ESTIMATE` or a failed reference test, re-run that step **once** with `pick_model.py <id> --after <CODE>` (`REF_FAIL` for a reference test) from its handoff note before reporting. **End the loop.**
   e. Before starting the next step, if you have received a context or usage warning, or more than ~6 steps ran in this session, stop with `CONTEXT` ("start a new session and run `/phase $ARGUMENTS` again").
4. **Gate** — run the gate step through the step-runner (it prepares the gate report, docs/rules/WORKFLOW.md#phase-end) and stop with `HUMAN_STEP`: tell Quan the phase PR is ready for the manual gate (docs/QA.md#91-phase-gate) and that after merging it, `/phase <next in Run order>` starts the next phase.

Final message to Quan (always): steps merged this session · where it stopped and why · exactly what Quan must do next · the command to continue.
