# Handoff — BUG #84
Branch: bug-84-macos-intel   Base: phase-2   PR: (draft, after cp1)
Machine: laptop

## Plan
Assumptions:
- The nightly macOS Intel runner (`macos-26-intel`, CPython 3.14) installs the NumPy 2.5.5 `macosx_14_0_x86_64` wheel (6.5 MiB in the log), which links Apple Accelerate, not OpenBLAS.
- threadpoolctl 3.8.0 has no Accelerate controller (no `accelerate`/`veclib` in its source), so `threadpool_limits(1, "blas")` in the test process does not limit Accelerate. Workers are capped by `VECLIB_MAXIMUM_THREADS=1` (`_WORKER_ENV`), set before NumPy loads. The in-process reference therefore runs multithreaded Accelerate and differs in the last bits.
- Product runs always use `ProcessExecutor` (`Pipeline.run`), so the 1-vs-N-workers promise holds; the broken side is the tests' in-process reference.
- macOS arm64 also uses Accelerate but passes (its kernels do not change the summation order with threads for these sizes, observed).

Reuse ladder: no new code beyond setting the one environment variable the executor already sets for workers; no dependency.

Tools: ponytail (full), superpowers systematic-debugging + test-driven-development, ponytail-review, silent-failure-hunter.

Files: `conftest.py` (new, repo root: env before NumPy loads), `packages/engine/tests/executor/test_executor.py` (regression test), `packages/engine/tests/runners/test_runners.py` (BLAS = 1 around the in-process run), `.github/workflows/nightly.yml` (`workflow_dispatch` input `ref` to verify a branch; no S2 issue for such runs), docs (RISKS R67, PROGRESS, CHANGELOG).

Checkpoints:
1. Failing regression test + nightly `ref` input; dispatch nightly on the branch: macOS Intel shows the two tests red and the BLAS name (proves reproduction).
2. Fix (root conftest); dispatch again: macOS Intel green. `check.py --fast` locally.
3. Docs, reviews, merge.
