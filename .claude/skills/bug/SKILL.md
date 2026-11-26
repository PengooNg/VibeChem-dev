---
description: Fix a VibeChem GitHub issue with the bug protocol (failing test first, root cause before code). Use when Quan types /bug <issue-number>.
argument-hint: [issue-number]
disable-model-invocation: true
---

Fix GitHub issue #$ARGUMENTS following CLAUDE.md §7. Load the `ponytail` skill (full) before touching code; its bug rule applies: grep every caller of the function you touch and fix the root cause once in the shared code. Talk to Quan in caveman voice (load `caveman`), but the root cause and questions go in full sentences.

1. Session preflight (CLAUDE.md §14.1). Read the issue (`gh issue view $ARGUMENTS`), its severity label and attachments.
2. Branch `bug-$ARGUMENTS-<short>` from the active phase branch.
3. Write the smallest failing test that reproduces it; commit and push; open a draft PR `[BUG #$ARGUMENTS] …` with base = phase branch.
4. **Show Quan the failing test and your 2–3 sentence root cause, and wait for his OK** before changing code. (Bugs are the one place where approval is always required.)
5. Fix in the smallest scope, verify (CLAUDE.md §7.6), run `ponytail-review` on the diff (plus silent-failure-hunter for `packages/` or `scripts/`), fill the PR sections Root cause · Fix · Test added · Possibly affected areas, add a PROGRESS.md Step-log row (`BUG #$ARGUMENTS`).
6. Merge with `uv run python scripts/merge_step.py <pr>` once green. For **S1**, do not merge: mark ready and stop with `HUMAN_STEP` so Quan checks the corrected numbers in the reference report.
