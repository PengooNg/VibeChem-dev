# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/bench_parallel.py
"""Parallel spike (TASKS.md T0.13, ARCHITECTURE.md §3.4 and ADR-004): 1 vs N loky workers.

    uv run python scripts/bench_parallel.py [--workers 1,2,4] [--tasks 32] [--rows 4000]
        [--cols 500] [--repeats 3] [--seed 20261124] [--json PATH]

Also runs frozen: ``scripts/build_engine.py --entry scripts/bench_parallel.py --name
vibechem-parallel-spike`` builds a PyInstaller bundle with the skeleton engine's options,
and the bundle executable takes the same arguments.

Pattern under test (ARCHITECTURE.md §3.4): a loky reusable process pool; BLAS limited to
one thread per worker with threadpoolctl (in the worker initializer); one root seed,
``SeedSequence.spawn`` per task; the input matrix saved once as ``.npy`` and opened by
every worker with ``np.load(mmap_mode="r")``. Each task looks like one CV fold: draw 80 %
of the rows with its own generator, simulate a response, solve ridge least squares
(``X'X + λI``) — BLAS-bound, roughly 0.05-0.1 s on one core with the defaults.

Configurations: ``serial`` (in this process, BLAS = 1 thread; the reference results),
``serial-blas`` (in this process, BLAS at its default width), ``loky-N`` (N workers,
BLAS = 1 each), and at the largest N ``loky-N-blas`` (BLAS default width in every worker:
oversubscription) and ``loky-N-pickled`` (the matrix sent with every task instead of the
memory-mapped file). Determinism: every configuration must give the same bits in every
repeat, and every BLAS = 1 configuration the same per-task coefficients as ``serial``.

loky in a frozen app needs ``loky_freeze_support()`` (below) before
``multiprocessing.freeze_support()``: neither PyInstaller nor the standard library knows the
command lines loky 3.7 uses for its workers and its resource tracker.
"""
# loky and threadpoolctl ship no type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import multiprocessing
import os
import platform
import re
import runpy
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import loky
import numpy as np
from numpy.typing import NDArray
from threadpoolctl import threadpool_info, threadpool_limits

if sys.platform == "win32":
    import loky.backend.popen_loky_win32
else:
    import loky.backend.popen_loky_posix  # imported here so PyInstaller collects it
import loky.backend.resource_tracker

RIDGE = 1e-3
ROW_FRACTION = 0.8
_RESOURCE_TRACKER_CMD = re.compile(
    r"from loky\.backend\.resource_tracker import main; main\((\d+), (True|False)\)"
)
_limiter: object = None  # keeps the worker's threadpool limits alive


def loky_freeze_support() -> None:
    """Start loky's helper processes in a frozen app; call first in ``__main__``.

    In a PyInstaller bundle ``sys.executable`` is the bundle itself, so loky re-runs it with:
    ``-c "from loky.backend.resource_tracker import main; main(<fd>, <verbose>)"`` (resource
    tracker), ``--multiprocessing-fork <handle>`` (Windows worker; the standard
    ``freeze_support()`` expects ``name=value`` arguments there and fails), or
    ``-m loky.backend.popen_loky_posix …`` (macOS/Linux worker; the bootloader has no ``-m``).
    Each is routed to loky's own entry point here; the process exits when it is done.
    ``VIBECHEM_SPIKE_NO_LOKY_SHIM=1`` skips it, to show what fails without it.
    """
    if not getattr(sys, "frozen", False) or os.environ.get("VIBECHEM_SPIKE_NO_LOKY_SHIM") == "1":
        return
    argv = sys.argv
    # Step 1: resource tracker (all OS).
    if "-c" in argv:
        command_index = argv.index("-c") + 1
        match = (
            _RESOURCE_TRACKER_CMD.fullmatch(argv[command_index])
            if command_index < len(argv)
            else None
        )
        if match:
            loky.backend.resource_tracker.main(int(match[1]), match[2] == "True")
            sys.exit(0)
    # Step 2: worker process.
    if sys.platform == "win32":
        if len(argv) == 3 and argv[1] == "--multiprocessing-fork" and "=" not in argv[2]:
            # The frozen command line has no parent pid; the pipe handle lives in the parent.
            loky.backend.popen_loky_win32.main(int(argv[2]), parent_pid=os.getppid())
    elif argv[1:3] == ["-m", "loky.backend.popen_loky_posix"]:
        sys.argv = [argv[0], *argv[3:]]
        runpy.run_module(loky.backend.popen_loky_posix.__name__, run_name="__main__")
        sys.exit(0)


@dataclass(frozen=True)
class Task:
    """One fold-like unit of work; ``matrix`` is a ``.npy`` path or the array itself."""

    index: int
    seed: np.random.SeedSequence
    matrix: str | NDArray[np.float64]


@dataclass(frozen=True)
class TaskResult:
    index: int
    digest: str  # sha256 of the coefficient bytes
    pid: int
    blas_threads: int
    seconds: float
    memmapped: bool


