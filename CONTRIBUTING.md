# Contributing to VibeChem

Thanks for your interest in VibeChem. It is a free, open-source desktop app for chemometrics on vibrational and hyperspectral spectra. This guide covers how to report problems, propose methods and send changes.

## Licence

VibeChem is licensed under the GNU General Public License v3.0 or later (`GPL-3.0-or-later`, see `LICENSE`). By contributing you agree that your contribution is released under the same licence.

- Every source file starts with `# SPDX-License-Identifier: GPL-3.0-or-later` (or the comment syntax of its language).
- Code copied from another project must have a GPL-3.0-compatible licence (MIT, BSD, Apache-2.0, LGPL, GPL-3.0). Keep the original copyright notice, add a header naming the source, and list it in `THIRD_PARTY.md`.

## Reporting bugs and requesting features

Use the issue forms on GitHub:
- **Bug report**: steps to reproduce, expected and actual result, and the output of "Copy diagnostics" (versions, OS, last errors, run and node IDs; it contains no user data). Attach the pipeline file if you can.
- **Feature request**: the problem you want solved, not only the solution.
- **Method request**: a chemometrics method you would like as a block, with its reference paper and any existing implementation.

A result that is silently wrong, such as a wrong number without any error or data leaking between training and test sets, is the most serious kind of bug (severity S1). Please say so clearly in the report.

## Development

Project rules live in `CLAUDE.md`, and the documents in `docs/` explain the design:
- `docs/TECH_STACK.md`: versions, folder layout, package boundaries, conventions, commands.
- `docs/QA.md`: tests, quality levels and the definition of done.
- `docs/METHODS.md`: algorithm definitions and reference values (from T1.04).
- Each package has a `README.md`. Read it before you change the package.

### Branches and pull requests
- Work happens in phases. Each phase has a branch `phase-<N>`; step and bug branches start from it and merge back into it. `main` only receives a phase at its gate.
- Step PR titles look like `[T1.07] <step title>`, and bug-fix titles like `[BUG #<issue>] <short description>`.
- Fill in every section of the pull request template.
- Step PRs are squash-merged into the phase branch with `scripts/merge_step.py`. It refuses when checks are red, the PR is a draft, or the step needs the owner.

### Before you open a pull request
- Add tests for every new or changed function. Algorithms also need reference tests with expected values from an independent source.
- Run the full local check: `uv run python scripts/check.py --fast` (available from step T0.03).
- Keep the change limited to what the step or issue needs.
- Don't use pickle for anything saved or shared, don't use global random state, and don't hard-code user-visible text (use i18n keys).
- Prefer an existing, maintained library with a compatible licence over new code. See the reuse register in `docs/TECH_STACK.md` §11.

## Citing

If you use VibeChem in published work, please cite it using `CITATION.cff`, and cite the methods listed in your VibeChem report.
