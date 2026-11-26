# Handoff — BUG #44
Branch: bug-44-gate-tilde-comment   Base: phase-1   Last commit: see PR #46   PR: #46
Stop code: QUESTION (Quan applies the gate revert, CLAUDE.md 13.2)   Machine: remote
Decision: Quan chose option A (2026-11-26): won't fix, gate back to phase-1, deny tests kept.
Done: revert patch prepared and checked in a throwaway worktree at HEAD: applies cleanly, gate identical to phase-1, 29 gate tests pass. Patch content is also in a PR #46 comment.
Patch: C:/Users/nmqua/AppData/Local/Temp/claude/072477f96f2482f1/31e26007-7219-40ab-b381-3d67e7f234d3/scratchpad/bug-44-revert.patch
  - scripts/permission_gate.py -> phase-1 version
  - scripts/tests/test_permission_gate.py: all 26 cases are deny tests (former allow cases pin the won't-fix)
  - CHANGELOG.md: #44 entry removed (no user-visible change)
  - docs/PROGRESS.md: step-log row = won't fix; Stops row resolved (option A)
Quan runs (at the PC):
  git switch bug-44-gate-tilde-comment && git pull
  git apply -v <patch path above>
  uv run pytest scripts/tests/test_permission_gate.py -q
  git commit -am "BUG #44: won't fix, gate back to phase-1, deny tests kept" && git push
Next action (Claude, after the push): check.py --fast, code-review, delete this note, PR title/body to "won't fix", Status complete, remove needs-quan, mark ready, gh pr checks 46 --watch, merge_step.py 46, close issue #44 as not planned