@dataclass
class ConfigResult:
    name: str
    workers: int  # 0 = in this process
    blas: str  # "1" or "default"
    startup_s: float | None
    wall_s: list[float] = field(default_factory=list[float])
    task_s_sum: float = 0.0
    distinct_pids: int = 0
    blas_threads_seen: list[int] = field(default_factory=list[int])
    memmapped: bool = False
    repeatable: bool = True  # every repeat gave the same bits
    same_as_serial: bool = True  # ... and they equal the serial BLAS = 1 reference
    digest: str = ""


def synthetic_matrix(rows: int, cols: int, rng: np.random.Generator) -> NDArray[np.float64]:
    """Spectra-like rows: smooth bands with random amplitudes plus noise (float64)."""
    axis = np.linspace(0.0, 1.0, cols)
    centres = np.array([0.2, 0.45, 0.7])
    bands = np.exp(-(((axis[None, :] - centres[:, None]) / 0.05) ** 2))  # 3 x cols
    amplitudes = rng.uniform(0.5, 1.5, size=(rows, centres.size))
    return amplitudes @ bands + rng.normal(0.0, 0.01, size=(rows, cols))


def blas_thread_count() -> int:
    """Largest thread count among the BLAS libraries loaded in this process (0 if none)."""
    return max(
        (int(lib["num_threads"]) for lib in threadpool_info() if lib["user_api"] == "blas"),
        default=0,
    )


def run_task(task: Task) -> TaskResult:
    """Ridge fit on a seeded 80 % row draw; returns a digest of the coefficients."""
    start = time.perf_counter()
    # Step 1: open the shared input (memory map, no copy) or take the array sent along.
    matrix = np.load(task.matrix, mmap_mode="r") if isinstance(task.matrix, str) else task.matrix
    rows, cols = matrix.shape
    # Step 2: this task's own generator, from its spawned seed.
    rng = np.random.default_rng(task.seed)
    picked = np.sort(rng.choice(rows, size=int(ROW_FRACTION * rows), replace=False))
    x = np.asarray(matrix[picked], dtype=np.float64)
    y = x @ rng.normal(size=cols) + rng.normal(0.0, 0.1, size=picked.size)
    # Step 3: ridge least squares (BLAS: X'X, X'y, solve).
    gram = x.T @ x + RIDGE * np.eye(cols)
    coef = np.linalg.solve(gram, x.T @ y)
    return TaskResult(
        index=task.index,
        digest=hashlib.sha256(coef.tobytes()).hexdigest(),
        pid=os.getpid(),
        blas_threads=blas_thread_count(),
        seconds=time.perf_counter() - start,
        memmapped=isinstance(matrix, np.memmap),
    )


def init_worker(blas_threads: int | None) -> None:
    """loky initializer: limit BLAS threads in this worker (``None`` = leave the default)."""
    global _limiter  # noqa: PLW0603
    # threadpoolctl only limits libraries already loaded: load NumPy's BLAS first. A loky
    # worker imports NumPy only when it unpickles the first task, after the initializer.
    importlib.import_module("numpy")

    if blas_threads is not None:
        _limiter = threadpool_limits(limits=blas_threads, user_api="blas")


def worker_pid(_: int) -> int:
    """Trivial job used to start every worker before timing."""
    time.sleep(0.05)
    return os.getpid()


def make_tasks(n_tasks: int, seed: int, matrix: str | NDArray[np.float64]) -> list[Task]:
    """One task per spawned child of the run's root seed."""
    children = np.random.SeedSequence(seed).spawn(n_tasks)
    return [Task(index=i, seed=child, matrix=matrix) for i, child in enumerate(children)]


def combined_digest(results: list[TaskResult]) -> str:
    ordered = sorted(results, key=lambda r: r.index)
    return hashlib.sha256("".join(r.digest for r in ordered).encode()).hexdigest()


def record(config: ConfigResult, wall: float, results: list[TaskResult], reference: str) -> None:
    """Add one timed repeat to ``config``."""
    config.wall_s.append(wall)
    config.task_s_sum = sum(r.seconds for r in results)
    config.distinct_pids = len({r.pid for r in results})
    config.blas_threads_seen = sorted({r.blas_threads for r in results})
    config.memmapped = all(r.memmapped for r in results)
    digest = combined_digest(results)
    config.digest = config.digest or digest
    config.repeatable = config.repeatable and digest == config.digest
    config.same_as_serial = config.same_as_serial and digest == (reference or digest)


def run_serial(
    name: str, tasks: list[Task], blas: int | None, repeats: int, reference: str
) -> ConfigResult:
    config = ConfigResult(name=name, workers=0, blas="1" if blas else "default", startup_s=None)
    with threadpool_limits(limits=blas, user_api="blas"):
        for _ in range(repeats):
            start = time.perf_counter()
            results = [run_task(task) for task in tasks]
            record(config, time.perf_counter() - start, results, reference)
    return config


