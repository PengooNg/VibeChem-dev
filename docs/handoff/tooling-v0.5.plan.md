# /plan: VibeChem tooling v0.5 (caveman, ponytail and ECC take over; K removed from the workflow)

> Paste this into a fresh Claude Code session in plan mode. The planner first reads the files under "Read first". All decisions are made (below), so it asks Quan nothing up front: it proposes the edits and waits for approval. This is a workflow and tooling change, **not** a TASKS.md step.
> v3 · 2026-11-26. Quan decided three things: **(1) caveman, ponytail and ECC override every earlier rule, skill and plugin wherever they conflict. (2) K has no role in any step. He will work on his own later. (3) `# Step N:` comments stay mandatory in blocks (Quan's instruction beats ponytail).**

## Read first
- `CLAUDE.md` (all of it)
- `docs/TOOLS.md`
- `docs/QA.md`
- `docs/TASKS.md` (legend and headings)
- `docs/PROGRESS.md`
- `docs/ARCHITECTURE.md` §1, §7 and the decision log
- `docs/DATA_MODEL.md` header, §4 and §5
- `docs/TECH_STACK.md`
- `.claude/agents/step-runner.md`
- `.claude/skills/{phase,step,resume,status,bug,block-template}/SKILL.md`
- `.github/PULL_REQUEST_TEMPLATE.md` and `.github/CODEOWNERS`
- `THIRD_PARTY.md`
- `scripts/merge_step.py` and `scripts/permission_gate.py` (read only; the gate is a Quan-only file)

Sources, pinned. Clone them shallow into the scratchpad, never into the repo:
| Repo | Commit | Licence |
|---|---|---|
| JuliusBrussee/caveman | `47c61be2d10a354f0c5cbe2b90959d24c06b16c6` (v4.2.0) | Apache-2.0 (keep `LICENSE` and `NOTICE`) |
| DietrichGebert/ponytail | `ebd8654c2c627f721eb8f9c0d1bd4090a29f9e10` (v5.3.3) | MIT |
| affaan-m/ECC | `4adeee6732a12d1540f49a4d50a38ce8c97f9a53` (v2.2.3) | MIT |

## Goal
1. **caveman** (`caveman` level, replies in Quan's language): used for chat with Quan and for PR text. Never used inside files: code, comments, docstrings, commits, docs or handoff notes.
2. **ponytail** (level `full`): used whenever any code is written, including Python, C++, TS, scripts, tests and CI.
3. **ECC**: used for product management and risk assessment at the phase level (gates, stops, planning the next phase), plus three risk-review agents.
4. **New precedence:** these three win over CLAUDE.md, TOOLS.md, QA.md and every other skill or plugin wherever they conflict. Where nothing conflicts, the existing rules still apply unchanged.
5. **Remove K** from every step, review, backlog, tag and approval. Quan is the only human reviewer.
6. Drop tools that do the same job.

## Decisions (all final)
- **D1 — copy, no plugins.** Skill and agent files are copied into `.claude/`. No plugin installs, so no caveman/ponytail/ECC hooks and no ponytail band. "Override" is a precedence rule in CLAUDE.md, not hooks.
- **D2 — caveman for PR text.** Narrative sections of PR descriptions and comments to Quan; exact formats stay exact.
- **D3 — gstack dropped** from the VibeChem workflow.
- **D4 — `debug` and `deploy-checklist` dropped.**
- **D5 — K backlog → `docs/RISKS.md`.** The 21 open rows are folded into "unreviewed infrastructure" rows, one per area (CI, engine, packaging, C++, dependencies, ADRs). The Phase 1 gate triages them with cpp-reviewer, silent-failure-hunter and ponytail-audit.
- **D6 — keep `# Step N:` comments.** Blocks keep numbered `# Step N:` comments matching METHODS.md. This is Quan's direct instruction, so it beats ponytail's comment rule.

## New precedence (write into CLAUDE.md as a top-level section, before Part A)
1. **Fixed mechanics.** Text cannot change these, so they stay as they are:
   - `permission_gate.py` and the deny list in `.claude/settings.json` (Quan-only files).
   - `merge_step.py` checks: base is `phase-*`, the PR is not a draft, CI is green, the step is not 👤, and the title starts with `[T`, `[BUG` or `[SYNC]`.
   - Branch protection.
   - Checkpoint commit prefix `T<x> cpN:`, because `/resume` rebuilds lost handoff notes from it.
2. **Quan's own decisions in this plan (D1–D6).** These beat the upstream text of the three skills.
3. **caveman, ponytail, ECC.** On any conflict with item 4, these win.
4. Everything else: CLAUDE.md, TOOLS.md, QA.md, METHODS/DATA_MODEL/UI_GUIDE, superpowers, Impeccable, the design skills, Humanizer and the rest.

### How the known conflicts resolve now (write these out explicitly)
| Conflict | Old rule | Now |
|---|---|---|
| Code comments | block-template requires `# Step N:` comments that match METHODS.md, plus line comments for review | **Blocks (D6):** header docstring + numbered `# Step N:` comments matching METHODS.md stay mandatory. Beyond those, ponytail applies: no other line comments except a one-line "why". **Non-block code:** ponytail only (one-line "why"). `shortcut: <limit>, <when to upgrade>` comments are allowed everywhere. |
| Test amount | QA.md §7 / CLAUDE.md §6.1: tests for every changed function, plus reference and property tests for algorithms | **ponytail:** non-trivial logic gets one small test; trivial changes get none. For an algorithm block, that one test is a **reference test against an independent value** (a block without one is unfinished). Property tests and extra unit tests become optional. superpowers TDD applies only to non-trivial logic. The golden and leakage suites stay as they are, because they are existing tests and ponytail never deletes them. |
| Reuse order (§12) | Our repo → stack libraries → new packages → port → build; a full estimate table for every plan | **ponytail ladder:** does it need to exist → already in this codebase → stdlib/platform → installed dependency → one line → the minimum code. A new dependency only when our minimum code would be large, never "for a few lines". The §12.4 estimate table only for M/L steps. The `REUSE` stop for M+ stays; ECC `council` prepares the recommended answer. Licence rules (§12.2) are unchanged, because ponytail has none. |
| Part A (Karpathy) A2 and A3 | Own text | **Replace with one line each: "apply the `ponytail` skill (full)".** A1 (ask when unclear) and A4 (checkable goals) stay; they don't conflict. |
| Diff review | code-review plugin is the gate, gstack `/review` gives a second opinion | **ponytail-review is the gate.** The code-review plugin and gstack `/review` are dropped. `/security-review` stays on 🔒 steps. ECC agents are added per area (see the step map). |
| Bug fixing | CLAUDE.md §7 order + `debug` skill + superpowers | §7 order stays, **plus ponytail's bug rule:** grep every caller of the touched function and fix the root cause once in the shared code. |
| PR text | Plain prose (caveman's own rule 5 also says plain) | **caveman voice in the narrative sections** (Quan's instruction beats the upstream rule). Template headings, the Status line, the health summary, code, paths and commands stay exact. Questions to Quan go in full sentences (caveman rule 7). |
| Talking to Quan | CLAUDE.md report formats, superpowers announcing skills | **caveman.** Fixed formats are payload and stay verbatim: `▶`/`✓` lines, DONE/STOP blocks, "Stopping safely: <reason>." No skill-use announcements. |
| Planning and stops | Phase runner prints the stop as it is | ECC `council` drafts the "recommended answer" (≤5 lines) for `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG` stops. ECC `intent-driven-development` rewrites a vague "Done when" into AC lines. `product-capability` details the next phase from PRD F-xx, using PRD.md as the product-context file it updates. |
| Risk | Spread across PROGRESS.md notes | ECC `council`, `production-audit` and `loop-design-check`, plus `ponytail-audit` and `ponytail-debt`, all feed **`docs/RISKS.md`**, updated at gates and on `S1_BUG` / `RED_FLAG` stops. |
Override means precedence, not "install everything". The excluded parts of the three repos stay excluded (list below).

## Tool set after v0.5
**Kept:** Context7, Playwright CLI and Test, Impeccable, ui-ux-pro-max, Emil's 4 skills, accessibility-review, ux-copy, Humanizer, documentation, testing-strategy, architecture, superpowers (TDD only for non-trivial logic, `systematic-debugging`, `verification-before-completion`), block-template (comment rules updated), our own commands, step-runner, the permission gate, `/security-review`.

**Added:**
- **caveman:** `caveman`.
- **ponytail:** `ponytail`, `ponytail-review`, `ponytail-audit`, `ponytail-debt`.
- **ECC skills:** `product-capability`, `intent-driven-development`, `council`, `production-audit`, `loop-design-check`.
- **ECC agents:** `silent-failure-hunter`, `cpp-reviewer`, `mle-reviewer`.

**Dropped:** gstack, the code-review plugin, the vendored `debug` and `deploy-checklist` skills.

**Excluded from the three repos:**
| Excluded | Reason |
|---|---|
| caveman `ultracave`/`megacave`, CLI/proxy/Auto/Browse/Blocks, `caveman-compress` | Telemetry, model routing; compress rewrites CLAUDE.md |
| `caveman-commit`, `caveman-review` | Would break the `T<x> cpN:` commit prefix (fixed mechanics); ponytail-review already does the review |
| caveman's `lean-build`, `surgical-patch`, `safe-refactor`, `investigate-first`, `verify-and-stop` | Duplicate ponytail |
| ECC `planner` agent | Auto-activates on planning and would take over the step plan |
| ECC `blueprint`, `orch-*`, `plan-orchestrate`, `ralphinho-rfc-pipeline`, `devfleet` | Competing pipelines to `/phase` |
| ECC `tdd-workflow`, `*-testing`, `*-verification`, `test-collaboration` | Duplicate superpowers and QA.md |
| ECC `code-reviewer` and language reviewers, `pr-test-analyzer` | Duplicate ponytail-review |
| ECC `security-review`, `security-bounty-hunter`, `safety-guard` | Duplicate `/security-review` and the gate |
| ECC `architecture-decision-records` | Would create `docs/adr/`; ADRs live in ARCHITECTURE.md §7 |
| ECC `product-lens`, `context-and-decisions` | Would create PRODUCT-BRIEF.md and CONTEXT.md |
| ECC `council-multi-model`, `deep-research` | External services |
| ECC `strategic-compact`, `context-budget` | CLAUDE.md §8.2 covers this |
| ECC `rules/`, hooks, GitHub App | Duplicate CLAUDE.md; hooks stack on the gate |

**Optional one-off:** after the merge, Quan runs `! npx ecc-agentshield scan .`.

## K removal (every file, on the phase-1 branch)
Reviewer is **Quan** everywhere. The C++, infra and packaging review that K would have done is now covered by the ECC agents and the phase-gate audits.
| File | Change |
|---|---|
| `CLAUDE.md` | §1: "owner and only reviewer: Quan"; drop the K sentence. §2: the PROGRESS row loses "K review backlog". §6.9–6.10: drop the K backlog row and the `k-review` label. §10: everything → Quan, with the agent lenses listed. §12.5: drop "add a K review backlog row". §14.4: no K. **§15 deleted.** Phase 3 rules from §15 (Python reference, equivalence tests, sanitizer-clean CI, fallback) move to TECH_STACK.md §5, where they already partly live. |
| `docs/TASKS.md` | Remove the `· K ·` / `· Q ·` area tags from every `### T… ·` heading and from the legend. Run-order row 7: "Beta = demo v0". Remove any K-only wording in step bodies. (`merge_step.py` only parses the step id and 👤, so this is safe; check that `test_merge_step.py` still passes. Its fixture headings may keep `· K ·` or be updated, either is fine.) |
| `docs/PROGRESS.md` | Delete the "K review backlog" section (rows → RISKS.md per D5). Delete gate notes that say "for K at demo v0". The Step log stays as history. |
| `docs/QA.md` | Owners → Quan. L4/L5 → Quan. §7: drop the K row. §8 "K — infrastructure review" → **"Infrastructure checklist"** (Quan at gates, with cpp-reviewer/silent-failure-hunter). §9 adds "RISKS.md updated". Visual-check row: drop gstack. |
| `docs/ARCHITECTURE.md` | Deciders → Quan. §1 team line → Quan + AI. ADR statuses `Accepted (provisional — K to confirm)` → `Accepted` (Quan already accepted them at the Phase 0 gate). ADR-010 note: drop "K to confirm". ADR-002 context/options: drop the K rationale; keep the decision. Decision log: add an entry "K removed from workflow; reviews = Quan + agents" (do not rewrite old entries). "Pending sign-off by Quan and K" → Quan. |
| `docs/DATA_MODEL.md` | Reviewers → Quan. "with K's approval" → "with Quan's approval". §4 and §5 headers: drop "K confirms at demo v0". |
| `docs/TECH_STACK.md` | Owner → Quan. §1 Eigen note: "Eigen 5.x may be evaluated". §8 dependency approval → Quan. Leave the CITATION `add K … once authorship is agreed` comment alone; authorship is not a workflow role (flag this to Quan). |
| `docs/PRD.md`, `docs/FUNCTION_CATALOG.md` | Rephrase the K mentions ("reviewed by Quan"). |
| `.github/CODEOWNERS` | Comment: "Everything → Quan." |
| `.github/PULL_REQUEST_TEMPLATE.md` | Drop the K backlog checkbox; header note on caveman voice (D2); review section = ponytail-review / security / visual check / agents. |
| `.claude/agents/step-runner.md` | DONE block: drop `K backlog row:`, add `Risks added: <none\|RISKS ids>`. |
| `.claude/skills/block-template/SKILL.md` and the 5 merged blocks (`snv`, `msc`, `detrend`, `savgol`, `cut`) | `Reviewers: algorithm -> Quan \| structure -> K` → `Reviewer: Quan`. `# Step N:` comments stay (D6). The template drops only the "extra line comments for K" guidance. |
| Leave untouched | `.claude/skills/impeccable/reference/onboard.md` (vendored upstream; its "K" is unrelated). |
Quan-only follow-ups for the PR description: delete the GitHub `k-review` label (the gate denies label edits); later, the Project's `me/PROJECT.md`, `me/OWNER_MANUAL.md` and `setup/SETUP.md` (outside the repo).

## Changes, by checkpoint
Branch `tooling-v0.5` from `phase-1`, PR base `phase-1`, title `[TOOLING] v0.5 caveman, ponytail, ECC; remove K`. `merge_step.py` refuses this title, so **Quan merges**. Start only when no step PR is `in-progress` (`t1-08-savgol` exists).

**cp1: copy the files in.** Copy verbatim plus LICENSE/NOTICE; only frontmatter may change (D1).
- `.claude/skills/caveman/SKILL.md` ← `caveman/skills/caveman/SKILL.md`
- `.claude/skills/{ponytail,ponytail-review,ponytail-audit,ponytail-debt}/` ← `ponytail/skills/…`
- `.claude/skills/{product-capability,intent-driven-development,council,production-audit,loop-design-check}/` ← `ECC/skills/…`. Copy `templates/` or `references/` only if the SKILL.md links them.
- `.claude/agents/{silent-failure-hunter,cpp-reviewer,mle-reviewer}.md` ← `ECC/agents/…`. Keep their read-only `tools:` lists; set `model: inherit`.
- Gate-only skills get `disable-model-invocation: true`, so their descriptions don't load every session. The runners use them by **Read**ing the path listed in TOOLS.md. These are council, product-capability, intent-driven-development, production-audit, loop-design-check, ponytail-audit and ponytail-debt. caveman, ponytail and ponytail-review stay model-invocable.
- `git rm -r .claude/skills/debug .claude/skills/deploy-checklist`.
- `THIRD_PARTY.md`: one row per copied item (repo, commit, licence, "frontmatter modified" where true), plus the caveman NOTICE text. Remove the rows for the dropped skills.

**cp2: rules.**
- `CLAUDE.md` → v1.0. Add the precedence section and the conflict table above. Replace A2 and A3 with the ponytail line. Add a "Voice" section: the main session and phase runner load `caveman` at session start; the step-runner does not; nobody uses it inside files.
- Update §5, §6.6 (review = ponytail-review + per-area agents + `/security-review` on 🔒 + the visual check on 👁), §7, §12 and §13 (remove the gstack, code-review and `debug` mentions; add caveman, ponytail and ECC), and §14.4 (gate: council go/no-go note, ponytail-audit, ponytail-debt, mle-reviewer, production-audit from Phase 5, product-capability + intent-driven-development to detail the next phase, RISKS.md update).
- `docs/TOOLS.md` → v0.5. §1 sources. §2 rules. "Not used" gets reasons. §3 step map:
  - every code step: ponytail + ponytail-review
  - core/engine/native: + silent-failure-hunter
  - `packages/native` / Phase 3: + cpp-reviewer
  - T2.05 and gates: + mle-reviewer
  - 🔒: + `/security-review`
  - 👁: the visual check
  - replace every gstack and code-review entry
- `docs/QA.md`: the test-amount rule from the conflict table; the reviewer list matches CLAUDE.md §6.6.

**cp3: runners and templates.**
- step-runner: load `ponytail` before the first checkpoint. Run the agents per the TOOLS.md §3 row. No caveman. ponytail's "skipped / risk" lines go into the PR "Assumptions" section.
- `{phase,step,resume,status,bug}`: talk to Quan in caveman voice and keep fixed formats verbatim. `/bug` loads ponytail. `phase`: on a REUSE / ESTIMATE / QUESTION / RED_FLAG stop, Read `council` and draft the recommended answer.
- `block-template`: keeps `# Step N:` (D6); other comments follow ponytail; `Reviewer: Quan`.
- PR template: as in the K table.
- New `docs/RISKS.md`: `ID | Risk | Area | Likelihood | Impact | Mitigation | Trigger/evidence | Status | Last reviewed`. Seed it from the K backlog (D5), open PROGRESS stops, ADR consequences and `docs/spikes/*.md`.

**cp4: K removal.** Work through the K table file by file.

**cp5: one-off risk run** (report only).
- Read `loop-design-check` and audit `/phase` + step-runner + `check.py` for spinning, gaming the verifier and runaway loops.
- Findings go into a PR comment and RISKS.md rows.
- Any gate or settings change goes into a patch in the scratchpad for Quan, because those files are deny-edit.

## Verification
- `uv run python scripts/check.py --fast` all PASS.
- `uv run pytest scripts/tests/test_permission_gate.py scripts/tests/test_merge_step.py` PASS. No new skill name collides with `FORBIDDEN_SKILLS`.
- `grep -rnE "\bK\b|k-review|K backlog|K to confirm" --include=*.md --include=*.py --include=CODEOWNERS . | grep -v impeccable/reference` returns nothing except the CITATION authorship comment and history in old decision-log rows.
- No `gstack`, `code-review`, `/debug` or `deploy-checklist` references remain. Every skill and agent named in CLAUDE.md and TOOLS.md exists in `.claude/` or is a built-in.
- Copied frontmatter parses as YAML; THIRD_PARTY.md rows have commit hashes.
- Smoke test (Quan, new session):
  - "where are we?" → a short caveman reply.
  - `/step <next-ID> wait` → the plan lists ponytail, ponytail-review and the right agents, and the reuse section follows the ponytail ladder.
- No `.claude/settings.json` change is needed. If one turns out to be needed, write a patch for Quan.

## Out of scope
- Changing algorithms, TASKS.md scope, or UI_GUIDE.md.
- Rewriting merged code beyond the `Reviewer:` docstring line.
- The gate and settings files (Quan only).
- Installing the three as plugins (D1).
- Caveman CLI/Cloud, ponytail band/board/webhook, ECC GitHub App/Pro.

## Stop and ask Quan if
- A copied skill needs files beyond its folder (scripts, hooks, MCP).
- A new-precedence rule would break one of the fixed mechanics.
- A conflict appears that the table does not settle.
- Removing K changes an ADR **decision**, not just who signs it.
- The gate denies a needed action.
