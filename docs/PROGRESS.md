# VibeChem — Progress log

> Written by Claude Code in every step PR (CLAUDE.md §6.9); newest rows first. Quan reads **Now** and **Needs you**.
> Live view between merges: the phase PR `[PHASE N] …` on GitHub, PRs labelled `needs-quan` / `paused`, or `/status`.

## Now
| Phase | Branch | Phase PR | Last merged step | Next step | Updated | Machine |
|---|---|---|---|---|---|---|
| 0 | `phase-0` | #6 | T0.02 (awaiting Quan's merge, #7) | T0.03 | 2026-11-23 | laptop |

## Needs you
<!-- One line per open item: date · step · stop code · exact action · PR. Remove the line when resolved (move it to Stops with "resolved"). -->
- (none)

## Step log
| Date | Step | Result | PR | Size est → actual (cp) | Reuse decision | Notes |
|---|---|---|---|---|---|---|
| 2026-11-23 | T0.02 | skeleton tree, legal/community files, PR template, issue forms, 10 labels, `merge_step.py` (28 unit tests); HUMAN_STEP (Quan merges) | #7 | M → 4 | reuse — GPL-3.0 text already in repo (verbatim FSF), Keep-a-Changelog 1.1.0; build — `merge_step.py` (stdlib + `gh`, required by TASKS) | check.py not yet available (T0.03): tests run with `uv run --no-project python -m unittest discover -s scripts/tests`; CI smoke does not run them yet; CITATION.cff lacks ORCID and DOI (TODOs for Quan); ui-ux-pro-max vendored commit not recorded in THIRD_PARTY.md |
| 2026-11-23 | T0.01 | ci-smoke green on 3 OS; HUMAN_STEP (Quan merges) | #4 | S → 2 | reuse — existing `ci-smoke.yml` from PR #1 (actions/checkout, actions/setup-python) | PR #1 went straight to `main`; triggers narrowed to PRs/pushes on `main` and `phase-*`; check.py not yet available (T0.03); labels not yet created (T0.02) |

## Stops
| Date | Step | Code | What was needed | Resolved (date, how) |
|---|---|---|---|---|

## Phase gates
<!-- Gate report per CLAUDE.md §14.4: exit criteria + evidence, health summary, estimate accuracy, reuse ratio, ADR recommendations, QA §9.1 items, open issues, Quan's decision. -->

## K review backlog (until demo v0 = Beta)
| Step | PR | Area | What K should check | Done |
|---|---|---|---|---|
| T0.02 | #7 | CI / repo tooling | `scripts/merge_step.py` guards (base `phase-*`, not draft, checks `pass`/`skipping` and ≥ 1 check, title prefix, 👤 read from TASKS.md on the base branch, `--match-head-commit`, remote-only branch delete via `gh api` instead of `--delete-branch`); `.gitattributes` LF policy and binary list; `.gitignore`; `.github/CODEOWNERS`; package README stubs vs §3.1 boundaries | [ ] |
| T0.01 | #4 | CI | `ci-smoke.yml` triggers (`main`, `phase-*`), action versions (checkout@v5, setup-python@v5, Python 3.14); workflow to be deleted in T0.06 | [ ] |
