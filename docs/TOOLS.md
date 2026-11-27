# VibeChem — Claude Code skills, plugins and tools

> v0.5 · 2026-11-26 · Read by Claude Code when planning a step (docs/rules/WORKFLOW.md#how-a-step-runs, docs/TOOLS.md#5-rules-for-the-tools). Humans install these once per machine (Quan's setup guide).
> v0.3: Playwright **CLI** replaces the Playwright MCP server; GitHub MCP removed (`gh` only); design set = Impeccable + ui-ux-pro-max + four of Emil Kowalski's skills; Humanizer for prose; visual check on UI steps.
> v0.4: superpowers (plugin) added; Impeccable and the knowledge-work skills are **vendored skills** instead of plugins; permission gate (docs/TOOLS.md#52-permission-gate).
> v0.5: **caveman, ponytail and ECC** vendored (copied, not installed as plugins: no hooks, no band) and given precedence over the project rules where they conflict (docs/rules/PRECEDENCE.md); **gstack, the code-review plugin, `debug` and `deploy-checklist` dropped**; ponytail-review is the review gate; K removed (Quan is the only human reviewer).
> All of these are **development tools only**. They never become app/engine dependencies (CLAUDE.md#hard-rules).

## 1. Where each tool comes from
| Tool | Kind | Comes from | Licence | Installed by |
|---|---|---|---|---|
| `/phase`, `/step`, `/resume`, `/status`, `/bug` | project skills (commands) | `.claude/skills/<name>/SKILL.md` | ours | repo (committed) |
| step-runner | subagent | `.claude/agents/step-runner.md` | ours | repo (committed) |
| caveman | skill (model-invocable) | vendored from `JuliusBrussee/caveman` `skills/caveman/` at a pinned commit (THIRD_PARTY.md) | Apache-2.0 | repo (committed) |
| ponytail, ponytail-review | skills (model-invocable) | vendored from `DietrichGebert/ponytail` `skills/<name>/` at a pinned commit | MIT | repo (committed) |
| ponytail-audit, ponytail-debt | skills (gate-only: `disable-model-invocation: true`; runners **Read** the file) | same | MIT | repo (committed) |
| council, product-capability, intent-driven-development, production-audit, loop-design-check | skills (gate-only, read by path) | vendored from `affaan-m/ECC` `skills/<name>/` at a pinned commit | MIT | repo (committed) |
| silent-failure-hunter, cpp-reviewer, mle-reviewer | subagents (read-only tools, `model: inherit`) | vendored from `affaan-m/ECC` `agents/` | MIT | repo (committed) |
| Context7 | MCP | `.mcp.json` | — | repo (approve once per machine) |
| Playwright CLI | npm dev tool + skill | `@playwright/cli` in `app/` devDependencies; skill from `playwright-cli install --skills`, committed under `.claude/skills/` (T0.04) | Apache-2.0 | repo; browser via `npx playwright install chromium` per machine |
| Playwright Test | npm dev dependency | `@playwright/test` in `app/` (e2e tests) | Apache-2.0 | repo |
| ui-ux-pro-max | skill | `.claude/skills/ui-ux-pro-max/` (nextlevelbuilder/ui-ux-pro-max-skill) | MIT | repo (committed) |
| break-ui, prototype, review-animations, animation-performance | skills | vendored from `emilkowalski/skills` at a pinned commit (THIRD_PARTY.md) | MIT | repo (committed) |
| Impeccable | skill | vendored from `pbakaus/impeccable` (`plugin/skills/impeccable/`) at a pinned commit. The plugin is **not** installed: it registers SessionStart/PostToolUse/Stop hooks | Apache-2.0 | repo (committed); telemetry off via `.impeccable/config.json` and `DO_NOT_TRACK=1` in `.claude/settings.json` |
| Humanizer | plugin | `blader/humanizer` marketplace (Claude Code ≥ 2.1.142) | MIT | each machine |
| testing-strategy, architecture, documentation | skills | vendored from `anthropics/knowledge-work-plugins` `engineering/skills/` (THIRD_PARTY.md). The plugin is not installed: it adds remote MCP servers | Apache-2.0 | repo (committed) |
| accessibility-review, ux-copy | skills | vendored from `anthropics/knowledge-work-plugins` `design/skills/` (same reason) | Apache-2.0 | repo (committed) |
| superpowers | plugin | `superpowers@claude-plugins-official` (obra/superpowers) | MIT | repo: `enabledPlugins` in `.claude/settings.json` (project scope); its SessionStart bootstrap hook is accepted |
| Permission gate | hook | `scripts/permission_gate.py`, registered in `.claude/settings.json` (docs/TOOLS.md#52-permission-gate) | ours | repo (committed) |
| `/security-review` | built-in command | Claude Code | — | — |

**Not used** (and why):
| Tool | Why not |
|---|---|
| gstack (all of it) | Dropped in v0.5 (D3): its review helpers duplicate ponytail-review and ECC; the rest ships, deploys or leaves the project. The gate still denies its dangerous commands (`FORBIDDEN_SKILLS`) |
| code-review plugin, `/review` | Dropped in v0.5: ponytail-review is the review gate |
| `debug`, `deploy-checklist` skills | Dropped in v0.5 (D4): docs/QA.md#6-bug-protocol + ponytail's bug rule + superpowers `systematic-debugging` cover debugging; QA.md §9 holds the release checklist |
| caveman `ultracave`, `megacave` (so `/caveman ultra` and `/caveman wenyan` do nothing here), CLI/proxy/Auto/Browse/Blocks, `caveman-compress` | Telemetry and model routing; compress rewrites CLAUDE.md |
| `caveman-commit`, `caveman-review` | Would break the `T<x> cpN:` commit prefix (fixed mechanics); ponytail-review already reviews |
| caveman `lean-build`, `surgical-patch`, `safe-refactor`, `investigate-first`, `verify-and-stop` | Duplicate ponytail |
| ponytail `ponytail-gain`, `ponytail-help`, hooks, band, board, webhook | Display/marketing helpers and hooks (D1: no hooks) |
| ECC `planner` agent | Auto-activates on planning and would take over the step plan |
| ECC `blueprint`, `orch-*`, `plan-orchestrate`, `ralphinho-rfc-pipeline`, `devfleet` | Competing pipelines to `/phase` |
| ECC `tdd-workflow`, `*-testing`, `*-verification`, `test-collaboration` | Duplicate superpowers and QA.md |
| ECC `code-reviewer`, language reviewers, `pr-test-analyzer` | Duplicate ponytail-review |
| ECC `security-review`, `security-bounty-hunter`, `safety-guard` | Duplicate `/security-review` and the gate |
| ECC `architecture-decision-records` | Would create `docs/adr/`; ADRs live in ARCHITECTURE.md §7 |
| ECC `product-lens`, `context-and-decisions` | Would create PRODUCT-BRIEF.md and CONTEXT.md |
| ECC `council-multi-model`, `deep-research` | External services |
| ECC `strategic-compact`, `context-budget` | docs/rules/WORKFLOW.md#stop-safely-never-mid-section covers this |
| ECC `rules/`, hooks, GitHub App; `product-capability`'s `docs/examples/` template | Duplicate CLAUDE.md; hooks stack on the gate; PRD.md is the product-context file |
| Skills and agents the vendored files only mention: `autonomous-loops`, `continuous-agent-loop`, `search-first`, `e2e-runner`, `code-reviewer`, `santa-method` | "See also" links and routing hints in council / loop-design-check / mle-reviewer; not vendored, ignore them (code review = ponytail-review) |
| Playwright MCP, GitHub MCP | Token cost; `playwright-cli` and `gh` cover them |
| Impeccable plugin, knowledge-work plugins | Hooks / remote MCP servers; their skills are vendored instead |
| frontend-design, Taste Skill | Impeccable is built on frontend-design; Taste Skill is a later candidate for the docs site (T7.02) |
| Headroom | Optional owner-side trial outside the repo; Claude Code never runs it |

Optional one-off (Quan): `! npx ecc-agentshield scan .` after the v0.5 merge.

## 2. What each tool is for
| Tool | Use it when | Rules |
|---|---|---|
| **caveman** | The main session and the phase runner load it at session start: every reply to Quan and the narrative sections of PR descriptions and PR comments | Never inside files (code, comments, docstrings, commits, docs, handoff notes). Fixed formats stay verbatim: `▶`/`✓` lines, DONE/STOP blocks, "Stopping safely: <reason>.", Status lines, health summaries, template headings, code, paths, commands. Questions to Quan in full sentences. The step-runner does **not** load it |
| **ponytail** (level `full`) | Whenever code is written: Python, C++, TypeScript, scripts, tests, CI | Wins over docs/rules/CODING.md (how to work, reuse) where they conflict (docs/rules/PRECEDENCE.md). Blocks keep header docstring + `# Step N:` comments (D6). Licence rules (docs/rules/CODING.md#reuse-first-and-estimate-before-committing, 12.2) still apply. Its "skipped / risk" closing lines go into the PR *Assumptions* section |
| **ponytail-review** | Every code step and bug fix before ready; on request | The review gate (replaces code-review). Branch diff plus the code it touches. Fix *Must fix* and in-scope *Should fix*; list the rest in the PR |
| **silent-failure-hunter** (agent) | Steps touching `packages/core`, `packages/engine`, `packages/native`, `scripts/` | Read-only report; findings handled like ponytail-review findings |
| **cpp-reviewer** (agent) | `packages/native` changes and every Phase 3 step | Read-only; C++ rules in TECH_STACK.md §5 win on conflicts with its generic advice |
| **mle-reviewer** (agent) | T2.05 (leakage suite) and every phase gate | Read-only; leakage findings are `S1_BUG` stops |
| **council** (read `.claude/skills/council/SKILL.md`) | The phase runner drafts the "recommended answer" (≤ 5 lines) for `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG` stops; go/no-go note at gates | Draft only; Quan decides. No notes outside the repo |
| **intent-driven-development** (read by path) | A step's "Done when" is too vague to check | Rewrites it into AC lines in the plan; a changed scope is still a `QUESTION` stop |
| **product-capability** (read by path) | Phase gate: detailing the next phase from PRD F-xx | PRD.md is its product-context file; output goes into TASKS.md step bodies |
| **production-audit** (read by path) | Phase gates from Phase 5 on (installers, update check, release) | Local evidence only; no external scanners |
| **loop-design-check** (read by path) | Auditing `/phase`, step-runner and `check.py` for spinning, verifier gaming and runaway loops (tooling v0.5 cp5; again when those files change) | Findings → `docs/RISKS.md` |
| **ponytail-audit, ponytail-debt** (read by path) | Every phase gate: whole-repo audit and the `shortcut:` debt ledger | Report only; findings → `docs/RISKS.md` and next-phase steps |
| **Context7** | Before writing or debugging code that calls a library API: FastAPI, pydantic, scikit-learn, SciPy, pyarrow, loky, nanobind, scikit-build-core, cibuildwheel, React, React Flow, uPlot, Tailwind, i18next, Electron, electron-builder, Vitest, Playwright… | Query the **version pinned in TECH_STACK.md §1**, not "latest". Note library + version in the plan's *Tools* line. Not a source for algorithm definitions (METHODS.md is) |
| **/security-review** | Steps marked 🔒 in §3 (auth, file parsing, file formats, IPC, installers, update check) | Run on the branch diff before ready; paste findings and how each was handled into the PR. An unresolved high finding is a stop (`RED_FLAG`) |
| **Playwright CLI** | Visual check on every `app/` step (§5.1: screenshots; the full set only on 👁 steps); reproducing UI bugs; contact sheets | Local dev app and localhost only. Screenshots go to `.playwright-cli/` (git-ignored) and are attached to the PR, never committed |
| **Playwright Test** | e2e tests in `app/e2e/`; nightly on 3 OS | Tests are code: they follow QA.md and run in CI |
| **Impeccable** | Steering and reviewing UI: `typeset`, `layout`, `quieter`, `distill`, `colorize`, `clarify`; review `critique`, `audit`; finish `polish`, `harden`, `adapt` | **UI_GUIDE.md wins.** Never `live`, never `init`/`document`/`extract`, no hook, no catalog-fetching "new design" flows, telemetry off. `bolder`, `delight`, `overdrive`, `animate` only when a step asks for it |
| **ui-ux-pro-max** | Gaps in UI_GUIDE.md (states, spacing, chart choice) and as a checklist | Same precedence; its demo code is never copied |
| **break-ui** | 👁 steps (§5.1): worst-case data (2,000 spectra, empty dataset, 60-character JA/VI labels, 1 sample per group, missing values) | Findings in scope fixed; others listed |
| **prototype** | When a step or Quan asks for alternatives | Options for Quan; the chosen one goes into UI_GUIDE.md via the step's PR |
| **review-animations, animation-performance** | Steps that add or change motion | Respect `prefers-reduced-motion`; motion only where UI_GUIDE.md allows |
| **accessibility-review** | Before ready on 👁 steps; once per phase gate over every changed screen (§5.1) | WCAG 2.1 AA, as UI_GUIDE.md states |
| **ux-copy** | Labels, tooltips, error messages, empty states, first-launch text | EN source text into i18n files only; error text must match DATA_MODEL.md §7 codes |
| **Humanizer** | Human-facing prose: README, docs site, first-launch guide, EN tooltip/help text, release notes, CHANGELOG, paper drafts | Never on METHODS.md formulas, error messages tied to codes, CLAUDE.md, TASKS.md, PR status lines or code. Meaning must not change |
| **testing-strategy** | Planning QA tooling, leakage suite, golden tests, e2e tests | Output becomes the plan's checkpoints; QA.md levels and tolerances win |
| **architecture** | Spikes, port-type design, phase gates, any new pattern | ADRs in ARCHITECTURE.md §7 format; Quan accepts at the gate |
| **superpowers** | `test-driven-development` for **non-trivial logic only** (ponytail test rule); `systematic-debugging` with docs/QA.md#6-bug-protocol; `verification-before-completion` before DONE, "ready" or "fixed"; `writing-plans`/`executing-plans` only as help for the §3 plan, which lives in `docs/handoff/<step>.md` | Never `brainstorming` in phase mode (stop with `QUESTION`); `using-git-worktrees` only under `.claude/worktrees/`; never `finishing-a-development-branch` (merge = `merge_step.py`). No skill-use announcements to Quan (caveman) |
| **documentation** | READMEs, docs site, first-launch guide text | Facts come from the docs; then Humanizer |

## 3. Step map
Every step that writes code: **ponytail + ponytail-review** + superpowers `verification-before-completion` (`test-driven-development` for non-trivial logic). Add per area: `packages/core`, `packages/engine`, `packages/native`, `scripts/` → **silent-failure-hunter**; `packages/native` / Phase 3 → **cpp-reviewer**; T2.05 and phase gates → **mle-reviewer**. 🔒 = also `/security-review`. 👁 = full visual check (§5.1: Playwright CLI screenshots of all states + Impeccable critique/audit + break-ui + accessibility-review). Other `app/` steps: screenshots + e2e test for new flows only (§5.1).

| Steps | Extra tools |
|---|---|
| Every bug fix | ponytail bug rule (grep every caller, fix the root cause once) + ponytail-review (+ Playwright CLI to reproduce UI bugs) |
| T0.01, T0.06 (CI) | Context7 (GitHub Actions, cibuildwheel) · `gh run view --log-failed` for CI logs |
| T0.02 (repo skeleton, legal, merge script) | documentation + Humanizer (README, CONTRIBUTING) |
| T0.03, T0.05 (Python workspace, native) | Context7 |
| T0.04 (app workspace) | Context7 · ui-ux-pro-max |
| T0.07 (QA tooling) | testing-strategy + Context7 |
| T0.09 (engine skeleton) 🔒 | Context7 (FastAPI) |
| T0.10 (skeleton UI) 👁 | Context7 + Impeccable + first `@playwright/test` Electron e2e test |
| T0.11 (shell + installers) 🔒 | Context7 (Electron, electron-builder, PyInstaller) |
| T0.12, T0.13 (spikes) | architecture (ADR update) + Context7 + council (go/no-go note) |
| T0.14 (port-type design) | architecture |
| Phase gates | architecture + council (go/no-go) + Impeccable `audit` + accessibility-review over the phase's changed screens + ponytail-audit + ponytail-debt + mle-reviewer (+ production-audit from Phase 5) + product-capability and intent-driven-development to detail the next phase · `docs/RISKS.md` updated |
| T1.01–T1.03 (dataset, block contract, schema) | Context7 (pydantic, scikit-learn API conventions) |
| T1.05, T1.06 (readers) 🔒 | Context7 (pyarrow, openpyxl, jcamp) |
| T1.07–T1.14 (blocks, metrics) | Context7 (scikit-learn, SciPy, chemotools) · block-template |
| T2.03 (file format) 🔒 | Context7 (pydantic, jsonschema) |
| T2.05 (leakage suite) | testing-strategy + mle-reviewer |
| T2.13 (golden) | testing-strategy |
| T2.06–T2.12 (cache, executor, runners, CLI, bench) | Context7 (loky, threadpoolctl) |
| Phase 3 (C++) | Context7 (nanobind, Eigen, cibuildwheel) + cpp-reviewer |
| T4.01, T4.02 (engine server, WebSocket) 🔒 | Context7 (FastAPI) |
| Glyph set (Phase 4, 👤) 👁 | prototype + Impeccable `critique` + Playwright CLI contact sheet |
| T4.03–T4.11 (UI) 👁 | Context7 + Impeccable + ui-ux-pro-max + break-ui + accessibility-review + ux-copy (+ review-animations where motion changes) |
| T5.01, T5.04 (shell, update check) 🔒 | Context7 (Electron) + production-audit |
| T5.03 (installers + first-launch guide) 👁 | production-audit + ux-copy + documentation + Humanizer |
| T5.05 (e2e) | testing-strategy + Playwright Test + Context7 |
| Phase 6 tooltip content | ux-copy + Humanizer |
| T7.01, T7.06 (release) | production-audit · T7.02 docs site: documentation + Humanizer · T7.04 paper: Humanizer |

## 4. If a tool is missing
Say so in the plan's *Tools* line and continue with the docs and official documentation. Don't block the step and don't guess APIs (docs/rules/CODING.md#a1-think-before-coding). A missing project command, the step-runner subagent, the ponytail/ponytail-review skills, or the Playwright CLI on a 👁 step → stop `MISSING_INPUT`.

## 5. Rules for the tools
_(moved from the old CLAUDE.md on 2026-11-27)_
The full list is in §1–§2 and the **per-step map** in §3. Read your step's row there when planning and name the tools in the plan's *Tools* line. Short version:
- **caveman** — voice for talking to Quan and for PR narrative (see CLAUDE.md#voice); never inside files.
- **ponytail** (full) — whenever code is written; **ponytail-review** before every merge (docs/QA.md#7-per-step-duties), plus the ECC agents per area (**silent-failure-hunter**, **cpp-reviewer**, **mle-reviewer**) and `/security-review` on 🔒 steps.
- **ECC skills, read by path** (gate-only, not auto-invoked): `council` (stop answers, go/no-go), `intent-driven-development` (vague "Done when"), `product-capability` (next-phase detail from PRD), `production-audit` (gates from Phase 5), `loop-design-check` (runner audits); with `ponytail-audit` and `ponytail-debt` at gates. All risk findings → `docs/RISKS.md`.
- **Context7** (MCP) — check library APIs at the pinned version before writing or debugging library calls.
- **Playwright CLI** (`playwright-cli` skill, run through Bash) — open the dev app, click through, screenshot. The project uses the CLI, not the Playwright MCP server (fewer tokens). Automated e2e tests use `@playwright/test`.
- **Design:** **Impeccable** (steer: `typeset`, `layout`, `quieter`, `distill` …; review: `critique`, `audit`; finish: `polish`, `harden`, `clarify`), **ui-ux-pro-max** (checklist), Emil's **break-ui**, **prototype**, **review-animations**, **animation-performance**, plus **accessibility-review** and **ux-copy**. **UI_GUIDE.md wins** over every design skill; conflicts become a proposed UI_GUIDE.md change (stop `DOC_CONFLICT` if it blocks the step).
  - Impeccable limits: never `live` mode, never install its hook, never `init`/`document`/`extract` (they write PRODUCT.md/DESIGN.md — UI_GUIDE.md is the only design doc), never start a "new design" flow that fetches the online catalog; telemetry stays off.
  - Glyphs and the block widget follow UI_GUIDE.md §4/§6; while UI_GUIDE.md §4 is marked *draft*, the glyph-set step is 👤 (Quan's taste decides).
- **Humanizer** — on human-facing prose before merge: README, docs site, first-launch guide, EN tooltip/help text, release notes, CHANGELOG entries, paper drafts. Never on METHODS.md formulas, error messages tied to codes, CLAUDE.md, TASKS.md, PR status lines or code comments.
- **testing-strategy, architecture, documentation** — QA, ADR and doc steps.
- **superpowers** — `test-driven-development` inside checkpoints for non-trivial logic only, `systematic-debugging` with docs/QA.md#6-bug-protocol, `verification-before-completion` before any DONE or "ready" claim. Its workflow never replaces docs/rules/WORKFLOW.md#how-a-step-runs: the plan goes in the handoff note, no `brainstorming` in phase mode (the step-runner can't ask questions; stop instead), worktrees only under `.claude/worktrees/`, never `finishing-a-development-branch` (merging is docs/rules/WORKFLOW.md#merging-a-step).
- **Not used:** gstack, the code-review plugin and `/review`, the `debug` and `deploy-checklist` skills (§1 "Not used"). The gate still denies gstack's dangerous commands.
- GitHub work uses `gh` only (no GitHub MCP).
- **Precedence:** see CLAUDE.md#precedence. Outside it, CLAUDE.md > TOOLS.md > any other plugin or skill text; a skill that says to commit, push, merge, deploy or ask questions in another way than docs/rules/WORKFLOW.md#how-a-step-runs/docs/rules/WORKFLOW.md#phase-mode is overruled.
These are development tools only: never app/engine dependencies (CLAUDE.md#hard-rules), never a reason to skip the docs. If one is missing, say so in the plan and continue without guessing (docs/rules/CODING.md#a1-think-before-coding).

### 5.1 Visual check by step type
- **`app/` step without 👁:** start the dev app (`pnpm --dir app dev`); with Playwright CLI take screenshots of each changed screen (normal + error state) and attach them to the PR (not committed). If the step adds a user flow, add or extend an `@playwright/test` e2e test in `app/e2e/`. No Impeccable, break-ui or accessibility-review.
- **👁 step:** the full set. With Playwright CLI open each changed screen/state (empty, loading, normal, error, long JA/VI labels); save screenshots and attach them to the PR (not committed). Run Impeccable `critique` and `audit` on the changed components, Emil `break-ui` on the changed views, and `accessibility-review` (WCAG 2.1 AA). Fix in-scope findings; list the rest in the PR. If the step adds a user flow, add or extend an `@playwright/test` e2e test in `app/e2e/`.
- **Phase gate:** one Impeccable `audit` + `accessibility-review` over every screen changed in the phase; findings → `docs/RISKS.md` or new steps.
- A non-👁 step that changes layout, tokens or a shared component should be 👁: flag it to Quan.

### 5.2 Permission gate
_(allow or deny, never ask)_
Every tool call goes through `scripts/permission_gate.py` (a PreToolUse hook in `.claude/settings.json`). It answers **allow** or **deny** and never asks Quan. Golden rule: **anything outside this project is denied.**
- **Allowed:** files in the repo (and its `.claude/worktrees/`, sibling `vibechem-*` worktrees), Claude's own folders (`~/.claude`, the `claude` temp/scratchpad folder, `~/.gstack`, `~/.bun`), `uv`/`pnpm`/`npx`, `gh` (PRs, issues, runs, read-only `gh api`), `git` (normal work, pushes to your own step branch), WebSearch/WebFetch, Context7, Claude Docs, `scripts/merge_step.py`.
- **Denied:** paths outside those folders; other MCP servers (Gmail, Calendar, Drive, GitHub MCP, …); pushes to `main`/existing `phase-*`, force pushes, `reset --hard`, `clean -f`, `rebase`, `branch -D`, global git config; `gh pr merge`, repo settings, secrets, label edits, writing `gh api` calls; `.env` files; machine-wide installs and system tools; downloads from unknown hosts; gstack's shipping/deploying commands (`FORBIDDEN_SKILLS` in the gate); edits to `.claude/settings*.json` or the gate itself.
- A deny is final: pick an allowed route or stop with the matching docs/rules/WORKFLOW.md#stop-conditions code. Never work around it (e.g. by scripting the same action another way). If a deny is clearly a gate bug, add a failing case to `scripts/tests/test_permission_gate.py`, prepare the fix as a patch in the scratchpad and stop (`QUESTION`); Quan applies it (only he edits the gate or the settings).
- Quan can still run anything himself with the `!` prefix.
