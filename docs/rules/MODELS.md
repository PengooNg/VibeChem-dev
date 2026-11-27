# Models: which model runs what

> Read this when you pick a model or spawn a subagent (phase, step, resume, bug skills). Decision R1 (Quan, 2026-11-27).

## Model per role
| Role | Model | Effort |
|---|---|---|
| Main session / phase runner | `sonnet` (interactive planning with Quan: `/model opusplan`) | medium |
| step-runner, default | `sonnet` | medium |
| step-runner, **Opus rule** (below) | `opus` | medium |
| `Explore` (overrides the built-in), `scribe` | `haiku` | low |
| silent-failure-hunter, cpp-reviewer | `sonnet` | medium |
| mle-reviewer, phase-gate step | `opus` | medium |
| Fable, `best` | never | — |

Effort is never `high`, `xhigh` or `max` unless Quan asks.

## Opus rule
The phase runner (and `/step`, `/resume`, `/bug`) runs `uv run python scripts/pick_model.py <step-id> [--after <STOP_CODE>]`, which prints `opus (rule <n>)` or `sonnet`, and passes that alias as `model:` to the step-runner. Rules 1–3 are checked by the script; rule 4 by the `--after` flag:
1. The step heading in TASKS.md matches `Size [ML]\b` (headings can read `Size L → split into …`) or carries the tag `⚑opus`.
2. The step's file list touches `packages/native/**`, `packages/engine/src/vibechem_engine/{scheduler,executor,compiler,cache}/**`, `packages/core/src/vibechem_core/blocks/{validate,split,select,transfer}/**`, `packages/core/src/vibechem_core/metrics.py`, or `docs/METHODS.md`.
3. It is the phase-gate step, or a resume after `S1_BUG`.
4. **Escalation:** a Sonnet step-runner stopped with `CI_RED`, `ESTIMATE` or a failed reference test → re-run that step **once** with Opus (resume from the handoff note; `--after CI_RED|ESTIMATE|REF_FAIL`). A second failure stops as usual.

Record the model in the step-runner DONE block (`Model: sonnet|opus (rule n)`) and in the `Model` column of the PROGRESS.md Step log, so Quan can tune the rule from real data.

## Precedence of model settings
The Agent tool `model` parameter beats an agent's frontmatter `model:`, which beats `CLAUDE_CODE_SUBAGENT_MODEL`. That variable is only the fallback for agents without a `model:` line (Plan, general-purpose).
