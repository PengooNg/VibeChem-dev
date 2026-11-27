Status: <state> · next: <action> · machine: <$VIBECHEM_MACHINE> · updated <YYYY-MM-DD HH:MM>
<!-- Keep the Status line first and current (docs/rules/WORKFLOW.md#status-line). States: cpN/M done · PAUSED at cpN/M · STOPPED: <CODE> · complete — merging -->
<!-- Voice (D2): narrative sections in caveman voice. Headings, the Status line, the health summary, code, paths and commands stay exact. Questions to Quan in full sentences. -->

## TASKS step
<!-- e.g. T1.07 · SNV, MSC, detrend, cut (docs/TASKS.md). Bug PRs: issue link. -->

## Plan as executed
<!-- Checkpoints as done, each with the command that proved it. Note any change from the original plan and why. -->

## Reuse decision
<!-- ponytail ladder (docs/rules/CODING.md#reuse-first-and-estimate-before-committing (12.1)): the rung taken in one line; M/L steps: the options table. -->

## Estimate vs actual
<!-- Estimated checkpoints → actual checkpoints (size S/M/L). -->

## Files changed
<!-- Grouped list. Only the step's files plus tests, docs, CHANGELOG, TASKS.md, PROGRESS.md, RISKS.md. -->

## Tests added
<!-- One small test per piece of non-trivial logic; the reference test for each algorithm block and the source of its expected value; regression tests. -->

## Docs updated
<!-- DATA_MODEL, METHODS, TECH_STACK, THIRD_PARTY, CHANGELOG, TASKS tick, PROGRESS.md, RISKS.md — or "none". -->

## Health summary
```
<paste the summary printed by `uv run python scripts/check.py --fast`>
```

## Tools used
<!-- Skills, agents, MCP tools (docs/TOOLS.md#5-rules-for-the-tools, TOOLS.md §3 row), incl. library + version checked with Context7. -->

## Review
<!-- ponytail-review findings and how each was handled; ECC agents for the areas touched (silent-failure-hunter, cpp-reviewer, mle-reviewer); /security-review for 🔒 steps; visual check for 👁 steps (screenshots attached, critique/audit/break-ui/accessibility findings). -->

## Bug fix (bug PRs only)
<!-- Root cause · Fix · Test added · Possibly affected areas (docs/QA.md#6-bug-protocol). Delete for step PRs. -->

## Assumptions and open questions
<!-- Assumptions made, anything you were unsure about, ponytail's "skipped / risk" lines. -->

## Unrelated issues noticed (not touched)
<!-- Pre-existing bugs or dead code outside the step — or "none". -->

## Definition of done (QA.md §7)
- [ ] Only the step's files (plus tests, docs, CHANGELOG, TASKS.md tick, PROGRESS.md, RISKS.md) changed
- [ ] Plan as executed and reuse decision recorded; TECH_STACK.md §11 updated if a candidate was evaluated
- [ ] Non-trivial logic has one small test; every algorithm block has a reference test against an independent value; bugs have a regression test
- [ ] Full `scripts/check.py --fast` PASS locally; CI green on 3 OS
- [ ] Docs updated if behaviour, fields or dependencies changed; `THIRD_PARTY.md` if code was copied; CHANGELOG entry if user-visible
- [ ] Template complete, health summary pasted, ponytail-review + per-area agents run
- [ ] PROGRESS.md updated (Now, Step log); `docs/RISKS.md` row if a risk stays open
- [ ] Handoff note deleted; labels set; merged with `merge_step.py` (👤 steps: Quan merges)
