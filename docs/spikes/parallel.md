<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Spike — parallel (T0.13)

**Question:** does the ADR-004 pattern hold up on all three OS, both in Python and inside a PyInstaller bundle? The pattern is a loky process pool with warm workers, BLAS capped at one thread per worker with threadpoolctl, one root seed with `SeedSequence.spawn` per task, and large inputs passed as memory-mapped files. Does it give a real speed-up with bit-identical results?
**Answer:** yes, with one required fix. loky 3.7 workers **do not start in a frozen app** on any OS when the entry script only calls `multiprocessing.freeze_support()`. A ~25-line `loky_freeze_support()` shim fixes this. With the shim, the frozen bundle gives the same speed-up and the same bits as plain Python. Every BLAS = 1 configuration gave bit-identical results to the serial run, at every worker count and in every repeat.

## What was measured
`scripts/bench_parallel.py` (`--workers 1,2,4 --tasks 32 --repeats 3`). The input is a synthetic 4,000 × 1,000 float64 matrix of spectra-like rows (32 MB), saved once as `.npy`. Each of the 32 tasks stands in for one CV fold. It builds its own generator from `SeedSequence(20261124).spawn(32)[i]`, draws 80 % of the rows, simulates a response, and solves ridge least squares (`X'X + λI`). The work is BLAS-bound, about 0.09–0.12 s per task on one core. A task returns the SHA-256 of its coefficient bytes.

| Config | What it is |
|---|---|
| `serial` | in the parent process, BLAS = 1 thread: **the reference bits** |
| `serial-blas` | in the parent process, BLAS at its default width (4 threads on the runners) |
| `loky-N` | loky reusable pool with N workers. The initializer sets `threadpool_limits(1, "blas")`. Workers open the matrix with `np.load(mmap_mode="r")` |
| `loky-4-blas` | 4 workers with BLAS left at its default width (oversubscription) |
| `loky-4-pickled` | 4 workers, with the matrix pickled into every task instead of memory-mapped |

"Start-up" is the time to spawn N workers and run one trivial job on each (cold pool). "Wall" times are taken on the warm pool. The frozen runs use a bundle built by `scripts/build_engine.py --entry scripts/bench_parallel.py --name vibechem-parallel-spike`. That is the skeleton engine's PyInstaller 6.21 one-folder configuration with this script as the entry point. Workflow: `spike-parallel.yml` (non-required, 3 OS).

## Results (GitHub-hosted runners, 2026-11-24, run 45369668426)
Median wall time in s for 32 tasks over 3 repeats. Speed-up is relative to `serial` on the same OS and in the same mode. Runner CPUs: Linux and Windows have 4 vCPUs (2 physical cores, OpenBLAS 0.3.34); macOS arm64 has 3 cores (NumPy uses Accelerate there, and threadpoolctl cannot see or limit it).

| Config | Linux Python | Linux frozen | Windows Python | Windows frozen | macOS Python | macOS frozen |
|---|---|---|---|---|---|---|
| serial (BLAS 1) | 2.89 | 2.86 | 3.99 | 3.97 | 1.39 | 1.72 |
| serial-blas (BLAS default) | 1.73 (1.67×) | 1.67 (1.71×) | 2.91 (1.37×) | 2.91 (1.37×) | 1.47 (0.94×) | 2.15 (0.80×) |
| loky-1 | 2.97 (0.97×) | 3.02 (0.95×) | 4.12 (0.97×) | 4.14 (0.96×) | 1.75 (0.79×) | 2.25 (0.77×) |
| loky-2 | 1.53 (**1.89×**) | 1.57 (**1.82×**) | 2.25 (**1.77×**) | 2.18 (**1.82×**) | 1.09 (**1.27×**) | 1.27 (**1.35×**) |
| loky-4 | 1.36 (**2.13×**) | 1.36 (**2.11×**) | 1.81 (**2.21×**) | 1.79 (**2.22×**) | 0.84 (**1.65×**) | 1.03 (**1.67×**) |
| loky-4-blas (oversubscribed) | 15.02 (0.19×) | 14.98 (0.19×) | 17.19 (0.23×) | 17.50 (0.23×) | 0.83 (1.68×) | 1.06 (1.63×) |
| loky-4-pickled | 1.60 (1.81×) | 1.60 (1.79×) | 2.04 (1.96×) | 2.05 (1.93×) | 4.65 (0.30×) | 9.09 (0.19×) |
| cold start, 1 / 2 / 4 workers | 0.19 / 0.17 / 0.25 | 0.34 / 0.22 / 0.34 | 0.24 / 0.26 / 0.33 | 0.28 / 0.27 / 0.36 | 0.57 / 0.26 / 0.35 | 0.88 / 0.47 / 0.84 |

**Determinism** (all 6 OS × mode combinations):
- Every BLAS = 1 configuration (`serial`, `loky-1/2/4`, `loky-4-pickled`) gave the **same per-task bits as `serial`** in every repeat. That holds whatever the worker count, task order or worker assignment, and whether the input was memory-mapped or pickled.
- Frozen and Python digests are **identical** on each OS (checked in the workflow).
- BLAS at default width (`serial-blas`, `loky-4-blas`) is repeatable, but on OpenBLAS it gives **different bits** from BLAS = 1, because a multi-threaded GEMM splits the sums differently. On macOS (Accelerate) the bits matched.
- Across OS the bits differ (one digest per OS). Linux and Windows run the same OpenBLAS version but pick CPU-specific kernels. Cross-machine equality therefore has to be judged with tolerances, not by hash.

