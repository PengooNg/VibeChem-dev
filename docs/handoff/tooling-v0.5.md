# Handoff — TOOLING v0.5
Branch: tooling-v0.5   Base: phase-1   Last commit: see PR   PR: (draft, see `gh pr list --head tooling-v0.5`)
Stop code: —   Machine: remote
Plan: docs/handoff/tooling-v0.5.plan.md (Quan's plan v3, decisions D1–D6 final) + session plan (pins = hashes as written; Dependabot folded into phase-1 in PR #47; #45 patch after this PR)
Done: cp1 copy (skills + agents at pinned hashes, frontmatter only, debug/deploy-checklist removed, THIRD_PARTY.md)
Not done: cp2 rules (CLAUDE.md v1.0, TOOLS.md v0.5, QA.md), cp3 runners/templates + docs/RISKS.md, cp4 K removal, cp5 loop-design-check risk run, ponytail-review of the diff, finish (Quan merges; title [TOOLING] is refused by merge_step.py)
Failing tests (if any): none
Decisions made:
  - upstream clones: scratchpad/upstream/{caveman,ponytail,ECC} at the pinned hashes (re-clone with `git fetch --depth 1 <url> <hash>` if the scratchpad is gone)
  - caveman line 19 names ultracave/megacave (not vendored): TOOLS.md says `/caveman ultra|wenyan` are unavailable
  - product-capability template not vendored: PRD.md is the product-context file (plan conflict table)
  - mle-reviewer `e2e-runner`, loop-design-check `autonomous-loops`, council `search-first` are see-also links to skills not vendored
Question for Quan (if any): —
Files read that matter: the 13 copied files; THIRD_PARTY.md; scripts/permission_gate.py FORBIDDEN_SKILLS (no collision)
Next action: cp2 — read CLAUDE.md, docs/TOOLS.md, docs/QA.md; write the precedence section + conflict table, A2/A3 → ponytail line, Voice section, §5/§6.6/§7/§12/§13/§14.4; TOOLS.md v0.5; QA.md test-amount rule
