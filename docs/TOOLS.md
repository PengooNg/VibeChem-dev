# VibeChem — Claude Code skills, plugins and tools

> v0.5 · 2026-11-26 · Read by Claude Code when planning a step (CLAUDE.md §3, §13). Humans install these once per machine (Quan's setup guide).
> v0.3: Playwright **CLI** replaces the Playwright MCP server; GitHub MCP removed (`gh` only); design set = Impeccable + ui-ux-pro-max + four of Emil Kowalski's skills; Humanizer for prose; visual check on UI steps.
> v0.4: superpowers (plugin) added; Impeccable and the knowledge-work skills are **vendored skills** instead of plugins; permission gate (CLAUDE.md §13.2).
> v0.5: **caveman, ponytail and ECC** vendored (copied, not installed as plugins: no hooks, no band) and given precedence over the project rules where they conflict (CLAUDE.md "Precedence"); **gstack, the code-review plugin, `debug` and `deploy-checklist` dropped**; ponytail-review is the review gate; K removed (Quan is the only human reviewer).
> All of these are **development tools only**. They never become app/engine dependencies (CLAUDE.md §4).

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
| Permission gate | hook | `scripts/permission_gate.py`, registered in `.claude/settings.json` (CLAUDE.md §13.2) | ours | repo (committed) |
| `/security-review` | built-in command | Claude Code | — | — |

**Not used** (and why):
| Tool | Why not |
|---|---|
| gstack (all of it) | Dropped in v0.5 (D3): its review helpers duplicate ponytail-review and ECC; the rest ships, deploys or leaves the project. The gate still denies its dangerous commands (`FORBIDDEN_SKILLS`) |
| code-review plugin, `/review` | Dropped in v0.5: ponytail-review is the review gate |
| `debug`, `deploy-checklist` skills | Dropped in v0.5 (D4): CLAUDE.md §7 + ponytail's bug rule + superpowers `systematic-debugging` cover debugging; QA.md §9 holds the release checklist |
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
| ECC `strategic-compact`, `context-budget` | CLAUDE.md §8.2 covers this |
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
| **ponytail** (level `full`) | Whenever code is written: Python, C++, TypeScript, scripts, tests, CI | Wins over CLAUDE.md Part A/§12 where they conflict (CLAUDE.md "Precedence" table). Blocks keep header docstring + `# Step N:` comments (D6). Licence rules (CLAUDE.md §12.2) still apply. Its "skipped / risk" closing lines go into the PR *Assumptions* section |
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
| **Playwright CLI** | Visual check on every `app/` step (CLAUDE.md §13.1); reproducing UI bugs; contact sheets | Local dev app and localhost only. Screenshots go to `.playwright-cli/` (git-ignored) and are attached to the PR, never committed |
| **Playwright Test** | e2e tests in `app/e2e/`; nightly on 3 OS | Tests are code: they follow QA.md and run in CI |
| **Impeccable** | Steering and reviewing UI: `typeset`, `layout`, `quieter`, `distill`, `colorize`, `clarify`; review `critique`, `audit`; finish `polish`, `harden`, `adapt` | **UI_GUIDE.md wins.** Never `live`, never `init`/`document`/`extract`, no hook, no catalog-fetching "new design" flows, telemetry off. `bolder`, `delight`, `overdrive`, `animate` only when a step asks for it |
| **ui-ux-pro-max** | Gaps in UI_GUIDE.md (states, spacing, chart choice) and as a checklist | Same precedence; its demo code is never copied |
| **break-ui** | Every `app/` step: worst-case data (2,000 spectra, empty dataset, 60-character JA/VI labels, 1 sample per group, missing values) | Findings in scope fixed; others listed |
| **prototype** | When a step or Quan asks for alternatives | Options for Quan; the chosen one goes into UI_GUIDE.md via the step's PR |
| **review-animations, animation-performance** | Steps that add or change motion | Respect `prefers-reduced-motion`; motion only where UI_GUIDE.md allows |
| **accessibility-review** | Before ready on UI steps | WCAG 2.1 AA, as UI_GUIDE.md states |
| **ux-copy** | Labels, tooltips, error messages, empty states, first-launch text | EN source text into i18n files only; error text must match DATA_MODEL.md §7 codes |
| **Humanizer** | Human-facing prose: README, docs site, first-launch guide, EN tooltip/help text, release notes, CHANGELOG, paper drafts | Never on METHODS.md formulas, error messages tied to codes, CLAUDE.md, TASKS.md, PR status lines or code. Meaning must not change |
| **testing-strategy** | Planning QA tooling, leakage suite, golden tests, e2e tests | Output becomes the plan's checkpoints; QA.md levels and tolerances win |
| **architecture** | Spikes, port-type design, phase gates, any new pattern | ADRs in ARCHITECTURE.md §7 format; Quan accepts at the gate |
| **superpowers** | `test-driven-development` for **non-trivial logic only** (ponytail test rule); `systematic-debugging` with CLAUDE.md §7; `verification-before-completion` before DONE, "ready" or "fixed"; `writing-plans`/`executing-plans` only as help for the §3 plan, which lives in `docs/handoff/<step>.md` | Never `brainstorming` in phase mode (stop with `QUESTION`); `using-git-worktrees` only under `.claude/worktrees/`; never `finishing-a-development-branch` (merge = `merge_step.py`). No skill-use announcements to Quan (caveman) |
| **documentation** | READMEs, docs site, first-launch guide text | Facts come from the docs; then Humanizer |

## 3. Step map
Every step that writes code: **ponytail + ponytail-review** + superpowers `verification-before-completion` (`test-driven-development` for non-trivial logic). Add per area: `packages/core`, `packages/engine`, `packages/native`, `scripts/` → **silent-failure-hunter**; `packages/native` / Phase 3 → **cpp-reviewer**; T2.05 and phase gates → **mle-reviewer**. 🔒 = also `/security-review`. 👁 = visual check (CLAUDE.md §13.1: Playwright CLI screenshots + Impeccable critique/audit + break-ui + accessibility-review).

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
| Phase gates | architecture + council (go/no-go) + ponytail-audit + ponytail-debt + mle-reviewer (+ production-audit from Phase 5) + product-capability and intent-driven-development to detail the next phase · `docs/RISKS.md` updated |
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
Say so in the plan's *Tools* line and continue with the docs and official documentation. Don't block the step and don't guess APIs (CLAUDE.md A1). A missing project command, the step-runner subagent, the ponytail/ponytail-review skills, or the Playwright CLI on a 👁 step → stop `MISSING_INPUT`.