**Without the shim** (`VIBECHEM_SPIKE_NO_LOKY_SHIM=1`, frozen): `TerminatedWorkerError` on Linux, macOS and Windows (worker exit code 2 on POSIX).

## Findings
1. **loky needs a freeze shim in the frozen app (blocking for the executor step).** In a bundle, `sys.executable` is the app itself, and loky 3.7 re-runs it with command lines that neither PyInstaller's `freeze_support()` hook nor the standard library knows:
   - `-c "from loky.backend.resource_tracker import main; main(fd, verbose)"` (resource tracker, all OS);
   - `--multiprocessing-fork <handle>` (Windows worker; the standard `freeze_support()` expects `name=value` arguments and crashes, and the frozen command line has no parent pid, so the shim passes `os.getppid()`);
   - `-m loky.backend.popen_loky_posix --process-name … --pipe <fd>` (macOS/Linux worker; the bootloader does not implement `-m`, so the app's own argparse rejects the arguments).

   `loky_freeze_support()` in `scripts/bench_parallel.py` routes each of these to loky's own entry point, and it must run **before** `multiprocessing.freeze_support()`. The resource-tracker route matches loky's exact command with a regex and calls `main()` directly; it never `exec`s argument text. It depends on loky internals, so pin loky to a minor version and keep the frozen test in CI (see recommendation).
2. **BLAS must be capped per worker, and the cap must come after NumPy is loaded.** threadpoolctl only limits libraries that are already loaded, and a loky worker imports NumPy only when it unpickles the first task, which happens after the initializer has run. The first local run therefore showed 24 BLAS threads per worker. Importing NumPy in the initializer fixes it. Without the cap, 4 workers × 4 OpenBLAS threads were **8–10× slower than serial** (15–17.5 s vs 1.4–1.8 s).
3. **Speed-up follows physical cores.** It was 1.8–1.9× with 2 workers and 2.1–2.2× with 4 workers on 2-core / 4-thread runners, and 1.65× with 4 workers on 3 macOS cores. Hyper-threads add only 12–25 %. Pool overhead is small: `loky-1` runs at 0.95–0.97× of in-process serial on Linux and Windows, and the cold start for 1–4 workers takes 0.17–0.36 s (up to 0.9 s on macOS). Keeping workers warm, as ADR-004 plans, is worth it for short runs.
4. **Parallel across tasks beats parallel inside BLAS** (2.1× vs 1.4–1.7× on the same 4 vCPUs), and it keeps the bits independent of the core count. This supports the ADR's "one core budget, never both at full width" rule. A task's BLAS width must be **fixed** (1), not derived from the free cores, otherwise results depend on scheduling.
5. **Memory maps beat pickling large inputs.** On Linux and Windows the 32 MB-per-task copy made the run 13–18 % slower. On macOS it was 5–9× slower, with median 4.7–9.1 s against 0.8–1.0 s for the memory map. Memory-mapped `.npy` is also the cheaper option for RAM: one page-cache copy instead of one copy per task.
6. **Accelerate on macOS is outside threadpoolctl's control.** `threadpool_info()` lists no BLAS library there, so `serial` and `loky-4-blas` are not truly single-threaded on macOS. Its 3-core speed-up is a lower bound. The core budget on macOS needs another lever, such as `VECLIB_MAXIMUM_THREADS` set through loky's `env=` (not tested here).
7. **Frozen vs Python:** on Linux and Windows the speed is the same within noise. On macOS the frozen run was 15–25 % slower in several configurations (one runner, one run, so it may be noise), and its cold start was slower too (up to 0.9 s). Re-check this on a real Mac at the gate.

## Not measured (limits of this spike)
- Real blocks and real fold structure. Memory-pressure behaviour (the free-RAM guard) on an 8 GB laptop. Nested parallelism together with C++ kernels (Phase 3).
- The production engine bundle. The spike bundle uses the same PyInstaller options but a different entry point. The engine does not import loky yet.
- Worker crash recovery, cancellation and the idle `timeout` (60 s here); these belong to the executor step.
- The `VECLIB_MAXIMUM_THREADS` or `env=` route for Accelerate.

## Recommendation for ADR-004 (for the T0.15 gate)
**Accept option A** (own scheduler over a loky pool, behind an executor interface). The spike shows the speed-up and the bit-level determinism ADR-004 relies on, on all three OS and in a frozen bundle. Proposed additions to Consequences/Actions:
- **Frozen entry:** the engine entry (`vibechem_engine/api/__main__.py`) calls a `loky_freeze_support()` (moved from the spike into `vibechem_engine`) before `multiprocessing.freeze_support()`. Pin loky `>=3.7,<3.8`. Add a frozen-bundle executor test (loky workers inside the real engine bundle) to `installers.yml`. Update TECH_STACK §12 (done in this PR).
- **BLAS width is fixed per task** (default 1, set in the worker initializer after importing NumPy). It is never derived from the cores currently free, because the bits change with the BLAS width (finding 4). The determinism test in nightly CI compares per-task hashes for 1 vs N workers.
- **Inputs above a size threshold are passed as memory-mapped `.npy` files** from the run's cache folder; small arguments are pickled.
- **macOS:** cap Accelerate through `env={"VECLIB_MAXIMUM_THREADS": "1"}` (to verify in the executor step), because threadpoolctl cannot see it.
- Cross-machine reproducibility is checked with tolerances (QA.md), not bit hashes.
- Move loky and threadpoolctl from the dev group into `vibechem-engine` when the executor first imports them, and add threadpoolctl to TECH_STACK §3.1.
