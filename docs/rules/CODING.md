# Coding rules: how to think, block template, reuse and estimates

> Read this when you plan or write code (step-runner, `/bug`). Moved verbatim from the old CLAUDE.md (Part A, block template, when unsure, reuse) on 2026-11-27.

## How to work (always applies)

These rules trade speed for care. For a trivial change (typo, one-line doc fix) use judgment and skip the ceremony, but never skip tests or the "never do" list (CLAUDE.md#hard-rules).

### A1. Think before coding
- **State your assumptions** explicitly in the plan. If an assumption changes behaviour, results or the architecture, it is a stop condition (docs/rules/WORKFLOW.md#stop-conditions) — don't pick silently.
- **Show alternatives** when a request can be read more than one way, and say which one you'd choose and why.
- **Push back** when a simpler approach exists or a request conflicts with the docs. Say so before writing code.
- **When something is unclear, stop.** Name exactly what is confusing and ask one short question. A question costs the user seconds; a wrong guess costs a review and a rewrite.
- **Never invent facts:** field names, error codes, port types, file formats, library APIs or paper equations. Look them up (DATA_MODEL.md, METHODS.md, and **Context7 for library APIs at the pinned version** — docs/TOOLS.md#5-rules-for-the-tools) or ask.
- List any assumptions still open at the end of the plan and of the PR description.

### A2. Simplicity first
Apply the `ponytail` skill (full).

### A3. Surgical changes
Apply the `ponytail` skill (full).

### A4. Goal-driven execution
- Turn every task into **checkable goals** before coding. "Fix the bug" → write a test that reproduces it, then make it pass. "Add MSC" → reference test against an independent value passes, `check.py` is green.
- For multi-step work, write a short plan where **each checkpoint has its own check** (which test or command proves it is done).
- Loop until the checks pass. Don't declare success on reasoning alone — run the tests.
- The step's **"Done when"** in TASKS.md is the success criterion. If it is too vague to check, that is a stop condition.

**Signs these rules are working:** small diffs, simple first drafts, questions asked before implementing rather than after a mistake, few rewrites in review.

## Block template and comment style
Every block is one file with a header docstring, typed parameters and numbered `# Step N:` comments matching `docs/METHODS.md` (D6: these stay mandatory even though ponytail limits comments; beyond them, only one-line "why" comments and `shortcut:` comments). **Before writing, changing or reviewing any block, load the `block-template` skill** (`.claude/skills/block-template/SKILL.md`) — it holds the full template and example.

## When unsure
See A1 and docs/rules/WORKFLOW.md#stop-conditions: ask before guessing. Prefer a short stop with one clear question over a wrong assumption.

## Reuse first, and estimate before committing
_(ponytail applied)_
Writing code we could have reused wastes the owner's time and money. Before planning any implementation:

**12.1 The ponytail ladder (take the first rung that fully works)**
1. Does it need to exist? Skip features, options and flexibility nobody asked for; name them in one line.
2. Already in this codebase: this repo, the step's "Reuse" line in TASKS.md, TECH_STACK.md §11 reuse register, FUNCTION_CATALOG.md "Likely source" notes.
3. Standard library or platform feature.
4. An installed dependency: NumPy, SciPy, scikit-learn, pyarrow, React Flow, uPlot, etc. (check the API with Context7, docs/TOOLS.md#5-rules-for-the-tools).
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
