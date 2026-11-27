---
description: Run exactly one VibeChem TASKS.md step (outside the phase loop). Use when Quan types /step <ID>, optionally adding "wait" to approve the plan first.
argument-hint: "[step-id] [wait]"
disable-model-invocation: true
---

Read first: docs/rules/WORKFLOW.md#session-preflight, #how-a-step-runs, #stop-conditions; docs/rules/MODELS.md.

Run VibeChem step $0 only. Do the session preflight (docs/rules/WORKFLOW.md#session-preflight) first.

- If the second argument is `wait` ("$1"), write the plan (docs/rules/WORKFLOW.md#how-a-step-runs) and **show it to Quan and wait for approval** before any code. Then delegate to the `step-runner` subagent with the approved plan.
- Otherwise delegate directly to the `step-runner` subagent.
- Model: before delegating, run `uv run python scripts/pick_model.py <step-id>` (add `--after <STOP_CODE>` when re-running after a stop, docs/rules/MODELS.md#opus-rule) and pass the printed alias (`opus` or `sonnet`) as the Agent tool `model` parameter. Show the model and the rule in the plan (`wait`) or the `▶` line.

Report the DONE or STOP result to Quan in caveman voice (load the `caveman` skill; the DONE/STOP block stays verbatim; for a `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG` stop, read `.claude/skills/council/SKILL.md` and add a recommended answer of ≤ 5 lines), and say what to do next. Do not start another step.
