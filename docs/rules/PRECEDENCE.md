# Precedence, Quan's decisions and voice

> Read this when two rules seem to conflict, or to check what a decision (D1–D6) or the voice rule says exactly.
> Moved verbatim from the old CLAUDE.md (v1.0) on 2026-11-27. Part A of the old CLAUDE.md was adapted from the four principles in `multica-ai/andrej-karpathy-skills` (MIT), based on Andrej Karpathy's observations of common LLM coding mistakes.

## Precedence
Where rules conflict, the higher item wins. Where nothing conflicts, every rule below still applies unchanged.
1. **Fixed mechanics** — no text can change these:
   - `scripts/permission_gate.py` and the deny list in `.claude/settings.json` (Quan-only files, docs/TOOLS.md#52-permission-gate).
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
| Reuse order (docs/rules/CODING.md#reuse-first-and-estimate-before-committing) | Our repo → stack libraries → new packages → port → build; a full estimate table for every plan | **ponytail ladder** (docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.1)). A new dependency only when our minimum code would be large, never "for a few lines". The docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.4) estimate table only for M/L steps. The `REUSE` stop for M+ stays; ECC `council` drafts the recommended answer. Licence rules (docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.2)) unchanged |
| Part A, A2 and A3 | Own text | "Apply the `ponytail` skill (full)." A1 and A4 stay |
| Diff review | code-review plugin, gstack `/review` second opinion | **ponytail-review is the gate.** `/security-review` stays on 🔒 steps. ECC agents per area (TOOLS.md §3) |
| Bug fixing | docs/QA.md#6-bug-protocol order + `debug` skill + superpowers | docs/QA.md#6-bug-protocol order stays, **plus ponytail's bug rule:** grep every caller of the touched function and fix the root cause once in the shared code |
| PR text | Plain prose (caveman's own rule 5 also says plain) | **caveman voice in the narrative sections** (D2 beats the upstream rule). Template headings, Status line, health summary, code, paths and commands stay exact. Questions to Quan in full sentences |
| Talking to Quan | Report formats, superpowers announcing skills | **caveman.** Fixed formats are payload and stay verbatim: `▶`/`✓` lines, DONE/STOP blocks, "Stopping safely: <reason>.". No skill-use announcements |
| Planning and stops | The phase runner prints the stop as it is | ECC `council` drafts the "recommended answer" (≤ 5 lines) for `REUSE` / `ESTIMATE` / `QUESTION` / `RED_FLAG` stops. ECC `intent-driven-development` rewrites a vague "Done when" into AC lines. `product-capability` details the next phase from PRD F-xx (PRD.md is its product-context file) |
| Risk | Spread across PROGRESS.md notes | ECC `council`, `production-audit`, `loop-design-check`, plus `ponytail-audit` and `ponytail-debt`, all feed **`docs/RISKS.md`**, updated at gates and on `S1_BUG` / `RED_FLAG` stops |

## Voice
- The main session and the phase runner load **caveman** at session start and talk to Quan in it, in Quan's language. The step-runner does not load it.
- Nobody uses caveman inside files: code, comments, docstrings, commits, docs, handoff notes.
- PR descriptions and PR comments: caveman in the narrative sections only (D2).
