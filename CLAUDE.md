# CLAUDE.md — rules for working on VibeChem

> v1.0 · 2026-11-26 · Part A (how to think and work) is adapted from the four principles in `multica-ai/andrej-karpathy-skills` (MIT), based on Andrej Karpathy's observations of common LLM coding mistakes; A2 and A3 now defer to ponytail. Part B (§1–§14) holds VibeChem's own rules; other docs cite these as "CLAUDE.md §N". When Part B is more specific, Part B wins — except where the **Precedence** section below says otherwise.
> v1.0: caveman, ponytail and ECC take precedence (tooling v0.5, decisions D1–D6); K removed from the workflow (Quan is the only human reviewer; §15 deleted).

---

# Precedence (read first)
Where rules conflict, the higher item wins. Where nothing conflicts, every rule below still applies unchanged.
1. **Fixed mechanics** — no text can change these:
   - `scripts/permission_gate.py` and the deny list in `.claude/settings.json` (Quan-only files, §13.2).
   - `scripts/merge_step.py` checks: base is `phase-*`, the PR is not a draft, CI is green, the step is not 👤, the title starts with `[T`, `[BUG` or `[SYNC]`.
   - Branch protection.
   - Checkpoint commit prefix `T<x> cpN:` (`/resume` rebuilds lost handoff notes from it).
2. **Quan's decisions D1–D6** (tooling v0.5): D1 skills are copied, never installed as plugins (no caveman/ponytail/ECC hooks, no band) · D2 caveman voice for PR text · D3 gstack dropped · D4 `debug` and `deploy-checklist` dropped · D5 the K backlog became `docs/RISKS.md` · D6 blocks keep numbered `# Step N:` comments.
3. **caveman, ponytail, ECC** (`.claude/skills/`, `.claude/agents/`; what each is for: `docs/TOOLS.md` §2).
4. Everything else: this file, TOOLS.md, QA.md, METHODS/DATA_MODEL/UI_GUIDE, superpowers, Impeccable, the design skills, Humanizer and the rest.

Override means precedence, not "install everything": the excluded parts of the three repos stay excluded (TOOLS.md §1 "Not used").

