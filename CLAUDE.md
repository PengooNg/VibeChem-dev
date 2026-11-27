# CLAUDE.md — rules for working on VibeChem

> v1.1 · 2026-11-27 · Minimal by design (≤ 100 lines, checked by `scripts/check_doc_refs.py`). The full rules live in the files named below; each starts with "Read this when …". Old section numbers (§1–§14) are gone: cite `file#heading` instead.

## What VibeChem is
A free, open-source (GPL-3.0-or-later) desktop app for chemometrics on vibrational and hyperspectral spectra: Python engine and blocks, C++20 kernels, React/TypeScript UI, Electron shell.
Built mostly by AI; owner and only human reviewer: **Quan**.

## Precedence
1. **Fixed mechanics** (no text changes them): `scripts/permission_gate.py` + the deny list in `.claude/settings.json`, `scripts/merge_step.py` checks, branch protection, checkpoint prefix `T<x> cpN:`, the quiet-test hook and the model router script.
2. **Quan's decisions**: D1–D6 (tooling v0.5) and R1–R5 (2026-11-27: router, minimal CLAUDE.md, quiet test output, lighter UI reviews, no permission prompts).
3. **caveman, ponytail, ECC** (`.claude/skills/`, `.claude/agents/`).
4. Everything else: this file, the rule files, TOOLS.md, QA.md, the other docs, the other skills.
Details, the conflict table and D1–D6: docs/rules/PRECEDENCE.md.

## Voice
caveman for chat with Quan and PR narrative sections only; fixed formats (`▶`/`✓` lines, DONE/STOP blocks, "Stopping safely: <reason>.", Status lines) stay verbatim; questions to Quan in full sentences.
Never caveman inside files (code, comments, docstrings, commits, docs, handoff notes). Full rule: docs/rules/PRECEDENCE.md#voice.

## Models
Main session and default step-runner: `sonnet`, effort medium. Hard steps: `opus`, effort medium, chosen by `uv run python scripts/pick_model.py <step-id>`.
Light helpers (`Explore`, `scribe`): `haiku`, effort low. Never Fable or `best`; never effort high/xhigh/max unless Quan asks.
Details and the Opus rule: docs/rules/MODELS.md.

## Where to find things
| When you … | Read |
|---|---|
| start any session | docs/rules/WORKFLOW.md#session-preflight |
| run or resume a step | docs/rules/WORKFLOW.md#how-a-step-runs, docs/rules/WORKFLOW.md#resuming |
| must stop / hand off | docs/rules/WORKFLOW.md#stop-conditions, docs/rules/WORKFLOW.md#stop-safely-never-mid-section |
| plan or write code | docs/rules/CODING.md, then the step's row in docs/TOOLS.md#3-step-map |
| write or review a block | the `block-template` skill, docs/rules/CODING.md#block-template-and-comment-style |
| finish a step / merge | docs/QA.md#7-per-step-duties, docs/rules/WORKFLOW.md#merging-a-step |
| fix a bug | docs/QA.md#6-bug-protocol |
| pick a model / spawn a subagent | docs/rules/MODELS.md |
| hit a rule conflict | docs/rules/PRECEDENCE.md |
| use a skill, plugin or MCP tool; permission gate | docs/TOOLS.md#5-rules-for-the-tools, docs/TOOLS.md#52-permission-gate |
| need test/check commands | docs/rules/WORKFLOW.md#commands |
| need the step itself, run order | `docs/TASKS.md` |
| need what happened so far, open stops | `docs/PROGRESS.md` |
| need open risks, audit findings | `docs/RISKS.md` |
| need product features (F-xx) | `docs/PRD.md`, `docs/FUNCTION_CATALOG.md` |
| need design decisions, ADRs | `docs/ARCHITECTURE.md` |
| need fields, codes, formats | `docs/DATA_MODEL.md` |
| need algorithm definitions | `docs/METHODS.md` |
| need versions, layout, commands, CI, reuse register | `docs/TECH_STACK.md` |
| need UI rules | `docs/UI_GUIDE.md` |
| phase gate | docs/rules/WORKFLOW.md#phase-end, docs/QA.md#91-phase-gate |
Before editing a package, also read that package's `README.md`. Read only what the step tells you.

## Hard rules
These apply even when nothing else is loaded.
- Never invent API fields, file-format fields, error codes or port types: use `docs/DATA_MODEL.md`; propose additions there first.
- Never add a dependency not in `docs/TECH_STACK.md` §1 or approved from its reuse register (§11).
- Never build from scratch what the reuse register or the reuse ladder shows already exists, without Quan's explicit approval.
- Never copy code unless its licence is GPL-3.0-compatible; ported code keeps its copyright, gets a source header and a `THIRD_PARTY.md` row.
- Never trust an external library's numbers blindly: reused algorithms get reference tests against independent values.
- Never use pickle (or `allow_pickle=True`) for anything saved or shared.
- Never loosen a test tolerance, delete/skip a test or regenerate golden files without saying so in the PR (phase mode: stop `RED_FLAG`).
- Never bypass the block contract (`vibechem_core/block.py`) or import across forbidden package boundaries (TECH_STACK.md §3.1).
- Never fit anything on validation/test data; fitted steps `fit` on training rows only.
- Never use global random state; accept a `numpy.random.Generator`.
- Never hard-code user-visible text; use i18n keys (EN/JA/VI).
- Never make network calls from the app or engine (except the update check in the Electron main process).
- Never introduce a new architectural pattern without an ADR in `docs/ARCHITECTURE.md` §7.
- Never stop mid-edit: no half-written file, no uncommitted branch.
- Never commit tokens or secrets; credentials come from environment variables only.
- Never merge into, push to or force-push `main` or `phase-*`, rewrite history, delete branches other than your own merged step branch, or change repository settings, rulesets or label meanings. Step PRs merge only via `scripts/merge_step.py`; `phase-N → main` is Quan's.
- Never merge a step marked 👤: prepare it and stop `HUMAN_STEP`.
- Never push to, comment on, close anything in, tag, release or run workflows on `PengooNg/VibeChem` (the release repo); read-only `gh … list/view/diff -R PengooNg/VibeChem` only.
- Permission rules are allow or deny only: a deny is final; never work around it. Anything Quan must run, give him as an exact `!` command.

## Stop codes
`HUMAN_STEP` · `REUSE` · `ESTIMATE` · `QUESTION` · `DOC_CONFLICT` · `CI_RED` · `RED_FLAG` · `S1_BUG` · `MISSING_INPUT` · `DEPENDENCY` · `CONTEXT` · `DESTRUCTIVE`.
When to use each and what Quan gets: docs/rules/WORKFLOW.md#stop-conditions. When unsure, stop and ask one short question (docs/rules/CODING.md#when-unsure).

## Compact instructions
When compacting, keep: current step ID, branch, PR, checkpoint, failing tests, decisions made, open questions. Drop file dumps and passing test output.
Test and check output is shortened by a hook; the full log is `.cache/test-logs/latest.log` (don't re-run with pipes).
