# Handoff — BUG #58
Branch: bug-58-spxy-groups   Base: phase-1   PR: (opened after cp1)
Stop code: —   Machine: work-pc
Decision by Quan (2026-11-27, chat): use recommendation on #58.

## Plan
- Assumptions: keep the row-level constant-y check (rounding case) and add `max_y == 0` on the unit means (as approved); group numbering stays first-appearance in the split blocks and sorted in the fold blocks (results unchanged for labelled data).
- Reuse: reuse — move folds `_groups` to one shared helper `group_codes` in `vibechem_core.blocks`; `sampling_units` renumbers its output by first appearance.
- Tools: ponytail (full), superpowers TDD, ponytail-review, silent-failure-hunter, mle-reviewer, verification-before-completion.
- Files: `blocks/__init__.py`, `blocks/split/__init__.py`, `blocks/split/spxy.py`, `blocks/validate/folds.py`, split tests, DATA_MODEL.md §7 row, RISKS.md, PROGRESS.md, CHANGELOG.md.
- cp1: failing regression tests (`pytest packages/core/tests/blocks/split` shows 4 failures).
- cp2: fix + docs (`check.py --fast` all PASS).
