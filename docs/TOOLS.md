# VibeChem — Claude Code skills, plugins and tools

> v0.4 · 2026-11-24 · Read by Claude Code when planning a step (CLAUDE.md §3, §13). Humans install these once per machine (Quan's setup guide).
> v0.3: Playwright **CLI** replaces the Playwright MCP server; GitHub MCP removed (`gh` only); design set = Impeccable + ui-ux-pro-max + four of Emil Kowalski's skills (frontend-design and Taste Skill dropped); Humanizer for prose; visual check on UI steps.
> v0.4: superpowers (plugin) and gstack (user skills, review helpers only) added; Impeccable and the knowledge-work engineering/design skills are **vendored skills** instead of plugins (the plugins ship hooks or remote MCP servers); permission gate (CLAUDE.md §13.2).
> All of these are **development tools only**. They never become app/engine dependencies (CLAUDE.md §4) and never override the project docs: METHODS.md for algorithms, DATA_MODEL.md for fields, UI_GUIDE.md for design, QA.md for quality.

## 1. Where each tool comes from
| Tool | Kind | Comes from | Licence | Installed by |
|---|---|---|---|---|
| `/phase`, `/step`, `/resume`, `/status`, `/bug` | project skills (commands) | `.claude/skills/<name>/SKILL.md` | ours | repo (committed) |
| step-runner | subagent | `.claude/agents/step-runner.md` | ours | repo (committed) |
| Context7 | MCP | `.mcp.json` | — | repo (approve once per machine) |
| Playwright CLI | npm dev tool + skill | `@playwright/cli` in `app/` devDependencies; skill from `playwright-cli install --skills`, committed under `.claude/skills/` (T0.04) | Apache-2.0 | repo; browser via `npx playwright install chromium` per machine |
| Playwright Test | npm dev dependency | `@playwright/test` in `app/` (e2e tests) | Apache-2.0 | repo |
| ui-ux-pro-max | skill | `.claude/skills/ui-ux-pro-max/` (nextlevelbuilder/ui-ux-pro-max-skill) | MIT | repo (committed) |
| break-ui, prototype, review-animations, animation-performance | skills | vendored from `emilkowalski/skills` at a pinned commit into `.claude/skills/` (T0.04; commit hash in THIRD_PARTY.md) | MIT | repo (committed) |
| Impeccable | skill | vendored from `pbakaus/impeccable` (`plugin/skills/impeccable/`) into `.claude/skills/impeccable/` at a pinned commit (THIRD_PARTY.md). The plugin is **not** installed: it registers SessionStart/PostToolUse/Stop hooks | Apache-2.0 | repo (committed); telemetry off via `.impeccable/config.json` and `DO_NOT_TRACK=1` in `.claude/settings.json` |
| Humanizer | plugin | `blader/humanizer` marketplace (Claude Code ≥ 2.1.142) | MIT | each machine |
| code-review | plugin | Claude Code plugin marketplace | — | each machine |
| testing-strategy, architecture, debug, deploy-checklist, documentation | skills | vendored from `anthropics/knowledge-work-plugins` `engineering/skills/` (THIRD_PARTY.md). The plugin is not installed: it adds remote MCP servers (Slack, Linear, GitHub MCP, …) | Apache-2.0 | repo (committed) |
| accessibility-review, ux-copy | skills | vendored from `anthropics/knowledge-work-plugins` `design/skills/` (same reason) | Apache-2.0 | repo (committed) |
| superpowers | plugin | `superpowers@claude-plugins-official` (obra/superpowers) | MIT | repo: `enabledPlugins` in `.claude/settings.json` (project scope); its SessionStart bootstrap hook is accepted |
| gstack | user skills | `git clone --single-branch --depth 1 https://github.com/garrytan/gstack.git ~/.claude/skills/gstack`, then `./setup` (needs Bun ≥ 1.4.2), then `gstack-config set update_check false`, `gstack-config set codex_reviews disabled`, telemetry off when asked. No team mode, no CLAUDE.md section from its installer | MIT | each machine (Quan runs the commands with `!`) |
| Permission gate | hook | `scripts/permission_gate.py`, registered in `.claude/settings.json` (CLAUDE.md §13.2) | ours | repo (committed) |
| `/review`, `/security-review` | built-in command | Claude Code | — | — |
Not used: Playwright MCP and GitHub MCP (token cost; `playwright-cli` and `gh` cover them) · the Impeccable plugin and the knowledge-work plugins (hooks / remote MCP servers; their skills are vendored instead) · `hamzafarooq/claude-code-starter` deploy-checklist (checks Vercel/Fly web apps calling the Claude API — not this desktop app) · gstack `/browse`, `/ship`, `/land-and-deploy`, `/modernize`, `/crew`, `/canary`, `/setup-deploy`, `/pair-agent`, `/ubicloud`, `/setup-gbrain`, `/setup-browser-cookies` (denied by the gate) · frontend-design (Impeccable is built on it) · Taste Skill (aimed at marketing websites with downloaded photos/fonts; candidate later for the docs site, T7.02) · Headroom (optional owner-side trial outside the repo; Claude Code never runs it).

## 2. What each tool is for
| Tool | Use it when | Rules |
|---|---|---|
| **Context7** | Before writing or debugging code that calls a library API: FastAPI, pydantic, scikit-learn, SciPy, pyarrow, loky, joblib, nanobind, scikit-build-core, cibuildwheel, React, React Flow, uPlot, Tailwind, shadcn/ui, i18next, Electron, electron-builder, Vitest, Playwright… | Query the **version pinned in TECH_STACK.md §1**, not "latest". Note library + version in the plan's *Tools* line. Not a source for algorithm definitions (METHODS.md is). |
| **code-review** | Every step before merge (CLAUDE.md §6.6); on request mid-step | Branch diff only. Fix findings inside the step; list the rest in the PR (A3). Never a reason to refactor untouched code. |
| **/security-review** | Steps marked 🔒 in §3 (auth, file parsing, file formats, IPC, installers, update check) | Run on the branch diff before ready; paste findings and how each was handled into the PR. An unresolved high finding is a stop (`RED_FLAG`). |
| **Playwright CLI** | Visual check on every `app/` step (CLAUDE.md §13.1); reproducing UI bugs; contact sheets (e.g. the glyph sheet) | Local dev app and localhost only. Snapshots/screenshots are written to disk (`.playwright-cli/`, git-ignored) and attached to the PR, never committed. Not a substitute for automated tests. |
| **Playwright Test** | e2e tests in `app/e2e/` from T0.10 onward; nightly on 3 OS | Tests are code: they follow QA.md and run in CI. |
| **Impeccable** | Steering and reviewing UI: `typeset`, `layout`, `quieter`, `distill`, `colorize`, `clarify`; review `critique`, `audit`; finish `polish`, `harden`, `adapt` | **UI_GUIDE.md wins.** Never `live`, never `init`/`document`/`extract` (no PRODUCT.md/DESIGN.md), no hook, no catalog-fetching "new design" flows, telemetry off. `bolder`, `delight`, `overdrive`, `animate` only when a step asks for it (the UI is deliberately calm). |
| **ui-ux-pro-max** | Gaps in UI_GUIDE.md (states, spacing, chart choice) and as a checklist | Same precedence; its demo code is never copied. |
| **break-ui** | Every `app/` step: worst-case data (2,000 spectra, empty dataset, 60-character JA/VI labels, 1 sample per group, missing values) | Findings in scope fixed; others listed. |
| **prototype** | When a step or Quan asks for alternatives (e.g. glyph variants, inspector layouts) | Produces options for Quan to choose; the chosen one goes into UI_GUIDE.md via the step's PR. |
| **review-animations, animation-performance** | Steps that add or change motion (running state, edge flow, panel transitions) | Respect `prefers-reduced-motion`; motion only where UI_GUIDE.md allows. |
| **accessibility-review** | Before ready on UI steps | Target WCAG 2.1 AA as UI_GUIDE.md states. |
| **ux-copy** | Labels, tooltips, error messages, empty states, first-launch text | EN source text into i18n files only; error text must match DATA_MODEL.md §7 codes. |
| **Humanizer** | Human-facing prose: README, docs site, first-launch guide, EN tooltip/help text, release notes, CHANGELOG, paper drafts, recruitment texts | Never on METHODS.md formulas, error messages tied to codes, CLAUDE.md, TASKS.md, PR status lines or code. Meaning must not change; JA/VI follow the i18n process. |
| **testing-strategy** | Planning QA tooling, leakage suite, golden tests, e2e tests | Output becomes the plan's checkpoints; QA.md levels and tolerances win. |
| **architecture** | Spikes, port-type design, phase gates, any new pattern | Writes ADRs in ARCHITECTURE.md §7 format; Quan accepts at the gate. |
| **debug** | Any bug, alongside CLAUDE.md §7 | CLAUDE.md §7 order wins. |
| **superpowers** | `test-driven-development` for each checkpoint (failing test → code → green → commit); `systematic-debugging` with CLAUDE.md §7; `verification-before-completion` before DONE, "ready" or "fixed"; `writing-plans`/`executing-plans` only as help for the §3 plan, which still lives in `docs/handoff/<step>.md`; `dispatching-parallel-agents` only when the phase runner asks | Never `brainstorming` in phase mode (stop with `QUESTION` instead); `using-git-worktrees` only under `.claude/worktrees/`; never `finishing-a-development-branch` (merge = `merge_step.py`). Commit messages follow CLAUDE.md §3 step 5. |
| **gstack** | `/plan-eng-review` (and `/plan-design-review` for UI) on the plan of M/L steps, spikes and phase gates; `/qa`, `/design-review` on 👁 steps next to the visual check; `/cso` next to `/security-review` on 🔒 steps; `/review` as a second opinion after code-review; `/careful` guard stays on | Review and report only: when a gstack skill offers to fix, commit or push, follow CLAUDE.md §3 instead. Forbidden list above (gate-enforced). Outside reviews (Codex) and the update check are off. |
| **deploy-checklist** | Installer, release and phase-gate steps | Merge its items into QA.md §9 checklists; don't replace them. |
| **documentation** | READMEs, docs site, first-launch guide text | Facts come from the docs; then Humanizer. |

## 3. Step map
🔒 = also run `/security-review` (+ gstack `/cso`). 👁 = visual check (CLAUDE.md §13.1: Playwright CLI screenshots + Impeccable critique/audit + break-ui + accessibility-review; + gstack `/qa` and `/design-review`).

| Steps | Tools |
|---|---|
| Every step that writes code | code-review + superpowers `test-driven-development` + `verification-before-completion` |
| Every bug fix | debug + code-review (+ Playwright CLI to reproduce UI bugs) |
| T0.01, T0.06 (CI) | Context7 (GitHub Actions, cibuildwheel) · `gh run view --log-failed` for CI logs |
| T0.02 (repo skeleton, legal, merge script) | documentation + Humanizer (README, CONTRIBUTING) |
| T0.03, T0.05 (Python workspace, native) | Context7 |
| T0.04 (app workspace) | Context7 · install `@playwright/cli` + `@playwright/test`, commit the playwright-cli skill, vendor the four Emil skills · ui-ux-pro-max |
| T0.07 (QA tooling) | testing-strategy + Context7 |
| T0.09 (engine skeleton) 🔒 | Context7 (FastAPI) |
| T0.10 (skeleton UI) 👁 | Context7 + Impeccable + first `@playwright/test` Electron e2e test |
| T0.11 (shell + installers) 🔒 | Context7 (Electron, electron-builder, PyInstaller) + deploy-checklist |
| T0.12, T0.13 (spikes) | architecture (ADR update) + Context7 + gstack `/plan-eng-review` |
| T0.14 (port-type design) | architecture |
| Phase gates | architecture + deploy-checklist + gstack `/plan-eng-review` |
| T1.01–T1.03 (dataset, block contract, schema) | Context7 (pydantic, scikit-learn API conventions) |
| T1.05, T1.06 (readers) 🔒 | Context7 (pyarrow, openpyxl, jcamp) |
| T1.07–T1.14 (blocks, metrics) | Context7 (scikit-learn, SciPy, chemotools) |
| T2.03 (file format) 🔒 | Context7 (pydantic, jsonschema) |
| T2.05, T2.13 (leakage suite, golden) | testing-strategy |
| T2.06–T2.12 (cache, executor, runners, CLI, bench) | Context7 (joblib, loky, threadpoolctl) |
| Phase 3 (C++) | Context7 (nanobind, Eigen, cibuildwheel) |
| T4.01, T4.02 (engine server, WebSocket) 🔒 | Context7 (FastAPI) |
| Glyph set (Phase 4, 👤) 👁 | prototype + Impeccable `critique` + Playwright CLI contact sheet |
| T4.03–T4.11 (UI) 👁 | Context7 + Impeccable + ui-ux-pro-max + break-ui + accessibility-review + ux-copy (+ review-animations where motion changes) |
| T5.01, T5.04 (shell, update check) 🔒 | Context7 (Electron) |
| T5.03 (installers + first-launch guide) 👁 | deploy-checklist + ux-copy + documentation + Humanizer |
| T5.05 (e2e) | testing-strategy + Playwright Test + Context7 |
| Phase 6 tooltip content | ux-copy + Humanizer |
| T7.01, T7.06 (release) | deploy-checklist · T7.02 docs site: documentation + Humanizer (Taste Skill may be evaluated here) · T7.04 paper: Humanizer |

## 4. If a tool is missing
Say so in the plan's *Tools* line and continue with the docs and official documentation. Don't block the step and don't guess APIs (CLAUDE.md A1). A missing project command, the step-runner subagent, or the Playwright CLI on a 👁 step → stop `MISSING_INPUT`.
