# Handoff — BUG #44
Branch: bug-44-gate-tilde-comment   Base: phase-1   Last commit: 5ddd26b   PR: #46
Stop code: RED_FLAG (+ ESTIMATE: third round of gate edits)   Machine: remote
Plan: PR #46 description ("Plan as executed")
Done:
  - c869227 first gate patch (Quan approved in chat, applied by Claude with git apply)
  - 5ddd26b follow-up (Quan approved in chat): `$`/backtick/backslash anywhere in the segment -> no drop; only a bare tilde or tilde+digits dropped; 5 new deny tests
  - 29 gate tests pass; check.py --fast all PASS (862 tests, 61/61 reference)
Not done: merge. Second code-review found 2 more bypasses:
  1. PowerShell block comment: `pwsh -c "ls <# x #> <tilde>"` -> allow (`#>` read as a bash comment start)
  2. looks_like_path no longer checks a token that starts with a tilde + whitespace (quoted text). Only bash quoting makes that safe; a program that calls expanduser on it (Windows ntpath) gets a path outside the project.
Proposed fix (needs Quan's approval, gate edit):
  1. drop_comment_tildes: return the segment unchanged if it contains `<#` or `#>`; deny test for the pwsh case
  2. choose: (a, recommended) remove the tilde+whitespace exemption in looks_like_path (quoted "<tilde> approx" is denied again; rephrase as "about"), so #44 covers comments only; or (b) keep it and accept the expanduser risk
  3. nits: docstring must say bash also expands a tilde+digits (dir stack); PROGRESS.md step-log row and "Needs you" line, CHANGELOG limits (apostrophes in a comment, `<tilde>0.5`, heredoc prose still denied)
Failing tests (if any): none
Question for Quan: approve 1 + 2a + 3? (recommended: yes)
Next action: on approval, write the patch in the scratchpad, `git apply --check`, apply, deny tests, gate tests + check.py --fast, code-review again, then finish steps (delete this note, PROGRESS.md, Status complete, mark ready, merge_step.py 46)
