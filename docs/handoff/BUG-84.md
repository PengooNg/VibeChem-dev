# Handoff — BUG #84
Branch: bug-84-macos-intel   Base: phase-2   PR: #96
Stop code: none (resumed)   Machine: laptop
Status: cp3 in progress (option A applied; verifying on CI)

## Plan (as started)
Checkpoints: 1 failing regression test + nightly `ref` input; 2 fix; 3 docs, reviews, merge.

## Done
- cp1: regression test `test_test_process_caps_accelerate_like_the_workers` (executor tests); `nightly.yml` `workflow_dispatch` input `ref` (checks one branch, opens no S2 issue).
- cp2 (part 1 of the cause): root `conftest.py` sets `VECLIB_MAXIMUM_THREADS=1` before NumPy loads (raises if NumPy loaded first); `test_process_pool_gives_the_same_curve` caps BLAS at 1 around its in-process run.
- Evidence (all on this branch):
  - Nightly dispatch 46152099395 (before the fix): macOS Intel NumPy BLAS = `accelerate`; 9 failures.
  - Nightly dispatch 46152738990 (after part 1): executor test passes; still red on macOS Intel: golden `nd_sg`, `test_shared_scheduler_gives_the_serial_results[1,4]`, `test_process_pool_gives_the_same_curve`, `test_each_candidate_equals_a_separate_cv_run_of_its_chain`, `test_quick_run_gives_the_same_bits_for_1_and_2_workers`. Linux, Windows, macOS arm64 green.
  - Probe 46153252708 (macOS Intel, `scripts/bug84_probe.py`): thread cap changes the bits of `x.T @ x`, `x @ v`, `lstsq`, `svd`; with one thread, `np.linalg.norm` still depends on the data's offset mod 32.
  - Probe 46153695070 (macOS Intel, OpenBLAS wheels via `MACOSX_DEPLOYMENT_TARGET=13.0 uv sync --locked --python-platform x86_64-apple-darwin`): no offset dependence; executor, runners, CLI, bench and golden tests pass 3 times (50 passed each).
  - Probe 46154017016 (macOS arm64, Accelerate): matrix-vector product differs for every offset tested (0, 8, 16, 32, 48), with or without the thread cap. The shipped arm64 dmg is exposed too.

## Decision by Quan: A
Install the OpenBLAS wheels on macOS wherever we install. Plan:
- cp3a: `scripts/uv_sync.sh` (non-macOS: `uv sync --locked`; macOS: `MACOSX_DEPLOYMENT_TARGET=13.0 uv sync --locked --python-platform <arch>-apple-darwin`, asserts NumPy and SciPy report OpenBLAS, sets `UV_NO_SYNC=1` for later CI steps so `uv run` cannot sync back to Accelerate). Used by every `uv sync` step in `ci.yml` (check), `nightly.yml` (check, e2e, bench) and `installers.yml` (the macOS dmg build; there is no separate release workflow yet). TECH_STACK §2 dev setup names it for macOS.
- cp3b: nightly dispatch on this branch + arm64 probe; all 6 formerly red macOS Intel tests and arm64 green.
- cp3c: remove the probe files; reviews (ponytail-review, silent-failure-hunter); PROGRESS row; R67 mitigated; merge.
Reuse: wrap (uv's own `--python-platform`; NumPy/SciPy's OpenBLAS wheels already in `uv.lock`). New dependencies: none.

## Not done
- The fix for alignment dependence (needs Quan's decision, below), its verification on macOS Intel and arm64, reviews, merge.
- Temporary files to remove before merge: `scripts/bug84_probe.py`, `.github/workflows/bug84-probe.yml`.

## Question for Quan
Accelerate cannot give bit-identical results (alignment-dependent kernels). Option A (recommended): install the OpenBLAS wheels on macOS everywhere we install (nightly macOS jobs, `ci.yml` macOS, installers/release macOS builds, TECH_STACK dev setup) with `MACOSX_DEPLOYMENT_TARGET=13.0` and `uv sync --python-platform <arch>-apple-darwin`; cost: slower BLAS on Apple Silicon and a larger bundle. Option B: a written waiver of bit-identity on macOS.

## Next action
On A: change the macOS install steps, rerun nightly dispatch (`gh workflow run nightly.yml --ref bug-84-macos-intel -f ref=bug-84-macos-intel`) and a probe on arm64; then remove the probe files, reviews (ponytail-review, silent-failure-hunter), PROGRESS Step-log row, R67 to mitigated, merge.