def run_loky(
    name: str, tasks: list[Task], workers: int, blas: int | None, repeats: int, reference: str
) -> ConfigResult:
    config = ConfigResult(
        name=name, workers=workers, blas="1" if blas else "default", startup_s=0.0
    )
    # Step 1: cold start — spawn the workers and run a trivial job on each.
    start = time.perf_counter()
    executor = loky.get_reusable_executor(
        max_workers=workers, timeout=60, initializer=init_worker, initargs=(blas,)
    )
    list(executor.map(worker_pid, range(workers)))
    config.startup_s = time.perf_counter() - start
    # Step 2: timed repeats on the warm pool.
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            results = list(executor.map(run_task, tasks))
            record(config, time.perf_counter() - start, results, reference)
    finally:
        # Workers keep the memory map open; Windows cannot delete the file before they exit.
        executor.shutdown(wait=True)
    return config


def run_all(args: argparse.Namespace, workdir: Path) -> dict[str, Any]:
    """Run every configuration; returns the JSON report."""
    # Step 1: input matrix, saved once for memory mapping.
    matrix = synthetic_matrix(args.rows, args.cols, np.random.default_rng(args.seed))
    path = workdir / "matrix.npy"
    np.save(path, matrix)
    tasks = make_tasks(args.tasks, args.seed, str(path))

    # Step 2: serial reference, then the pools.
    configs = [run_serial("serial", tasks, 1, args.repeats, "")]
    reference = configs[0].digest
    configs.append(run_serial("serial-blas", tasks, None, args.repeats, reference))
    for n in args.workers:
        configs.append(run_loky(f"loky-{n}", tasks, n, 1, args.repeats, reference))
    top = max(args.workers)
    configs.append(run_loky(f"loky-{top}-blas", tasks, top, None, args.repeats, reference))
    pickled = make_tasks(args.tasks, args.seed, matrix)
    configs.append(run_loky(f"loky-{top}-pickled", pickled, top, 1, args.repeats, reference))

    serial_s = statistics.median(configs[0].wall_s)
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "cpu_count": os.cpu_count(),
        "loky_cpu_count": loky.cpu_count(),
        "loky_physical_cores": loky.cpu_count(only_physical_cores=True),
        "blas": [
            {k: lib.get(k) for k in ("internal_api", "version", "num_threads")}
            for lib in threadpool_info()
            if lib["user_api"] == "blas"
        ],
        "workload": {"rows": args.rows, "cols": args.cols, "tasks": args.tasks, "seed": args.seed},
        "repeats": args.repeats,
        "configs": [
            {
                **asdict(c),
                "median_s": statistics.median(c.wall_s),
                "speedup": serial_s / statistics.median(c.wall_s),
            }
            for c in configs
        ],
    }


def markdown(report: dict[str, Any]) -> str:
    """Job-summary table for one run (ASCII: a frozen app ignores ``PYTHONIOENCODING``)."""
    frozen = "frozen bundle" if report["frozen"] else "Python"
    lines = [
        (
            f"### Parallel spike - {report['platform']} ({frozen}), "
            f"{report['loky_cpu_count']} CPUs ({report['loky_physical_cores']} physical)"
        ),
        "",
        "| Config | Workers | BLAS | Start-up s | Median s | Speed-up | Task CPU s | PIDs | BLAS threads | memmap | Repeatable | Same bits as serial |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in report["configs"]:
        startup = "-" if c["startup_s"] is None else f"{c['startup_s']:.2f}"
        lines.append(
            f"| {c['name']} | {c['workers'] or 'in-process'} | {c['blas']} | {startup} | "
            f"{c['median_s']:.2f} | {c['speedup']:.2f}x | {c['task_s_sum']:.2f} | "
            f"{c['distinct_pids']} | {c['blas_threads_seen']} | {'yes' if c['memmapped'] else 'no'} | "
            f"{'yes' if c['repeatable'] else '**NO**'} | {'yes' if c['same_as_serial'] else 'no'} |"
        )
    lines.append(f"\nReference digest (serial): `{report['configs'][0]['digest'][:16]}`")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="bench_parallel")
    parser.add_argument("--workers", default="1,2,4", help="comma-separated worker counts")
    parser.add_argument("--tasks", type=int, default=32)
    parser.add_argument("--rows", type=int, default=4000)
    parser.add_argument("--cols", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261124)
    parser.add_argument("--json", type=Path, help="write the report as JSON here")
    args = parser.parse_args(argv)
    try:
        args.workers = sorted({int(n) for n in args.workers.split(",")})
    except ValueError:
        parser.error("--workers must be comma-separated integers")
    if min(args.workers) < 1 or min(args.tasks, args.rows, args.cols, args.repeats) < 1:
        parser.error("--workers, --tasks, --rows, --cols and --repeats must be >= 1")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="vibechem-parallel-") as workdir:
        report = run_all(args, Path(workdir))
    print(markdown(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # BLAS at full width may change the bits (it splits the sums differently); only the
    # one-thread configurations must match the serial reference.
    ok = all(
        c["repeatable"] and (c["same_as_serial"] or c["blas"] != "1") for c in report["configs"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    loky_freeze_support()
    multiprocessing.freeze_support()
    sys.exit(main(sys.argv[1:]))
