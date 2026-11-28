<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Benchmarks and profiling report (T2.12)

**Question:** does the engine reach the ARCHITECTURE.md §1.2 target (parallel speed-up ≥ 4× on 8 cores for nested CV, identical metrics for any core count), and which code should become a C++ kernel in Phase 3?
**Answer:** determinism holds (same result bits for 1, 2, 4, 8 and 16 workers and across repeats). The speed-up does **not** reach the target: **2.4×** at 8 workers on this machine. The cause is not the maths but the parent process, which pickles about 5 MB of dataset into each of 1,173 small tasks (5.2 GB in one run). Fixing that is a pure-Python change and has to come before any kernel. Phase 3 kernel candidates are few: Kennard–Stone and SPXY first; the PLS fit is faster with our own NumPy SIMPLS than with scikit-learn's NIPALS (2.8×), so it needs no kernel.

## What was measured
`scripts/bench.py` (`uv run python scripts/bench.py --workers 1,2,4,8,16 --repeats 2 --outer 10 --inner 5 --rows 800 --cols 1000 --profile`). It builds one pipeline through `vibechem.Pipeline`: `data.dataset` → `validate.kfold` (10 outer folds); `data.dataset` → `model.pls` (10 LV) → `validate.nested_cv` (3 chains: none, SNV, MSC; 5 inner folds). Data: synthetic 800 × 1,000 spectra (6.4 MB). One run is 1,173 tasks, each under 0.1 s. Runs use a warm `ProcessExecutor` (start-up is listed apart). Speed-up is the best of 2 runs relative to 1 worker. Each run's metrics, predictions and candidate tables are hashed.

Machine: Windows 11, 24 logical CPUs, Python 3.14.10 (laptop). **CI runners have 3–4 cores**, so the 4× / 8-core target cannot be judged there: the nightly `bench` job (3 OS, 1/2/4 workers) checks determinism and records the core count; the speed-up verdict is printed only when the machine has at least 8 CPUs. Numbers from the first nightly runs go into the PROGRESS.md log, not here.

## Results
| Workers | Start-up (s) | Best wall (s) | Speed-up | Result hash |
|---|---|---|---|---|
| 1 | 1.19 | 24.98 | 1.00× | 6ff6667e5168 |
| 2 | 1.24 | 14.42 | 1.73× | 6ff6667e5168 |
| 4 | 1.16 | 11.08 | 2.25× | 6ff6667e5168 |
| 8 | 1.34 | 10.52 | **2.37×** (target 4×: FAIL) | 6ff6667e5168 |
| 16 | 1.54 | 10.28 | 2.43× | 6ff6667e5168 |

Determinism: PASS (one hash for every worker count and repeat). The curve flattens at 4 workers: a serial part dominates.

### Why: the parent process is the bottleneck
Probing the 1-worker and 8-worker runs (timing each task inside the worker, `cProfile` in the parent):

| | 1 worker | 8 workers |
|---|---|---|
| Wall | 26.7 s | 10.4 s |
| Time inside tasks (sum) | 11.1 s | 16.5 s (workers compete for memory bandwidth and SMT) |
| Ideal wall (sum / workers) | 11.1 s | 2.1 s |
| Parent: `Pickler.dump` | | 4.5 s of 11.4 s, 3.8 ms per task |

- 1,173 tasks send 5,202 MB in total (median 4.9 MB, maximum 6.8 MB per task, dataset 6.4 MB): every task carries a full or partial `SpectralDataset` inside a task dependency, so `ProcessExecutor.share()` (memory map for top-level arrays only) never applies.
- The same pipeline in this process with an inline executor takes 12.4 s: faster than 8 workers (BLAS threads are not limited there).
- Task overhead is the next layer: scheduling, result `unpickle`, pipe I/O (about 13 ms per task with 1 worker).

## Profile of the compute (one run in this process, `cProfile`, 13.3 s of own time)
| Area | Share |
|---|---|
| scikit-learn | 34 % |
| NumPy | 24 % |
| VibeChem blocks | 23 % |
| other (built-ins) | 15 % |
| VibeChem engine | 3 % |
| SciPy | 0.3 % |

| Own time | Calls | Function |
|---|---|---|
| 24.1 % | 201 | scikit-learn `_PLS.fit` |
| 18.6 % | 4,020 | `numpy.outer` (the deflation step of NIPALS, 2 per component) |
| 7.7 % | 2,010 | `_get_first_singular_vectors_power_method` |
| 7.2 % | 201 | `vibechem_core` PLS block `fit` (own code around scikit-learn) |
| 5.3 % | 8,653 | `numpy.array` (copies) |
| 3.5 % | 361 | PLS block `apply` / prediction |
| 2.6 % | 330 | `SpectralDataset.subset` (row copies per fold) |

Block timings at 1,000 variables (one call, this machine):

| Block | 2,000 rows | 5,000 rows |
|---|---|---|
| `split.kennard_stone` | 0.94 s | **7.1 s** |
| `split.spxy` | 0.98 s | **7.2 s** |
| `preprocess.snv`, `msc`, `savgol`, `detrend`, `split.random` | ≤ 0.04 s | ≤ 0.08 s |
| `model.pls` fit, 640 × 1,000, 10 LV | NIPALS (scikit-learn) 43 ms; SIMPLS (own NumPy) **15 ms** | |

## Findings for Phase 3 and for earlier fixes
**Pure-Python and NumPy fixes (no kernel; do first):**
1. **Task transfer (blocks the 4× target).** Send datasets once as memory-mapped arrays and let tasks pass row indices, or share the `X` array of a `SpectralDataset` before it enters a task spec; expect most of the 4.5 s of pickling and the 5.2 GB to go. Needs a design decision (scheduler / runner, ADR-004 follow-up); proposed as an extra Phase 2 step before the gate.
2. **PLS default algorithm.** `algorithm: simpls` (own NumPy) is 2.8× faster than scikit-learn NIPALS on this size, and the PLS fit with `np.outer` deflation is 25–45 % of compute. Changing the default changes numbers within the METHODS.md tolerance: a decision for Quan; not changed here.
3. `SpectralDataset.subset` and `numpy.array` copies (8 %) per fold: views or index arrays.
4. Kennard–Stone and SPXY keep a full n × n matrix (`shortcut:` in the code, 200 MB at n = 5,000). An incremental O(n) minimum-distance update removes the matrix; test this in NumPy before writing C++.

**C++ kernel candidates (Phase 3, only if the NumPy fix is not enough):**
1. Kennard–Stone / SPXY max-min selection loop (7 s at 5,000 rows; O(n²) distance updates with n Python iterations).
2. Nothing else measured is over 0.1 s per call at v1 data sizes. CARS, SPA and PDS (planned in the outline) are not in the engine yet; profile them when they exist (T3.03–T3.06 are chosen from this report only for blocks present at the gate).

## Not measured
Other pipelines (PLS-DA, repeated CV, grid search without nesting), 4,000-variable data, macOS and Linux numbers (nightly job), imaging cubes, memory use per worker, a cold pool inside the frozen app (T0.13 covers that).
