Status: <state> · next: <action> · machine: <$VIBECHEM_MACHINE> · updated <YYYY-MM-DD HH:MM>
<!-- Keep the Status line first and current (CLAUDE.md §8.1). States: cpN/M done · PAUSED at cpN/M · STOPPED: <CODE> · complete — merging -->

## TASKS step
<!-- e.g. T1.07 · SNV, MSC, detrend, cut (docs/TASKS.md). Bug PRs: issue link. -->

## Plan as executed
<!-- Checkpoints as done, each with the command that proved it. Note any change from the original plan and why. -->

## Reuse decision
<!-- reuse > wrap > port > build (CLAUDE.md §12): options table or one line, and the choice. -->

## Estimate vs actual
<!-- Estimated checkpoints → actual checkpoints (size S/M/L). -->

## Files changed
<!-- Grouped list. Only the step's files plus tests, docs, CHANGELOG, TASKS.md, PROGRESS.md. -->

## Tests added
<!-- Unit / reference / property / regression tests, and the source of each expected value. -->

## Docs updated
<!-- DATA_MODEL, METHODS, TECH_STACK, THIRD_PARTY, CHANGELOG, TASKS tick, PROGRESS.md — or "none". -->

## Health summary
```
<paste the summary printed by `uv run python scripts/check.py --fast`>
```

## Tools used
<!-- Skills, plugins, MCP tools (CLAUDE.md §13), incl. library + version checked with Context7. -->

## Review
<!-- code-review findings and how each was handled; /security-review for 🔒 steps; visual check for app/ steps (screenshots attached, critique/audit/break-ui/accessibility findings). -->

## Bug fix (bug PRs only)
<!-- Root cause · Fix · Test added · Possibly affected areas (CLAUDE.md §7). Delete for step PRs. -->

## Assumptions and open questions
<!-- Assumptions made, anything you were unsure about. -->

## Unrelated issues noticed (not touched)
<!-- Pre-existing bugs or dead code outside the step (CLAUDE.md A3) — or "none". -->

## Definition of done (QA.md §7)
- [ ] Only the step's files (plus tests, docs, CHANGELOG, TASKS.md tick, PROGRESS.md) changed
- [ ] Plan as executed and reuse decision recorded; TECH_STACK.md §11 updated if a candidate was evaluated
- [ ] New/changed behaviour has tests (unit + reference/property for algorithms, incl. wrapped libraries)
- [ ] Full `scripts/check.py --fast` PASS locally; CI green on 3 OS
- [ ] Docs updated if behaviour, fields or dependencies changed; `THIRD_PARTY.md` if code was copied; CHANGELOG entry if user-visible
- [ ] Template complete, health summary pasted, code-review run
- [ ] PROGRESS.md updated (Now, Step log, K backlog row if applicable)
- [ ] Handoff note deleted; labels set; merged with `merge_step.py` (👤 steps: Quan merges)
