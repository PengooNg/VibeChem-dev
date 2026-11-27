---
description: Resume the VibeChem step that is paused or stopped, then continue its phase. Use when Quan types /resume, optionally followed by his answer to the last stop.
argument-hint: [answer to the last stop question]
disable-model-invocation: true
---

1. Session preflight (CLAUDE.md §14.1).
2. Find the step to resume: open PRs labelled `paused` or `needs-quan` in the active phase (`gh pr list --label paused --label needs-quan --state open`). If there are several, take the lowest step ID. If none, find an interrupted step (an open draft step PR without those labels, or a `docs/handoff/*.md` on a pushed branch) and rebuild its handoff note from the commit history (CLAUDE.md §8.3).
3. Quan's answer for this resume (may be empty): "$ARGUMENTS". If the stop was `QUESTION`, `REUSE`, `ESTIMATE`, `DOC_CONFLICT` or `RED_FLAG` and no answer is given here or in the PR comments, show Quan the question again and stop.
4. Delegate the step to the `step-runner` subagent with the answer. Record the answer in the handoff note and the PR ("Decision by Quan: …").
5. After DONE, continue exactly like `/phase` (its loop, step 3 onward) for the active phase.

Talk to Quan in caveman voice (load the `caveman` skill); DONE/STOP blocks, `▶`/`✓` lines and questions in full sentences stay as `/phase` describes.
