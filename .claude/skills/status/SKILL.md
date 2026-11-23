---
description: Summarise VibeChem progress in plain language — phase, steps done, current/paused/stopped steps, what Quan must do. Use when Quan types /status or asks "where are we?".
disable-model-invocation: true
allowed-tools: Bash(git fetch *) Bash(git log *) Bash(git show *) Bash(gh pr list *) Bash(gh pr view *) Bash(gh issue list *) Bash(gh run list *) Read
---

Read-only. Change nothing.

1. `git fetch --all --prune`.
2. Read `docs/TASKS.md` and `docs/PROGRESS.md` **as they are on the active phase branch** (`git show origin/phase-<N>:docs/PROGRESS.md`), not only the local copy.
3. `gh pr list --state open`, `gh issue list --label S1 --label S2 --state open`, latest nightly run (`gh run list --workflow nightly.yml --limit 1`) once it exists.

Answer in this order, short:
- **Phase:** N — name · steps ticked x/y · phase PR link
- **Just finished:** last 3 merged steps (date, PR)
- **In progress / paused / stopped:** step, PR, checkpoint, machine, stop code
- **Needs you:** each item with the exact action
- **Health:** nightly result, open S1/S2 bugs, red PRs
- **Next:** the command Quan should type
