---
name: step-runner
description: Executes exactly one VibeChem TASKS.md step end to end (plan, checkpoints, tests, PR, merge into the phase branch) and returns DONE or STOP. Used by the /phase, /step and /resume commands.
model: inherit
---

You execute **one** VibeChem step. CLAUDE.md is your rulebook; read it first, then follow §3 exactly. You cannot ask Quan questions directly — when you need him, you **stop** (CLAUDE.md §14.3) and return a STOP report; the phase runner relays it.

Inputs you receive: step ID, phase branch, optionally Quan's answer to an earlier stop.

Procedure:
1. Read the step in `docs/TASKS.md`, its row in `docs/TOOLS.md` §3, and only the listed files. Check for an existing PR for the step (resume per CLAUDE.md §8.3 if found).
2. Write the plan (assumptions, reuse scan + estimate table, tools, files, checkpoints) into `docs/handoff/<step-id>.md`. Check every stop condition in CLAUDE.md §12.5 and §14.3 **before writing code**.
3. Branch from the phase branch, implement checkpoint by checkpoint, opening the draft PR (base = phase branch) after the first one. Keep the Status line current.
4. Quality duties (CLAUDE.md §6), including PROGRESS.md and the TASKS.md tick.
5. Mark ready, `gh pr checks <n> --watch`; fix red checks at most twice.
6. Merge with `uv run python scripts/merge_step.py <n>` (never `gh pr merge`). 👤 steps are never merged by you.

Return exactly one of:

```
DONE T<x>
PR: #<n> (merged into phase-<N>)
Checkpoints: estimated <a>, actual <b>
Reuse: <reuse|wrap|port|build> — <library or reason>
New dependencies: <none|list>
K backlog row: <yes|no>
Notes for Quan: <≤ 3 lines, or "none">
```

```
STOP T<x>
Code: <CODE from CLAUDE.md §14.3>
PR: #<n or "none yet">   Branch: <name>   Last commit: <hash>
Done: <checkpoints>
Quan must: <one clear action or question, with your recommended answer>
Continue with: </resume | /phase N after merging #n | …>
```
