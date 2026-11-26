# Handoff — TOOLING v0.5
Branch: tooling-v0.5   Base: phase-1   Last commit: see PR   PR: (draft, see `gh pr list --head tooling-v0.5`)
Stop code: —   Machine: remote
Plan: docs/handoff/tooling-v0.5.plan.md (Quan's plan v3, decisions D1–D6 final) + session plan (pins = hashes as written; Dependabot folded into phase-1 in PR #47; #45 patch after this PR)
Done: cp1 copy (skills + agents at pinned hashes, frontmatter only, debug/deploy-checklist removed, THIRD_PARTY.md); cp2 rules (CLAUDE.md v1.0 incl. its K removal and §15 deleted, TOOLS.md v0.5, QA.md v0.4 incl. its K removal)
Not done: cp3 runners/templates + docs/RISKS.md (CLAUDE.md and TOOLS.md already point to docs/RISKS.md — create it in cp3), move the §15 Phase 3 rules into TECH_STACK.md §5 (cp4), cp4 K removal, cp5 loop-design-check risk run, ponytail-review of the diff, finish (Quan merges; title [TOOLING] is refused by merge_step.py)
Failing tests (if any): none
Decisions made:
  - upstream clones: scratchpad/upstream/{caveman,ponytail,ECC} at the pinned hashes (re-clone with `git fetch --depth 1 <url> <hash>` if the scratchpad is gone)
  - caveman line 19 names ultracave/megacave (not vendored): TOOLS.md says `/caveman ultra|wenyan` are unavailable
  - product-capability template not vendored: PRD.md is the product-context file (plan conflict table)
  - mle-reviewer `e2e-runner`, loop-design-check `autonomous-loops`, council `search-first` are see-also links to skills not vendored
Question for Quan (if any): —
Files read that matter: the 13 copied files; THIRD_PARTY.md; scripts/permission_gate.py FORBIDDEN_SKILLS (no collision)
Next action: cp3 — step-runner (load ponytail, agents per TOOLS.md §3, DONE block `Risks added:`), skills {phase,step,resume,status,bug} (caveman voice, fixed formats verbatim, /bug loads ponytail, phase reads council on stops), block-template (D6, Reviewer: Quan), PR template, new docs/RISKS.md seeded from the PROGRESS.md K backlog (one row per area), open stops, ADR consequences, docs/spikes/*.md
