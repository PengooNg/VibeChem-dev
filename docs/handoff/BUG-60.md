# Handoff — BUG #60
Branch: bug-pls-nipals-tol   Base: phase-1   Last commit: —   PR: —
Stop code: —   Machine: work-pc
Plan:
- Assumptions: R JSON is used unchanged (git normalises CRLF to LF, values identical). Oliveoil is R `pls` `oliveoil` (16 × 5 chemistry, 6 sensory), taken from the JSON itself, not a new dataset file. VIP vs other software is `T-iter` (METHODS #vip "Tolerance"); SIMPLS PLS2 predictions `T-iter`. One `assert_reference` row per LV count (the worst element), not one per value, so the report stays readable.
- Reuse: rung 4, scikit-learn `PLSRegression` stays; only `tol` / `max_iter` change (no new code, no dependency).
- Tools: ponytail (full), superpowers TDD (test first), systematic-debugging (root cause), ponytail-review, silent-failure-hunter, mle-reviewer, verification-before-completion. Context7 queried; scikit-learn 1.9.1 source read for the stop rule.
- Files: testdata/expected/r_pls_reference.json, testdata/datasets/PROVENANCE.md, packages/core/tests/blocks/model/test_pls.py, packages/core/src/vibechem_core/blocks/model/pls.py, docs/METHODS.md, docs/RISKS.md, docs/PROGRESS.md, CHANGELOG.md.
- cp1: JSON + provenance + reference tests (VIP PLS2 fails) · check: `uv run pytest packages/core/tests/blocks/model/test_pls.py`
- cp2: fix tol/max_iter + docs · check: `uv run python scripts/check.py --fast`
Done: —
Next action: cp1
