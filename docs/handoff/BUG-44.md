# Handoff — BUG #44
Branch: bug-44-gate-tilde-comment   Base: phase-1   Last commit: c869227 (gate patch applied)   PR: #46
Stop code: RED_FLAG   Machine: remote
Plan: PR #46 description ("Plan as executed")
Done: regression tests; gate patch applied with Quan's approval (c869227); 29 gate tests pass; check.py --fast all PASS (862 tests, 61/61 reference)
Not done: merge. code-review found 3 bypasses the patch opens (confirmed: all return allow):
  1. escaped space before the hash: `ls x\ # <tilde>` (bash: no comment, so the tilde expands to home)
  2. hash inside a parameter expansion: `ls ${a:- # } <tilde>-` (the `$` before the hash is not guarded)
  3. drop pattern `<tilde>[^/]*` also drops `<tilde>root`, `<tilde>+`, `<tilde>-`, which bash expands
Proposed fix (needs Quan's approval, gate edit):
  - in drop_comment_tildes, return the segment unchanged if a backslash, `$` or backtick appears anywhere in it (not only after the hash)
  - narrow the dropped words to a bare tilde or a tilde followed by digits only
  - add deny tests for the three cases above
Also noticed (separate issue, deny side, safe): a multi-line double-quoted string with a bare tilde is still denied, because SEGMENT_SPLIT cuts the quote open and shlex falls back to whitespace splitting.
Failing tests (if any): none
Question for Quan: approve the proposed fix above as a follow-up gate edit on this branch? (recommended: yes)
Next action: on approval, write the fix + 3 deny tests, run gate tests + check.py --fast, re-run code-review, then the finish steps (delete this note, PROGRESS.md "Needs you" line, Status complete, mark ready, merge_step.py 46)
