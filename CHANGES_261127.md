# /plan: CHANGES 2026-11-27 — lean context + model router + two repos

> Paste into a fresh Claude Code session in plan mode, in the **VibeChem-dev** clone. All decisions are made; propose the edits per part, then wait for Quan's approval. Workflow/tooling change, **not** a TASKS.md step.
> v1.1 · 2026-11-27 · Replaces `CHANGES.md` (two-repo only). Design reference for Part B: `docs/DEPLOYMENT_PLAN.md` v1.2 (added in B0). Where this file and DEPLOYMENT_PLAN.md differ on releases, DEPLOYMENT_PLAN.md wins.
> Three PRs, in order: **Part A** `[TOOLING] lean context: minimal CLAUDE.md, model router, quiet test output, lighter UI reviews` → **Part B-1** `[TOOLING] two repos: dev + release mirror` (B0–B3, B5–B7) → **Part B-2** `[TOOLING] shipped tree release-clean` (B4). All: branch from the **active phase branch** (`phase-2` at the time of writing), base the same branch; `merge_step.py` refuses `[TOOLING]`, so **Quan merges**. This file is an instruction file: never commit it.

## Changed vs v1
1. Base branch `phase-1` → active phase branch (`phase-2`).
2. No settings `ask` rules: they prompt even when the gate allows (Quan's rule: allow or deny only). Release-repo comment/close and `git tag` are **deny**; Claude drafts and gives Quan the exact `!` command.
3. The gate does not guard the release repo today (`gh release create`, `gh repo create/clone`, `gh workflow run`, `-R PengooNg/VibeChem` comments all pass). The "never touch the release repo" hard rule moves into Part A; the B7 gate patch must be applied before any release work.
4. A1 also rewrites the ~90 `CLAUDE.md §N` citations across the repo; `check_doc_refs.py` fails on any left over.
5. Part B split: B-2 cleans ~450 existing leak hits in shipped files; `export-check` becomes a required check only after B-2.
6. `.gitignore` adds `pengoo/` (today only in this machine's `.git/info/exclude`; the dev repo is public).
7. Router: `scripts/pick_model.py` decides the Opus rule deterministically instead of the main session reading prose.
8. `release.yml` does not exist in dev: it is new in `public/`, built from `installers.yml`.
9. Hook: `python "${CLAUDE_PROJECT_DIR}/…"` like the gate (not `uv run` on every Bash call); hooks run in parallel, so no "gate first" ordering; full `updatedInput`, no `permissionDecision`.
10. Datasets: both are published/CC0 → `public: true`, no `QUESTION`/`DESTRUCTIVE` stop.
11. Settings keys verified against the Claude Code docs (2026-11-27): `model`, `effortLevel` (low/medium/high/xhigh), `availableModels` valid in the project file; agent frontmatter `model` + `effort`; a project `Explore.md` overrides the built-in; the Agent tool `model` parameter beats the frontmatter, which beats `CLAUDE_CODE_SUBAGENT_MODEL`.

## Preconditions (check first; any fails → stop and tell Quan)
- `git remote get-url origin` → `PengooNg/VibeChem-dev`; `gh repo view --json visibility` → `PUBLIC` (DEPLOYMENT_PLAN §2 A2–A3 done). Checked 2026-11-27: OK; release repo `PengooNg/VibeChem` exists, public, empty.
- `[TOOLING] v0.5` (caveman, ponytail, ECC; K removed) is in the active phase branch. Work from the repo's **current** CLAUDE.md (v1.0+), not older copies.
- No step PR labelled `in-progress`.

## Decisions (final)
- **R1 Router.** Main session and default step model: **Sonnet, medium**. Hard steps: **Opus, medium** (Quan: medium is enough; never `high`/`xhigh`/`max` unless Quan asks). Light helpers: **Haiku, low**. Fable / `best` not used.
- **R2 Minimal CLAUDE.md.** ≤ 100 lines: identity, precedence summary, voice, models, a "where to find" map, hard rules, stop-code names, compact instructions. Everything else moves **verbatim** to `docs/rules/*.md`, `QA.md` or `TOOLS.md`, each referenced by path + heading so Claude Code always knows where to look. A check enforces that every reference resolves.
- **R3 Quiet test output.** A `PreToolUse` hook wraps known test/check commands so only failures, the health summary and the exit status reach context; the full log is saved to a file.
- **R4 Lighter UI reviews.** Impeccable critique/audit, break-ui and accessibility-review run only on 👁 steps and at phase gates. Other `app/` steps: Playwright screenshots + e2e test for new flows.
- **R5 No prompts.** Permission rules are allow or deny only; no settings `ask` rules. Anything Quan must approve is drafted by Claude and run by Quan with `!`.
- **E1–E7** (two repos) as in Part B. **E8:** the dev repo is public while active, private only when static (DEPLOYMENT_PLAN §2.1); nothing sensitive is ever committed to it (DEPLOYMENT_PLAN §1 rule 5).
- Precedence: R1–R5 and E1–E8 join item 2 of the precedence list (Quan's decisions). The hook, router rule, publish workflow, manifest, leak rules and deploy key join item 1 (fixed mechanics).

---

# Part A — lean context

## A1: split CLAUDE.md (move, don't rewrite)
Create these files; move text **verbatim** (only headings and cross-reference wording may change). Each file starts with a one-line "Read this when …" so a skill knows when to load it.

| New home | Gets (from current CLAUDE.md) | Read by |
|---|---|---|
| `docs/rules/PRECEDENCE.md` | Full precedence section + the v0.5 conflict table + D1–D6 | Anyone resolving a rule conflict |
| `docs/rules/WORKFLOW.md` | §3 how a step runs · §8 status line, safe stops, handoff template, resuming, two machines, `/status` answer · §9 commands · §14 preflight, merging, **full stop-conditions table**, phase end | phase, step, resume, status skills; step-runner |
| `docs/rules/CODING.md` | Part A A1 + A4 (A2/A3 are already "apply ponytail") · §5 block template pointer + comment rules · §12 reuse ladder, judging, decide, estimate, `REUSE` triggers | step-runner, bug skill |
| `docs/rules/MODELS.md` | New, from A2 below | phase, step, resume, bug skills |
| `docs/QA.md` (new §"Per-step duties" and §"Bug protocol") | §6 quality duties · §7 bug protocol · §10 reviews. Delete any older duplicate text in QA.md so each rule exists **once** | step-runner, bug skill |
| `docs/TOOLS.md` | §13 skills/plugins/tools + §13.1 visual check (rewritten per A4) | step-runner (its §3 row), phase gate |
| `.claude/skills/block-template/SKILL.md` | The SNV example block (if not already there) | block steps |

**New `CLAUDE.md` (≤ 100 lines), in this order:**
1. *What VibeChem is* — 2 lines. *Two repos* — 2 lines + "→ `docs/DEPLOYMENT_PLAN.md`" (Part B adds this).
2. *Precedence* — 4 numbered lines (fixed mechanics → Quan's decisions → caveman/ponytail/ECC → everything else) + "→ `docs/rules/PRECEDENCE.md`".
3. *Voice* — 2 lines (caveman for chat/PR text only; never inside files).
4. *Models* — 3 lines + "→ `docs/rules/MODELS.md`".
5. *Where to find things* — one table, situation → file#heading:

   | When you … | Read |
   |---|---|
   | start any session | `docs/rules/WORKFLOW.md#session-preflight` |
   | run or resume a step | `docs/rules/WORKFLOW.md#how-a-step-runs`, `#resuming` |
   | must stop / hand off | `docs/rules/WORKFLOW.md#stop-conditions`, `#handoff-note` |
   | plan or write code | `docs/rules/CODING.md`, then the step's row in `docs/TOOLS.md#step-map` |
   | finish a step / merge | `docs/QA.md#per-step-duties`, `docs/rules/WORKFLOW.md#merging-a-step` |
   | fix a bug | `docs/QA.md#bug-protocol` |
   | pick a model / spawn a subagent | `docs/rules/MODELS.md` |
   | hit a rule conflict | `docs/rules/PRECEDENCE.md` |
   | release, patch, outside PR, release-repo issue | `docs/DEPLOYMENT_PLAN.md` (Part B) |
   | need fields, codes, formats | `docs/DATA_MODEL.md` |
   | need algorithm definitions | `docs/METHODS.md` |
   | need versions, layout, commands, CI | `docs/TECH_STACK.md` |
   | need UI rules | `docs/UI_GUIDE.md` |
   | phase gate | `docs/rules/WORKFLOW.md#phase-end`, `docs/QA.md#phase-gate` |

6. *Hard rules* — the §4 "Never do" list condensed to one line per rule (same rules, no examples). These stay in CLAUDE.md because they must apply even when nothing else is loaded. Add now (Part A, not B5): "Never push to, comment on, close anything in, tag, release or run workflows on `PengooNg/VibeChem` (the release repo); read-only `gh … list/view/diff -R PengooNg/VibeChem` only."
7. *Stop codes* — names only, one line, + "→ `docs/rules/WORKFLOW.md#stop-conditions`".
8. *Compact instructions* — "When compacting, keep: current step ID, branch, PR, checkpoint, failing tests, decisions made, open questions. Drop file dumps and passing test output."

**Make skills and agents load what they need.** Add a `Read first:` line at the top of each: `phase`, `step`, `resume`, `status`, `bug`, `block-template`, `step-runner.md`, listing exact `file#heading` targets from the table. No skill may rely on text that is no longer in CLAUDE.md without such a line.

**Rewrite old citations.** About 90 `CLAUDE.md §N` citations exist outside CLAUDE.md (TASKS 16, permission_gate.py 11, TOOLS 10, TECH_STACK 9, QA 7, step-runner 6, PROGRESS 5, PR template 4, RISKS 3, ARCHITECTURE 3, skills bug/step/resume/phase/block-template, METHODS 2, FUNCTION_CATALOG, THIRD_PARTY, CODEOWNERS, app/README, `vibechem_core/block.py`, `vibechem_engine/api/app.py`). Rewrite each to the new `file#heading` (`git grep -n "CLAUDE\.md ?§"` lists them). In the two shipped `.py` files point to `docs/METHODS.md` or drop the reference (they must be release-clean anyway). `scripts/permission_gate.py` and `scripts/merge_step.py` are Quan-only → their message text goes in the A5 patch.

**Reference check.** `scripts/check_doc_refs.py`: every `docs/...md#anchor` and `.claude/...` path in CLAUDE.md, docs, skills and agents exists (file + heading anchor, GitHub slug rules); no `CLAUDE.md §` citation is left anywhere (except this instruction file, which is not committed); CLAUDE.md ≤ 100 lines (335 today). Add as `check.py` area `docs` (part of `--fast`). One small test.

**PR evidence:** a mapping table *old CLAUDE.md section → new file#heading* covering every section; `diff` showing moved text is unchanged apart from headings.

## A2: model router
**`docs/rules/MODELS.md`:**

| Role | Model | Effort |
|---|---|---|
| Main session / phase runner | `sonnet` (interactive planning with Quan: `/model opusplan`) | medium |
| step-runner, default | `sonnet` | medium |
| step-runner, **Opus rule** (below) | `opus` | medium |
| `Explore` (overrides built-in), `scribe` | `haiku` | low |
| silent-failure-hunter, cpp-reviewer | `sonnet` | medium |
| mle-reviewer, phase-gate step | `opus` | medium |
| Fable, `best` | never | — |

**Opus rule** — the phase runner (and `/step`, `/resume`, `/bug`) runs `uv run python scripts/pick_model.py <step-id> [--after <STOP_CODE>]`, which prints `opus (rule <n>)` or `sonnet`, and passes that alias as `model:` to the step-runner. Rules 1–3 are checked by the script; rule 4 by the `--after` flag:
1. The step heading in TASKS.md matches `Size [ML]\b` (headings can read `Size L → split into …`) or carries the tag `⚑opus`.
2. The step's file list touches `packages/native/**`, `packages/engine/src/vibechem_engine/{scheduler,executor,compiler,cache}/**`, `packages/core/src/vibechem_core/blocks/{validate,split,select,transfer}/**`, `packages/core/src/vibechem_core/metrics.py`, or `docs/METHODS.md`.
3. It is the phase-gate step, or a resume after `S1_BUG`.
4. **Escalation:** a Sonnet step-runner stopped with `CI_RED`, `ESTIMATE` or a failed reference test → re-run that step **once** with Opus (resume from the handoff note). A second failure stops as usual.

Record the model in the step-runner DONE block (`Model: sonnet|opus (rule n)`) and add a `Model` column to the PROGRESS.md Step log, so Quan can tune the rule from real data.

**Files:**
- `scripts/pick_model.py` (stdlib only): reads the step block in `docs/TASKS.md` (heading + `Files` line), applies rules 1–3, `--after CI_RED|ESTIMATE|REF_FAIL|S1_BUG` applies rules 3–4. One small test (an S step on plain paths → sonnet; a `Size L → split` heading → opus rule 1; an S step touching `scheduler/` → opus rule 2).
- `.claude/agents/step-runner.md`: remove the `model: inherit` line (the caller decides; the Agent tool `model` parameter beats the frontmatter anyway); `effort: medium`.
- `.claude/agents/Explore.md` (new): `model: haiku`, `effort: low`, read-only tools (Read, Grep, Glob, Bash read-only). Same purpose text as the built-in.
- `.claude/agents/scribe.md` (new): `model: haiku`, `effort: low`. Jobs: `/status` reports, PROGRESS/TASKS tick edits, summarising long logs, running export/leak checks and reporting results. Never writes code.
- `.claude/agents/{silent-failure-hunter,cpp-reviewer}.md`: `model: sonnet`, `effort: medium`. `mle-reviewer.md`: `model: opus`, `effort: medium`.
- Skills `phase`, `step`, `resume`, `bug`: run `scripts/pick_model.py` and pass its alias when spawning the step-runner; print it in the `▶` line (`▶ T<x> <title> (size <S/M>, <model>)`); `status` delegates to `scribe`.
- `CLAUDE_CODE_SUBAGENT_MODEL` is only the fallback for agents without a `model:` line (Plan, general-purpose); it ranks below the frontmatter.
- `docs/TASKS.md`: add `⚑opus` to headings of open steps that rule 2 would match only partly or that you judge hard; list them in the PR for Quan to accept. No other heading changes.

## A3: quiet test output (hook)
- `.claude/hooks/quiet_tests.py` (stdlib only, works on Windows): reads the hook JSON from stdin. If `tool_input.command` **exactly** matches one of these shapes, with no shell metacharacters (`;&|<>$\`` or newlines): `uv run pytest …`, `uv run python scripts/check.py …`, `pnpm --dir app test …`, `pnpm --dir app e2e …`, `pnpm --dir app lint …` → return `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {…}}}` with the **full** tool input (`updatedInput` replaces the whole object: keep `description`, `timeout`, `run_in_background`) and only `command` replaced by `uv run --no-project python .claude/hooks/run_quiet.py -- <original command>`. No `permissionDecision` (the gate's decision stands). Otherwise print nothing and exit 0. Matching hooks run in parallel: the gate checks the original command; the wrapper's allowlist is the guard for the rewritten one.
- `.claude/hooks/run_quiet.py`: re-checks the same allowlist (refuses anything else), runs the command, saves full output to `.cache/test-logs/<timestamp>.log` and `.cache/test-logs/latest.log`, prints: failure blocks (`FAILED`, `ERROR`, `Traceback`, `FAIL`, `✗` with 5 lines of context, max 150 lines), the `check.py` health-summary block verbatim, a final `exit=<code> · full log: .cache/test-logs/latest.log`, and **exits with the original exit code**.
- `scripts/check.py`: print the health summary between `=== HEALTH SUMMARY ===` and `=== END HEALTH SUMMARY ===` (no other change).
- `.gitignore`: `.cache/` and `pengoo/` (pengoo sources are today ignored only by this machine's `.git/info/exclude`; the dev repo is public — DEPLOYMENT_PLAN §1 rule 5).
- Rule text (in `docs/rules/WORKFLOW.md#commands`): "Test and check output is shortened by a hook. If you need the full output, read `.cache/test-logs/latest.log` — don't re-run with pipes."
- Tests: one for `quiet_tests.py` (match / no match / metacharacter rejected), one for `run_quiet.py` (exit code preserved, failure lines kept).
- Hook registration is in `.claude/settings.json` (Quan-only) → patch in A5.

## A4: lighter UI reviews
- `docs/TOOLS.md` §13.1 → **Visual check by step type:**
  - `app/` step **without 👁**: start the dev app, Playwright CLI screenshots of changed screens (normal + error state), attach to the PR; add/extend an `@playwright/test` e2e test if the step adds a user flow. No Impeccable, break-ui or accessibility-review.
  - **👁 step:** the full set as before (all states incl. long JA/VI labels, Impeccable `critique` + `audit`, Emil `break-ui`, `accessibility-review`).
  - **Phase gate:** one Impeccable `audit` + `accessibility-review` over every screen changed in the phase; findings → RISKS.md or new steps.
- Update the TOOLS.md §3 step map and the QA.md per-step duties to match. Any non-👁 step that changes layout, tokens or a shared component should have been 👁: list such open steps in the PR for Quan.

## A5: Quan-only patch (scratchpad; attach to PR; don't apply)
`.claude/settings.json`:
```json
{
  "model": "sonnet",
  "effortLevel": "medium",
  "env": { "CLAUDE_CODE_SUBAGENT_MODEL": "sonnet" },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash",
        "hooks": [ { "type": "command",
                     "command": "python \"${CLAUDE_PROJECT_DIR}/.claude/hooks/quiet_tests.py\"",
                     "timeout": 10 } ] }
    ]
  }
}
```
Merge into the existing file (keep permissions and the permission-gate hook entry unchanged; hooks run in parallel, order does not matter). No extra allow rule is needed: `Bash(uv *)` already covers the wrapper. Keys checked against the Claude Code docs on 2026-11-27 (`model`, `effortLevel`, `env`, `availableModels`, PreToolUse `updatedInput`); re-check only if Claude Code warns about a key at start. Optionally restrict selectable models to sonnet/opus/haiku/opusplan with `availableModels`.
Also in this patch: the `CLAUDE.md §N` citations in the message strings of `scripts/permission_gate.py` (11) and `scripts/merge_step.py` (1) → new `file#heading`.
Test with the gate tests that a denied command can't pass through the wrapper (the wrapper's allowlist is the guard).

## A6: verify
- `check.py --fast` all PASS incl. `docs`; CLAUDE.md ≤ 100 lines; mapping table complete.
- Smoke (Quan, new session after the patch): "where are we?" → answered via `scribe`; `/step <next-ID> wait` → plan shows the chosen model and why, reads only the listed rule sections; a failing test run shows the short output and the log path.

---

# Part B — two repos (start after Part A is merged)
PR B-1 = B0–B3, B5–B7. PR B-2 = B4 (starts after B-1 is merged). Until B-2 is merged, `export-check` runs on PRs but is **not** a required check (it is red on today's tree).

## B0: plan doc
Move the root `DEPLOYMENT_PLAN.md` to `docs/DEPLOYMENT_PLAN.md` unchanged (v1.2).

## B1: export tooling (ponytail; one small test each)
- `release/public-manifest.toml`: `include`, `exclude`, `overlay = "public"`, `datasets = "testdata/datasets/PROVENANCE.md"` — contents per DEPLOYMENT_PLAN §3.
- `release/leak-rules.toml`: `forbidden_paths`, `forbidden_patterns` (DEPLOYMENT_PLAN §4), `[[allow]]` (`path`, `pattern`, `reason`) for identity files only.
- `scripts/release/export_public.py --ref <git-ref> --out <dir> [--dry-run]`: reads the tree at the ref (never the working tree), applies include → exclude → dataset filter → overlay, writes `<dir>`, prints the sorted file list. Deterministic. Non-zero on a missing overlay file or unknown dataset flag.
- `scripts/release/leak_check.py <dir>`: prints `path:line: pattern` per hit; non-zero on any hit not covered by `[[allow]]`.
- Tests in `scripts/release/tests/`. `check.py` area `export` (export `HEAD` to a temp dir + leak check), part of `--fast`; `check.py` skips dev-only parts cleanly when their files are absent.

## B2: release overlay `public/` (Humanizer on prose)
`README.md` (what it is, install from Releases, quick start, docs, how to cite, licence, `Copyright (C) 2026 Nguyen Minh Quan and VibeChem contributors`; no link to -dev) · `CONTRIBUTING.md` (public commands, tests, import flow per DEPLOYMENT_PLAN §6, DCO, GPL inbound) · `SECURITY.md` · `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 verbatim) · `.gitignore` (no tool lines) · `.github/workflows/ci.yml` (PR + push to main; release build test on 3 OS) · `.github/workflows/release.yml` (**new**; dev has no `release.yml` — build it from dev `installers.yml`, which stays in dev for skeleton CI) · `.github/ISSUE_TEMPLATE/{bug.yml,feature.yml,config.yml}` · `.github/PULL_REQUEST_TEMPLATE.md` (merged upstream, credited in the next release).

## B3: dev workflows and dev README
- `.github/workflows/publish-public.yml` exactly per DEPLOYMENT_PLAN §5.3 (`PUBLIC_DEPLOY_KEY`; `permissions: contents: read`; `gitleaks/gitleaks-action` pinned by SHA; `dry_run` default `true`).
- `ci.yml`: job `export-check` (export `HEAD` + leak check + gitleaks) on PRs to `main`/`phase-*`; note in the PR that Quan adds it to required checks **after B-2 is merged**. `check.py` area `export` reports but does not fail `--fast` until B-2 (flip it to failing in B-2).
- `nightly.yml`: unchanged, but document in DEPLOYMENT_PLAN §2.1 that Quan disables it when static.
- Dev root `README.md` (3 lines): "Development repository of VibeChem. Releases, docs and issues: https://github.com/PengooNg/VibeChem." (The overlay README replaces it in the export.)

## B4 (PR B-2): shipped tree public-clean + private data out (comments, docstrings, metadata only; no logic)
- Size: on 2026-11-27 the shipped paths had ~222 dev-doc references, 126 step IDs, 44 `Quan`, 24 `ADR-`/`D-` ids, 16 `claude`, 12 `Reviewer:` lines. Size L → split into checkpoints per package (core, engine, app, docs/metadata).
- Run export + leak check on `HEAD`; fix every hit: block headers drop the `Reviewer:` line, `Implementation:` without dev-doc references (E6; also in `block-template`); comments pointing to dev-only docs → `docs/METHODS.md` or removed; METHODS.md / references.bib without step IDs or review notes.
- Split `THIRD_PARTY.md` → shipped items stay; `.claude/` content (caveman, ponytail, ECC, Impeccable, ui-ux-pro-max, Emil's skills …) → `THIRD_PARTY_DEV.md`.
- `CITATION.cff`: `repository-code: "https://github.com/PengooNg/VibeChem"`; drop the commented co-author line; author details unchanged (provisional). `[project.urls]` and any Electron update/publish config → `PengooNg/VibeChem`.
- **Private data (rule 5):** `PROVENANCE.md` gets `public: true|false` per dataset. Checked 2026-11-27: `gasoline_nir` (published, Kalivas 1997), `olive_oil_ftir` (CC0-1.0) and `expected/r_pls_reference.json` (R `pls` public data) are all `public: true` — no stop needed. Only a dataset added later that is unpublished gets `false`: then stop `QUESTION`; if it is already in the tree, stop `DESTRUCTIVE`. Tests needing `false` datasets read from `$VIBECHEM_PRIVATE_DATA`, get `@pytest.mark.private_data`, skip when absent (register the marker; say in the PR this adds a skip condition only, no tolerance or golden change). `.gitignore`: `testdata/private/`.
- `CHANGELOG.md`: existing entries reworded user-facing.

## B5: rules (into the Part A files; CLAUDE.md stays ≤ 100 lines)
- `CLAUDE.md`: "Two repos" 2 lines (§1 of the new layout); hard rules add one line each (the release-repo line is already there from Part A): never create/push tags or releases or run/enable/disable workflows; never write tool names, model names, step IDs, stop codes, process notes or dev-doc references into shipped files; never commit secrets, unpublished data or personal data (dev repo is public); never edit the manifest `include` list or leak `[[allow]]` (→ `PUBLIC_SCOPE`). Stop-code list adds `PUBLIC_SCOPE`, `REPO_PRIVATE`. Where-to-find table: release row (already there).
- `docs/rules/WORKFLOW.md`: session preflight step 0: `gh repo view PengooNg/VibeChem-dev --json visibility` → if `PRIVATE`, stop `REPO_PRIVATE` ("Dev repo is private: rulesets not enforced and CI minutes metered. Make it public (DEPLOYMENT_PLAN §2.1) or confirm you are on GitHub Pro."). Stop table adds `PUBLIC_SCOPE` (a step needs a new shipped top-level path, a manifest/allow change, or a dataset marked public → Quan gets the paths and why) and `REPO_PRIVATE`. Branches: `release-*`, `hotfix-*`, `ext-*`; tags only on `main`, only by Quan.
- `docs/QA.md`: per-step duties add "export-check PASS"; gate checklist adds "export dry-run reviewed"; release checklist → DEPLOYMENT_PLAN §8; bug protocol: `/bug public#<n>`, fix commits carry `Public-Issue: <n>`.
- `docs/TECH_STACK.md`: §3 layout adds `docs/rules/`, `scripts/pick_model.py`, `scripts/check_doc_refs.py`, `public/`, `release/`, `scripts/release/`, `.claude/hooks/`, `THIRD_PARTY_DEV.md`, `docs/DEPLOYMENT_PLAN.md`; §8 workflows split dev / release (release.yml moved, publish-public, export-check); §13 CITATION URL, THIRD_PARTY split; developer setup adds `VIBECHEM_PRIVATE_DATA`.
- `docs/TOOLS.md`: `/release`, `/import-pr`, `scribe`, gitleaks (CI only).
- `docs/TASKS.md`: steps that mention installers, GitHub Release, Zenodo or the Beta/v1 release get one line "Publishing: see DEPLOYMENT_PLAN.md". No scope change.
- `docs/RISKS.md`: rows from DEPLOYMENT_PLAN §9.
- Dev PR template: checkbox "Shipped files release-clean (export-check PASS)"; title prefixes `[RELEASE]`, `[HOTFIX]`, `[EXT #n]`. Dev `CONTRIBUTING.md` → 3-line pointer to the release repo.
- `docs/PROGRESS.md`: Step-log rows for Part A and Part B.

## B6: skills
- `.claude/skills/release/SKILL.md` — `/release <version> [--hotfix <tag>]`: DEPLOYMENT_PLAN §5.2; ends `HUMAN_STEP` with the exact tag command for Quan. Model: sonnet.
- `.claude/skills/import-pr/SKILL.md` — `/import-pr <n>`: DEPLOYMENT_PLAN §6 steps 1–6; drafts the reply and gives Quan the exact `! gh pr comment <n> -R PengooNg/VibeChem --body-file …` and `! gh pr close …` commands; never posts itself (denied). Model: sonnet (opus if the diff touches an Opus-rule path).
- `/bug`: accepts `public#<n>`. `/status` (via `scribe`): adds "Release repo: last release, open issues, open PRs" and "Dev repo visibility".

## B7: Quan-only patches (scratchpad; attach; don't apply). **Apply before any release work** — today the gate lets `gh release create`, `gh repo create/clone`, `gh workflow run` and release-repo comments through, and `settings.local.json` allows `Bash(gh repo *)` (Quan: remove that line).
- `.claude/settings.json` (on top of A5). No `ask` rules (R5): the former ask list is in deny.
  - allow: `Bash(gh repo view PengooNg/VibeChem-dev --json visibility*)`, `Bash(gh issue list -R PengooNg/VibeChem *)`, `Bash(gh issue view * -R PengooNg/VibeChem*)`, `Bash(gh pr list -R PengooNg/VibeChem *)`, `Bash(gh pr view * -R PengooNg/VibeChem *)`, `Bash(gh pr diff * -R PengooNg/VibeChem*)`, `Bash(gh release list -R PengooNg/VibeChem*)`, `Bash(gh release view * -R PengooNg/VibeChem*)`, `Bash(uv run python scripts/release/export_public.py *)`, `Bash(uv run python scripts/release/leak_check.py *)`
  - deny: `Bash(gh issue comment * -R PengooNg/VibeChem *)`, `Bash(gh pr comment * -R PengooNg/VibeChem *)`, `Bash(gh pr close * -R PengooNg/VibeChem*)`, `Bash(gh issue close * -R PengooNg/VibeChem*)`, `Bash(git tag *)`, `Bash(git remote add *)`, `Bash(git remote set-url *)`, `Bash(git push *PengooNg/VibeChem.git*)`, `Bash(git push --tags*)`, `Bash(git push origin v*)`, `Bash(git push * refs/tags/*)`, `Bash(git tag -d *)`, `Bash(gh repo create *)`, `Bash(gh repo clone *)`, `Bash(gh release create *)`, `Bash(gh release edit *)`, `Bash(gh release delete *)`, `Bash(gh release upload *)`, `Bash(gh workflow *)`, `Edit(release/public-manifest.toml)`, `Edit(release/leak-rules.toml)`, `Edit(.github/workflows/publish-public.yml)`, `Edit(.claude/hooks/*)`
  - Show with the gate tests that `-R PengooNg/VibeChem` rules don't match `PengooNg/VibeChem-dev`.
- `scripts/permission_gate.py` + test: mirror the deny rules (also `--repo` and URL forms). `check_gh` today denies only `release delete`; add: any write `gh` subcommand (`comment`, `close`, `create`, `edit`, `merge`, `review`, `reopen`) whose `-R`/`--repo` resolves to `PengooNg/VibeChem` (exact, not `-dev`), `gh repo create/clone`, `gh release create/edit/upload`, `gh workflow *`, `git tag`.
- `scripts/merge_step.py` + test: accept the `[EXT` prefix; `[RELEASE]`, `[HOTFIX]`, `[TOOLING]` stay Quan-merged.

## B8: verify (report only)
- `check.py --fast` all PASS (incl. `docs`, `export`); `uv run pytest scripts/release/tests` PASS; gate + merge_step tests PASS with patches applied in a temp copy.
- Export of `HEAD`: sorted file list as a PR comment; release build test passes inside it with no dev-only file present.
- `leak_check` clean; `grep -rniE "claude|anthropic|caveman|ponytail|vibecod|opus|sonnet|haiku" <export>` → nothing outside allow entries.
- Every skill/agent/file#heading named in CLAUDE.md, skills, agents and TOOLS.md exists (the `docs` check).

## After merge (Quan)
1. Apply A5 and B7 patches; run the gate tests; start a new session (settings and hooks load at start).
2. After B-2 is merged: add `export-check` to required checks on `main` and `phase-*`.
3. Finish DEPLOYMENT_PLAN §2 A4–A11.

## Out of scope
Algorithms, TASKS.md scope (beyond `⚑opus` tags and publishing pointers), UI_GUIDE.md · user guide (Phase 7) · PyPI · docs website · rewriting old history.

## Stop and ask Quan if
- Moving a CLAUDE.md section would change its meaning, or two sections contradict once side by side.
- A leak-check hit can only be fixed by changing logic, a tolerance or a golden file.
- A shipped file depends on a dev-only file in a way that can't be skipped cleanly.
- A dataset's public status is unclear, or private data is already in the tree.
- A documented settings key differs from this plan in a way that changes behaviour.
- Any rule here would break a fixed mechanic from v0.5.