## How the known conflicts resolve
| Conflict | Old rule | Now |
|---|---|---|
| Code comments | block-template: `# Step N:` comments matching METHODS.md plus line comments for review | **Blocks (D6):** header docstring + numbered `# Step N:` comments matching METHODS.md stay mandatory; beyond those, ponytail: no other line comments except a one-line "why". **Other code:** ponytail only. `shortcut: <limit>, <when to upgrade>` comments are allowed everywhere |
| Test amount | QA.md §7 / §6.1: tests for every changed function, plus reference and property tests for algorithms | **ponytail:** non-trivial logic gets one small test; trivial changes get none. For an algorithm block that one test is a **reference test against an independent value** (a block without one is unfinished). Property tests and extra unit tests are optional. superpowers TDD only for non-trivial logic. The golden and leakage suites stay (existing tests are never deleted) |
| Reuse order (§12) | Our repo → stack libraries → new packages → port → build; a full estimate table for every plan | **ponytail ladder** (§12.1). A new dependency only when our minimum code would be large, never "for a few lines". The §12.4 estimate table only for M/L steps. The `REUSE` stop for M+ stays; ECC `council` drafts the recommended answer. Licence rules (§12.2) unchanged |
| Part A, A2 and A3 | Own text | "Apply the `ponytail` skill (full)." A1 and A4 stay |
| Diff review | code-review plugin, gstack `/review` second opinion | **ponytail-review is the gate.** `/security-review` stays on 🔒 steps. ECC agents per area (TOOLS.md §3) |
| Bug fixing | §7 order + `debug` skill + superpowers | §7 order stays, **plus ponytail's bug rule:** grep every caller of the touched function and fix the root cause once in the shared code |
| PR text | Plain prose (caveman's own rule 5 also says plain) | **caveman voice in the narrative sections** (D2 beats the upstream rule). Template headings, Status line, health summary, code, paths and commands stay exact. Questions to Quan in full sentences |
| Talking to Quan | Report formats, superpowers announcing skills | **caveman.** Fixed formats are payload and stay verbatim: `▶`/`✓` lines, DONE/STOP blocks, "Stopping safely: <reason>.". No skill-use announcements |
| Planning and stops | The phase runner prints the stop as it is | ECC `council` drafts the "recommended answer" (≤ 5 lines) for `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG` stops. ECC `intent-driven-development` rewrites a vague "Done when" into AC lines. `product-capability` details the next phase from PRD F-xx (PRD.md is its product-context file) |
| Risk | Spread across PROGRESS.md notes | ECC `council`, `production-audit`, `loop-design-check`, plus `ponytail-audit` and `ponytail-debt`, all feed **`docs/RISKS.md`**, updated at gates and on `S1_BUG` / `RED_FLAG` stops |

# Voice
- The main session and the phase runner load **caveman** at session start and talk to Quan in it, in Quan's language. The step-runner does not load it.
- Nobody uses caveman inside files: code, comments, docstrings, commits, docs, handoff notes.
- PR descriptions and PR comments: caveman in the narrative sections only (D2).

---

# Part A — How to work (always applies)

These rules trade speed for care. For a trivial change (typo, one-line doc fix) use judgment and skip the ceremony, but never skip tests or the "never do" list (§4).

## A1. Think before coding
- **State your assumptions** explicitly in the plan. If an assumption changes behaviour, results or the architecture, it is a stop condition (§14.3) — don't pick silently.
- **Show alternatives** when a request can be read more than one way, and say which one you'd choose and why.
- **Push back** when a simpler approach exists or a request conflicts with the docs. Say so before writing code.
- **When something is unclear, stop.** Name exactly what is confusing and ask one short question. A question costs the user seconds; a wrong guess costs a review and a rewrite.
- **Never invent facts:** field names, error codes, port types, file formats, library APIs or paper equations. Look them up (DATA_MODEL.md, METHODS.md, and **Context7 for library APIs at the pinned version** — §13) or ask.
- List any assumptions still open at the end of the plan and of the PR description.

## A2. Simplicity first
Apply the `ponytail` skill (full).

## A3. Surgical changes
Apply the `ponytail` skill (full).

## A4. Goal-driven execution
- Turn every task into **checkable goals** before coding. "Fix the bug" → write a test that reproduces it, then make it pass. "Add MSC" → reference test against an independent value passes, `check.py` is green.
- For multi-step work, write a short plan where **each checkpoint has its own check** (which test or command proves it is done).
- Loop until the checks pass. Don't declare success on reasoning alone — run the tests.
- The step's **"Done when"** in TASKS.md is the success criterion. If it is too vague to check, that is a stop condition.

**Signs these rules are working:** small diffs, simple first drafts, questions asked before implementing rather than after a mistake, few rewrites in review.

---

# Part B — VibeChem specifics

## 1. What VibeChem is
A free, open-source (GPL-3.0-or-later) desktop app for chemometrics on vibrational and hyperspectral spectra. Python engine and blocks, C++20 kernels, React/TypeScript UI, Electron shell. Built mostly by AI; owner and only human reviewer: **Quan**. Infrastructure, C++ and packaging review is covered by the ECC agents and the phase-gate audits (§10).

## 2. Doc map — read only what the step tells you
| Need | File |
|---|---|
| The step you are doing (what to read, files, size, reuse candidates, done criteria) and the phase run order | `docs/TASKS.md` |
| What happened so far, open stops | `docs/PROGRESS.md` |
| Open risks, unreviewed infrastructure, audit findings | `docs/RISKS.md` |
| What the product does, feature IDs (F-xx) | `docs/PRD.md` |
| Every function, its priority and likely reuse source | `docs/FUNCTION_CATALOG.md` |
| System design, ADRs, technical decisions | `docs/ARCHITECTURE.md` |
| Versions, folder layout, package boundaries, conventions, commands, CI, branches, **reuse register**, legal files | `docs/TECH_STACK.md` |
| Exact field names, endpoints, events, error codes, formats | `docs/DATA_MODEL.md` |
| Algorithm definitions, references, tolerances | `docs/METHODS.md` (from T1.04) |
| Colours, type, layout, components, tooltips | `docs/UI_GUIDE.md` |
| Tests, quality levels, bug protocol, definition of done, phase-gate checklist | `docs/QA.md` |
| Which skills, plugins and MCP tools to use for this step | `docs/TOOLS.md` (§3 row for your step) |
Before editing a package, also read that package's `README.md`. The owner's manual and project plan are kept outside the repo; you don't need them.

## 3. How a step runs
A step runs either inside `/phase N` (normal) or alone via `/step <ID>`. In phase mode the main session is the **phase runner** and each step is executed by the **step-runner** subagent (`.claude/agents/step-runner.md`) so every step starts with a fresh context.

1. **Prepare:** read the step in `docs/TASKS.md`, its row in `docs/TOOLS.md` §3, and only the files/sections the step lists. Check dependencies are ticked; if not → stop (§14.3 `DEPENDENCY`).
2. **Already started?** `gh pr list --search "[T<x>]" --state open`. If a PR exists, follow **Resuming** (§8.3).
3. **Plan** (written, not waited on): assumptions and open questions (A1) · reuse scan and estimate (§12) · tools for this step (§13) · files to create/change (only those listed, plus tests) · checkpoints, each with the command that proves it done (A4). Put the plan in `docs/handoff/<step-id>.md` and in the draft PR description.
   - **In phase mode do not wait for approval.** Proceed unless a stop condition in §14.3 applies. If one applies, stop *before* writing code.
   - With `/step` and an explicit "wait for my approval", wait.
4. **Branch** from the current phase branch: `git switch phase-<N> && git pull && git switch -c t<step>-<short-name>` (e.g. `t1-07-snv-msc`). Never commit to `main` or directly to `phase-*`.
5. **Checkpoints, one at a time.** After each: `check.py --fast --only <area>` → commit (`T1.07 cp2: MSC block + tests`) → push → update the handoff note and the PR **Status** line.
6. **After the first checkpoint** open a **draft PR** with base `phase-<N>`:
   - Title `[T1.07] <step title>` · label `in-progress` · description starts with the Status line (§8.1).
7. If the work grows beyond ~1.5× the planned checkpoints → stop (§14.3 `ESTIMATE`).
8. **Finish:** quality duties (§6), then merge (§14.2). In phase mode return a one-paragraph DONE report to the phase runner.

## 4. Never do
- Never invent API fields, file-format fields, error codes or port types — use `docs/DATA_MODEL.md`; propose additions there first.
- Never add a dependency that is not in `docs/TECH_STACK.md` §1 or approved from its reuse register (§11 there).
- Never build from scratch something the reuse register or §12 search shows already exists, without Quan's explicit approval.
- Never copy code from another project unless its licence is GPL-3.0-compatible; ported code keeps the original copyright, gets a source header, and is listed in `THIRD_PARTY.md`.
- Never trust an external library's numbers blindly: every reused algorithm gets the same reference tests as our own code, with expected values from an independent source.
- Never use pickle (or `allow_pickle=True`) for anything saved or shared.
- Never loosen a test tolerance, delete/skip a test, or regenerate golden files without saying so explicitly in the PR — in phase mode this is a stop condition (`RED_FLAG`).
- Never bypass the block contract (`vibechem_core/block.py`) or import across forbidden package boundaries (TECH_STACK.md §3.1).
- Never fit anything on validation/test data; fitted steps use `fit` on training rows only.
- Never use global random state; accept a `numpy.random.Generator`.
- Never hard-code user-visible text; use i18n keys (EN/JA/VI).
- Never make network calls from the app or engine (except the update check in the Electron main process).
- Never introduce a new architectural pattern without an ADR in `docs/ARCHITECTURE.md` §7.
- Never stop in the middle of an edit, leaving a file half-written or the branch uncommitted (§8).
- Never commit tokens or secrets; credentials come from environment variables only.
- **Never merge into `main`, push to `main` or `phase-*` directly, force-push, rewrite history, delete branches other than your own merged step branch, or change repository settings, rulesets or labels' meaning.** Merging a step PR into its phase branch goes only through `scripts/merge_step.py` (§14.2). Merging `phase-N → main` is always Quan's action.
- Never merge a step marked 👤 — prepare it and stop (§14.3 `HUMAN_STEP`).

## 5. Block template and comment style
Every block is one file with a header docstring, typed parameters and numbered `# Step N:` comments matching `docs/METHODS.md` (D6: these stay mandatory even though ponytail limits comments; beyond them, only one-line "why" comments and `shortcut:` comments). **Before writing, changing or reviewing any block, load the `block-template` skill** (`.claude/skills/block-template/SKILL.md`) — it holds the full template and example.

## 6. Quality duties before merging a step (QA.md §7)
1. Tests follow ponytail (Precedence table): non-trivial logic gets one small test in the mirrored test file; trivial changes get none. Every algorithm block (including wrapped libraries) has a **reference test against an independent value**. Bugs get a regression test.
2. Run the **full** `uv run python scripts/check.py --fast` until everything is PASS.
3. Regenerate `reports/reference_report.md` (done by `check.py`) and check that new methods appear in it.
4. Paste the **health summary** printed by `check.py` into the PR description.
5. Fill every section of the PR template: TASKS step, files changed, tests added, docs updated, **plan as executed**, **reuse decision** (§12), **tools used** (§13), estimate vs actual checkpoints, assumptions, anything you were unsure about (including ponytail's "skipped / risk" lines), unrelated issues noticed but not touched.
6. **Diff self-review:** run **ponytail-review** on the branch diff, plus the ECC agents for the areas touched (TOOLS.md §3: silent-failure-hunter, cpp-reviewer, mle-reviewer); for steps marked 🔒 also run **`/security-review`**; for 👁 steps also do the **visual check** (§13.1). Fix what is in scope and list the rest. Then check the red flags in QA.md §4. Any red flag you cannot undo → stop (`RED_FLAG`).
7. If a dependency was added: update TECH_STACK.md §1 and §11 and `THIRD_PARTY.md` (if code was copied) in the same PR. Update `CHANGELOG.md` if behaviour changed.
8. Tick the step in `docs/TASKS.md` (status overview) in the same PR.
9. **Update `docs/PROGRESS.md`** in the same PR: "Now" table and one Step-log row. If a review finding, dependency or ADR leaves a risk open, add a row to **`docs/RISKS.md`**.
10. Delete `docs/handoff/<step-id>.md`, set the Status line to `Status: complete — merging`, remove `in-progress`/`paused` labels, mark the PR **ready for review**.

## 7. When something fails — bug protocol (A4 applied; full version: QA.md §6)
Use superpowers **systematic-debugging** alongside this protocol; this order wins if they differ. **ponytail's bug rule applies on top:** before editing, grep every caller of the function you touch, and fix the root cause once in the shared code.
1. **Reproduce**: write the smallest failing test that shows the bug; commit it first. This test is the success criterion.
2. **Locate**, in this order, and stop at the first that points somewhere:
   failing test path (tests mirror source paths) → error code origin (DATA_MODEL.md §7 lists the defining module) → `node_id`/`block_id`/`trace_id` in logs → golden test's first divergent node → `git bisect` between the last green commit and now.
3. **Read only** that module, its package README, its tests and the relevant METHODS.md / DATA_MODEL.md section. If the failure involves a library call, check its documented behaviour for our pinned version with Context7 before assuming a bug.
4. **Explain** the root cause in 2–3 sentences in the PR before changing code. If the cause is inside a reused library, say so; prefer pinning a version, a documented workaround or an upstream issue over patching vendored code.
5. **Fix** in the smallest scope (ponytail); no unrelated refactoring.
6. **Verify**: the new test passes, then the module's tests, then `check.py --fast`. The new test stays as a regression test.
7. **Report** in the PR: Root cause · Fix · Test added · Possibly affected areas. Bug PR title: `[BUG #<issue>] <short description>`; base = the current phase branch.
- A bug found **during** a step that is inside the step's scope: fix it in the step. Outside the scope: open an issue, note it in PROGRESS.md, continue the step.
- A suspected **S1** (silent wrong number, leakage) anywhere: stop (`S1_BUG`) — Quan decides before any further feature work.
- A bug in your own step that CI keeps showing red: up to **2 fix attempts**, then stop (`CI_RED`).

## 8. Status, context limits and resuming
### 8.1 Status line (first line of every step PR description)
`Status: <state> · next: <action> · machine: <$VIBECHEM_MACHINE> · updated <YYYY-MM-DD HH:MM>`
States: `cp2/4 done` · `PAUSED at cp2/4` · `STOPPED: <CODE>` · `complete — merging`.

### 8.2 Stop safely, never mid-section
You cannot see exactly how much context or usage is left, so work so that an interruption at any moment is harmless.

**Always:** keep every checkpoint small (one block, one module, one test group); after each checkpoint tests pass → commit → push → update handoff note and Status line; never start a new file or large edit unless you expect to finish and commit it.

**Stop and hand off (`CONTEXT`) when:** the system warns that context is low or will be compacted · the step session is long (≈ 3 checkpoints, many large files read, repeated failed attempts) · a usage-limit warning appears · you notice you are re-reading files or losing track of earlier decisions.

**How to stop (any stop code, in this order):**
1. Finish or revert the edit in progress so every file is complete and valid.
2. Run the tests for the finished part; record failures rather than hiding them.
3. Commit (`T1.07 WIP cp3: <what is done>`) and push. If no PR exists yet, open the draft PR now.
4. Write/update `docs/handoff/<step-id>.md`:
   ```
   # Handoff — T1.07
   Branch: t1-07-snv-msc   Base: phase-1   Last commit: <hash>   PR: #<number>
   Stop code: CONTEXT   Machine: work-pc
   Plan: <link to plan section or copy>
   Done: cp1 SNV + tests; cp2 MSC + tests
   Not done: cp3 detrend (not started), cp4 cut
   Failing tests (if any): none
   Decisions made: MSC wraps chemotools
   Question for Quan (if any): —
   Files read that matter: docs/METHODS.md#msc, packages/core/src/vibechem_core/block.py
   Next action: implement detrend per METHODS.md#detrend, then property tests
   ```
5. PR: Status line `PAUSED at cp2/4` (for `CONTEXT`) or `STOPPED: <CODE>`; label `paused` (context) or `needs-quan` (any other code); comment with the question or the required action.
6. Report (to the phase runner, which tells Quan): **"Stopping safely: <reason>."** + step ID, PR, done, remaining, what Quan must do, and that `/resume` continues.

### 8.3 Resuming
Read CLAUDE.md, the step in TASKS.md and the handoff note; check out the branch; `git pull`; run the tests; apply Quan's answer if the stop was a question; switch the label back to `in-progress`; continue from "Next action". Do not redo finished checkpoints. If the session was cut off without a note, rebuild the note from the commit history first.

### 8.4 Two machines (work PC on weekdays, laptop on weekends)
- Every session starts with the **session preflight** (§14.1): fetch, clean tree, pull the phase branch, sync environments.
- Never leave work only on one machine: every stop ends with commit + push (§8.2).
- `$VIBECHEM_MACHINE` (set once per machine: `work-pc` / `laptop`) goes in the Status line and handoff note.
- If an open step PR is labelled `in-progress` (not `paused`) when a session starts, it may be running on the other machine or was cut off: ask Quan before touching it.

### 8.5 Status request (`/status`, or "where are we?")
Follow `.claude/skills/status/SKILL.md` (read-only; change nothing).

## 9. Commands
| Command | Use |
|---|---|
| `uv run python scripts/check.py --fast --only <area>` | After each checkpoint (`core`, `engine`, `native`, `app`) |
| `uv run python scripts/check.py --fast` | Before marking a PR ready (must be all PASS) |
| `uv run pytest <test file>` | One test file |
| `pnpm --dir app dev` | Run the app in development |
| `gh pr list --state open` | Steps in progress, paused, stopped |
| `gh pr checks <n> --watch` | Wait for CI on a PR |
| `uv run python scripts/merge_step.py <pr>` | The only way to merge a step PR (§14.2) |
Full list: `docs/TECH_STACK.md` §7.

## 10. Reviews
Quan is the only human reviewer: everything goes to him (CODEOWNERS), and he spot-checks merged steps and reviews fully at the phase gate. The agent lenses cover what a second reviewer would:
- Every code change → **ponytail-review**.
- Engine, core, native, scripts (formats, API, scheduler, ports, error handling) → **silent-failure-hunter**.
- C++ and native build → **cpp-reviewer** (plus TECH_STACK.md §5 rules).
- Leakage, splits, metrics, reproducibility → **mle-reviewer** (T2.05 and gates).
- CI, packaging, installers, dependencies → `/security-review` on 🔒 steps, and the gate audits (ponytail-audit, production-audit from Phase 5).
Open findings from any of these go into `docs/RISKS.md`.

## 11. When unsure
See A1 and §14.3: ask before guessing. Prefer a short stop with one clear question over a wrong assumption.

## 12. Reuse first, and estimate before committing (ponytail applied)
Writing code we could have reused wastes the owner's time and money. Before planning any implementation:

**12.1 The ponytail ladder (take the first rung that fully works)**
1. Does it need to exist? Skip features, options and flexibility nobody asked for; name them in one line.
2. Already in this codebase: this repo, the step's "Reuse" line in TASKS.md, TECH_STACK.md §11 reuse register, FUNCTION_CATALOG.md "Likely source" notes.
3. Standard library or platform feature.
4. An installed dependency: NumPy, SciPy, scikit-learn, pyarrow, React Flow, uPlot, etc. (check the API with Context7, §13).
5. One line a reader gets at a glance.
6. Otherwise the minimum code. A **new dependency** (PyPI, conda-forge, npm) or a **port** from GPL-compatible code (Orange/Quasar, GPL-3.0; pengoo only from parts Quan provides — pengoo is never copied wholesale; missing files → stop `MISSING_INPUT`) only when our minimum code would be large, never "for a few lines".
If you cannot search the web in this session, list the candidates you know; if the step is M or larger, stop (`REUSE`) and ask Quan to confirm before building.

**12.2 Judge each candidate**
| Criterion | Acceptable |
|---|---|
| Licence | MIT, BSD, Apache-2.0, LGPL, GPL-3.0 (GPL-compatible) |
| Maintenance | Release or commit in the last ~18 months; issues answered |
| Quality | Has tests; used by others; correct against METHODS.md (we verify with our reference tests) |
| Fit | Covers most of what the step needs without forcing a different architecture |
| Cost | Install size, extra native dependencies, Windows/macOS/Linux wheels available, Python 3.14 support |
| Safety | No network calls, no pickle loading of shared files |

**12.3 Decide: reuse > wrap > port > build**
- **Reuse** as a dependency (add to TECH_STACK.md) when it fits well.
- **Wrap** it behind our block contract when the API differs.
- **Port** (copy + adapt) only for small, stable code from GPL-compatible sources, with header + `THIRD_PARTY.md`.
- **Build** only when nothing fits, or when our own code is clearly smaller and simpler than the dependency (e.g. SNV is 4 lines of NumPy; a 20 MB package for it is not worth it).

**12.4 Estimate before committing** — for **M and L steps only**, put this table in the plan (S steps: one line naming the rung of the ladder you took):
| Option | What it covers | Licence / maintenance | Effort (checkpoints, ~files, ~lines) | Risks |
|---|---|---|---|---|
| Reuse/wrap `<package>` | … | … | … | … |
| Port from `<project>` | … | … | … | … |
| Build ourselves | … | — | … | … |
Recommendation: one line. Sizes: **S** = 1–2 checkpoints, **M** = 3–4 checkpoints (one session), **L** = more than 4.
An **L** estimate: split the step into `T<x>a`, `T<x>b` … in TASKS.md (same format, same total scope, dependencies kept) inside the first sub-step's PR and continue with `a`. If splitting would change the scope → stop (`ESTIMATE`).

**12.5 Stop and ask Quan (stop code `REUSE`, before any code) when:**
- A reusable option exists but you recommend building anyway.
- Building would be **M or larger** and no strong reuse option was found — show what you searched.
- The best option has a licence, maintenance or size concern.
- Your estimate is more than double the size given in TASKS.md.
- The reuse decision changes the architecture or adds a native dependency.
For a `REUSE` stop the phase runner reads `.claude/skills/council/SKILL.md` and drafts the recommended answer (≤ 5 lines).
Adding a pure-Python dependency that is already listed as a candidate in TECH_STACK.md §11 for this step, with an acceptable licence and no concern above, does **not** need a stop: approve it in the PR (and add a `docs/RISKS.md` row if a concern stays open).

## 13. Skills, plugins and tools
The full list, rules and **per-step map** are in `docs/TOOLS.md`. Read your step's row there when planning and name the tools in the plan's *Tools* line. Short version:
- **caveman** — voice for talking to Quan and for PR narrative (see "Voice"); never inside files.
- **ponytail** (full) — whenever code is written; **ponytail-review** before every merge (§6.6), plus the ECC agents per area (**silent-failure-hunter**, **cpp-reviewer**, **mle-reviewer**) and `/security-review` on 🔒 steps.
- **ECC skills, read by path** (gate-only, not auto-invoked): `council` (stop answers, go/no-go), `intent-driven-development` (vague "Done when"), `product-capability` (next-phase detail from PRD), `production-audit` (gates from Phase 5), `loop-design-check` (runner audits); with `ponytail-audit` and `ponytail-debt` at gates. All risk findings → `docs/RISKS.md`.
- **Context7** (MCP) — check library APIs at the pinned version before writing or debugging library calls.
- **Playwright CLI** (`playwright-cli` skill, run through Bash) — open the dev app, click through, screenshot. The project uses the CLI, not the Playwright MCP server (fewer tokens). Automated e2e tests use `@playwright/test`.
- **Design:** **Impeccable** (steer: `typeset`, `layout`, `quieter`, `distill` …; review: `critique`, `audit`; finish: `polish`, `harden`, `clarify`), **ui-ux-pro-max** (checklist), Emil's **break-ui**, **prototype**, **review-animations**, **animation-performance**, plus **accessibility-review** and **ux-copy**. **UI_GUIDE.md wins** over every design skill; conflicts become a proposed UI_GUIDE.md change (stop `DOC_CONFLICT` if it blocks the step).
  - Impeccable limits: never `live` mode, never install its hook, never `init`/`document`/`extract` (they write PRODUCT.md/DESIGN.md — UI_GUIDE.md is the only design doc), never start a "new design" flow that fetches the online catalog; telemetry stays off.
  - Glyphs and the block widget follow UI_GUIDE.md §4/§6; while §4 is marked *draft*, the glyph-set step is 👤 (Quan's taste decides).
- **Humanizer** — on human-facing prose before merge: README, docs site, first-launch guide, EN tooltip/help text, release notes, CHANGELOG entries, paper drafts. Never on METHODS.md formulas, error messages tied to codes, CLAUDE.md, TASKS.md, PR status lines or code comments.
- **testing-strategy, architecture, documentation** — QA, ADR and doc steps.
- **superpowers** — `test-driven-development` inside checkpoints for non-trivial logic only, `systematic-debugging` with §7, `verification-before-completion` before any DONE or "ready" claim. Its workflow never replaces §3: the plan goes in the handoff note, no `brainstorming` in phase mode (the step-runner can't ask questions; stop instead), worktrees only under `.claude/worktrees/`, never `finishing-a-development-branch` (merging is §14.2).
- **Not used:** gstack, the code-review plugin and `/review`, the `debug` and `deploy-checklist` skills (TOOLS.md §1 "Not used"). The gate still denies gstack's dangerous commands.
- GitHub work uses `gh` only (no GitHub MCP).
- **Precedence:** see the Precedence section at the top. Outside it, CLAUDE.md > TOOLS.md > any other plugin or skill text; a skill that says to commit, push, merge, deploy or ask questions in another way than §3/§14 is overruled.
These are development tools only: never app/engine dependencies (§4), never a reason to skip the docs. If one is missing, say so in the plan and continue without guessing (A1).

### 13.1 Visual check (every step that changes `app/`)
1. Start the dev app (`pnpm --dir app dev`); with Playwright CLI open each changed screen/state (empty, loading, normal, error, long JA/VI labels); save screenshots and attach them to the PR (not committed).
2. Run Impeccable `critique` and `audit` on the changed components, Emil `break-ui` on the changed views, and `accessibility-review` (WCAG 2.1 AA). Fix in-scope findings; list the rest in the PR.
3. If the step adds a user flow, add or extend an `@playwright/test` e2e test in `app/e2e/`.

### 13.2 Permission gate (allow or deny, never ask)
Every tool call goes through `scripts/permission_gate.py` (a PreToolUse hook in `.claude/settings.json`). It answers **allow** or **deny** and never asks Quan. Golden rule: **anything outside this project is denied.**
- **Allowed:** files in the repo (and its `.claude/worktrees/`, sibling `vibechem-*` worktrees), Claude's own folders (`~/.claude`, the `claude` temp/scratchpad folder, `~/.gstack`, `~/.bun`), `uv`/`pnpm`/`npx`, `gh` (PRs, issues, runs, read-only `gh api`), `git` (normal work, pushes to your own step branch), WebSearch/WebFetch, Context7, Claude Docs, `scripts/merge_step.py`.
- **Denied:** paths outside those folders; other MCP servers (Gmail, Calendar, Drive, GitHub MCP, …); pushes to `main`/existing `phase-*`, force pushes, `reset --hard`, `clean -f`, `rebase`, `branch -D`, global git config; `gh pr merge`, repo settings, secrets, label edits, writing `gh api` calls; `.env` files; machine-wide installs and system tools; downloads from unknown hosts; gstack's shipping/deploying commands (`FORBIDDEN_SKILLS` in the gate); edits to `.claude/settings*.json` or the gate itself.
- A deny is final: pick an allowed route or stop with the matching §14.3 code. Never work around it (e.g. by scripting the same action another way). If a deny is clearly a gate bug, add a failing case to `scripts/tests/test_permission_gate.py`, prepare the fix as a patch in the scratchpad and stop (`QUESTION`); Quan applies it (only he edits the gate or the settings).
- Quan can still run anything himself with the `!` prefix.

## 14. Phase mode
### 14.1 Session preflight (every session, every machine)
1. `git fetch --all --prune`. If the working tree has uncommitted changes → stop and ask Quan (never discard them).
2. Find the active phase: the lowest phase in TASKS.md "Run order" with unticked steps. Its branch `phase-<N>` exists? If not, create it from `main`: `git switch main && git pull && git switch -c phase-<N> && git push -u origin phase-<N>`.
3. `git switch phase-<N> && git pull`. If `main` has commits the phase branch lacks (e.g. Dependabot), open a small PR `[SYNC] main → phase-<N>` and merge it with `merge_step.py` first.
4. Sync environments when they exist: `uv sync` (if `uv.lock` exists), `pnpm --dir app install --frozen-lockfile` (if `app/pnpm-lock.yaml` exists).
5. Open PRs: a `paused` or `needs-quan` step PR in this phase is handled first (§8.3; for `needs-quan` check whether Quan answered in the PR comments or the chat — if not, report it and stop). An `in-progress` PR → ask Quan (§8.4).

### 14.2 Merging a step
`uv run python scripts/merge_step.py <pr>` (created in T0.02) refuses unless: base is `phase-*`; PR is not draft; all CI checks are green; the step is not 👤; title starts with `[T`, `[BUG` or `[SYNC]`. It squash-merges with the PR title as the commit message and deletes the step branch. Before the script exists (T0.01–T0.02), stop with `HUMAN_STEP` and ask Quan to merge.
After the merge, update the **phase PR** (`phase-<N> → main`, draft, title `[PHASE N] <name>`; open it after the first merged step): its description is the live dashboard — steps done, current step, open stops, link to PROGRESS.md on the phase branch. Edit it with `gh pr edit`.

### 14.3 Stop conditions (stop the step *and* the phase loop)
| Code | When | What Quan gets |
|---|---|---|
| `HUMAN_STEP` | A 👤 step: do Claude Code's part, mark the PR ready, don't merge | What to check / do, and "merge the PR, then `/phase N`" |
| `REUSE` | Any §12.5 condition | The options table and the recommended answer (drafted with `council`) |
| `ESTIMATE` | Work > 1.5× plan, or a split would change scope | Why, and a re-plan or split proposal (drafted with `council`) |
| `QUESTION` | An assumption that changes behaviour, results, defaults or the architecture; vague "Done when" (first try `intent-driven-development` to turn it into AC lines) | One short question with the recommended answer (drafted with `council`) |
| `DOC_CONFLICT` | Docs contradict each other or the code; a field/code/type is missing in DATA_MODEL/METHODS | The conflict and a proposed doc change |
| `CI_RED` | Checks still red after 2 fix attempts, or flaky | Failing job, cause found so far |
| `RED_FLAG` | A QA.md §4 red flag you can't avoid (tolerance, deleted test, golden regeneration, files outside step) | The reason and the recommended answer (drafted with `council`), for Quan to accept or reject; a `docs/RISKS.md` row |
| `S1_BUG` | Suspected silent wrong result or leakage, anywhere | Evidence (test, numbers); a `docs/RISKS.md` row |
| `MISSING_INPUT` | Dataset, pengoo file, credential, tool or account needed and absent | Exactly what is needed and where to put it |
| `DEPENDENCY` | The step depends on an unticked step | Which step |
| `CONTEXT` | §8.2 limits | Resume with `/resume` |
| `DESTRUCTIVE` | The step seems to need deleting data, rewriting history or changing settings/rulesets | What and why |
Never stop for something you can answer from the docs. Never continue past a stop by guessing.

### 14.4 Phase end
When only the phase-gate step is left: run it (it is 👤):
1. Prepare the gate report in PROGRESS.md "Phase gates": exit criteria with evidence, health summary on the phase branch, estimate-vs-actual per step, reuse ratio, ADRs to accept, QA.md §9.1 items for this phase, open issues.
2. Audits, each read by path from `.claude/skills/` or run as an agent: `ponytail-audit` (whole repo), `ponytail-debt` (`shortcut:` ledger), **mle-reviewer**, `production-audit` (from Phase 5), and the infrastructure checklist (QA.md §8, with cpp-reviewer / silent-failure-hunter). Findings go into `docs/RISKS.md`.
3. A `council` go/no-go note (≤ 5 lines) in the gate report.
4. Detail the next phase's steps in TASKS.md if they are only an outline, with `product-capability` (from PRD F-xx) and `intent-driven-development` (checkable "Done when" lines).
5. Merge that PR into the phase branch, mark the phase PR **ready**, and stop with `HUMAN_STEP`. Quan does the manual gate and merges the phase PR into `main` (merge commit). The next `/phase` starts the next phase in Run order.
