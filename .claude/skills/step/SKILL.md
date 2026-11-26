---
description: Run exactly one VibeChem TASKS.md step (outside the phase loop). Use when Quan types /step <ID>, optionally adding "wait" to approve the plan first.
argument-hint: "[step-id] [wait]"
disable-model-invocation: true
---

Run VibeChem step $0 only. Do the session preflight (CLAUDE.md §14.1) first.

- If the second argument is `wait` ("$1"), write the plan (CLAUDE.md §3.3) and **show it to Quan and wait for approval** before any code. Then delegate to the `step-runner` subagent with the approved plan.
- Otherwise delegate directly to the `step-runner` subagent.

Report the DONE or STOP result to Quan in caveman voice (load the `caveman` skill; the DONE/STOP block stays verbatim; for a `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG` stop, read `.claude/skills/council/SKILL.md` and add a recommended answer of ≤ 5 lines), and say what to do next. Do not start another step.
