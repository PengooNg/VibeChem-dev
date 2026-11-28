# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/bench.py
"""Speed-up, determinism and profile of the pipeline engine (TASKS.md T2.12, ARCHITECTURE.md §1.2).

    uv run python scripts/bench.py [--workers 1,2,4,8] [--rows 600] [--cols 800] [--outer 5]
        [--inner 4] [--repeats 2] [--seed 20261128] [--profile] [--quick] [--json PATH]

Runs one nested-CV pipeline (``data.dataset`` -> ``validate.kfold`` and ``model.pls`` ->
``validate.nested_cv`` with three preprocessing chains) through ``vibechem.Pipeline`` on a
synthetic spectra-like dataset, once per worker count, on the real ``ProcessExecutor`` (warm pool: its start-up is listed apart and not in the speed-up).

* Speed-up: ``wall(1 worker) / wall(N workers)``, best of ``--repeats``. The target of
  ARCHITECTURE.md §1.2 (>= 4x on 8 cores) is judged only when this machine has at least 8
  logical CPUs; the CPU count is always printed, because the CI runners have fewer.
* Determinism: the result of every run (metrics, predictions, candidate tables) is hashed;
  all worker counts and all repeats must give the same hash (the exit code is 1 otherwise).
* ``--profile``: the same pipeline once in this process under ``cProfile``; prints the
  functions with the most own time and the time per area, to find kernels for Phase 3.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import os
import platform
import pstats
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import Future
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np

from vibechem_core.data import Axis, Results, SpectralDataset
from vibechem_engine.executor import ProcessExecutor
from vibechem_engine.pipeline import Pipeline, results_of

TARGET_SPEEDUP = 4.0
TARGET_WORKERS = 8
SNV: dict[str, Any] = {"block_id": "preprocess.snv", "params": {}}
MSC: dict[str, Any] = {"block_id": "preprocess.msc", "params": {}}
# Own time per area of the source tree, matched in order on the file name of a profiled function.
AREAS = (
    ("scikit-learn", "sklearn"),
    ("SciPy", "scipy"),
    ("NumPy", "numpy"),
    ("VibeChem blocks", "vibechem_core"),
    ("VibeChem engine", "vibechem_engine"),
)


@dataclass
class Config:
    name: str
    workers: int
    wall_s: list[float] = field(default_factory=list[float])
    digests: list[str] = field(default_factory=list[str])
    speedup: float | None = None
    startup_s: float = 0.0


def synthetic_dataset(rows: int, cols: int, seed: int) -> SpectralDataset:
    """Spectra-like rows (three bands of random height, a slope and noise) and a response
    that depends on the band heights, so every PLS fit has something to find."""
    rng = np.random.default_rng(seed)
    axis = np.linspace(1000.0, 2500.0, cols)
    unit = (axis - axis[0]) / (axis[-1] - axis[0])
    bands = np.exp(-(((unit[None, :] - np.array([0.2, 0.5, 0.75])[:, None]) / 0.04) ** 2))
    heights = rng.uniform(0.5, 1.5, size=(rows, 3))
    slope = rng.uniform(0.0, 0.3, size=(rows, 1)) * unit[None, :]
    x = heights @ bands + slope + rng.normal(0.0, 0.01, size=(rows, cols))
    y = heights @ np.array([1.0, -0.5, 2.0]) + rng.normal(0.0, 0.05, size=rows)
    return SpectralDataset(
        x,
        Axis(axis, "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(rows)],
        row_index=np.arange(rows),
        source_id="synthetic",
        y=y[:, None],
        y_columns=["y"],
        y_units=["unit"],
    )


def nested_pipeline(outer: int, inner: int, n_components: int = 10) -> Pipeline:
    """dataset -> kfold (outer folds); dataset -> pls -> nested_cv (needs the outer folds)."""
    nodes: list[dict[str, Any]] = [
        {"node_id": "src", "block_id": "data.dataset", "params": {"dataset_id": "bench"}},
        {"node_id": "folds", "block_id": "validate.kfold", "params": {"k": outer}},
        {"node_id": "pls", "block_id": "model.pls", "params": {"n_components": n_components}},
        {
            "node_id": "nest",
            "block_id": "validate.nested_cv",
            "params": {
                "search_space": [[None, SNV, MSC]],
                "inner_folds": {"block_id": "validate.kfold", "params": {"k": inner}},
            },
        },
    ]
    wires = [
        ("src", "spectra", "folds", "spectra"),
        ("src", "spectra", "pls", "spectra"),
        ("pls", "model", "nest", "model"),
        ("folds", "folds", "nest", "folds"),
    ]
    edges = [
        {"edge_id": f"e{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
        for i, (a, ap, b, bp) in enumerate(wires)
    ]
    return Pipeline({"nodes": nodes, "edges": edges})


def digest(results: Results) -> str:
    """sha256 over the metrics, predictions and candidate tables (bit for bit)."""
    h = hashlib.sha256(json.dumps(sorted(results.metrics.items()), sort_keys=True).encode())
    for table in (results.predictions, results.candidates):
        for key in sorted(table or {}):
            h.update(key.encode())
            h.update(np.ascontiguousarray((table or {})[key]).tobytes())
    return h.hexdigest()


def warm_pool(workers: int, spill_dir: Path) -> tuple[ProcessExecutor, float]:
    """A pool whose ``workers`` processes are up and have imported NumPy; also its start-up s."""
    start = time.perf_counter()
    pool = ProcessExecutor(workers, spill_dir)
    for future in [pool.submit(_ready, i) for i in range(workers * 4)]:
        future.result()
    return pool, time.perf_counter() - start


def _ready(_: int) -> int:
    time.sleep(0.2)  # long enough that every worker picks up a task, so all of them start
    return os.getpid()


def run_once(
    pipeline: Pipeline, data: SpectralDataset, pool: ProcessExecutor, seed: int
) -> tuple[float, str]:
    """Wall time of one run on a warm pool, and the result digest."""
    start = time.perf_counter()
    run = pipeline.run({"bench": data}, seed=seed, executor=pool)
    wall = time.perf_counter() - start
    if run.status != "succeeded":
        raise RuntimeError(f"run {run.status}: {dict(run.errors)}")
    return wall, digest(results_of(run, pipeline)["nest"])


class InlineExecutor:
    """Runs every task in the calling thread: what ``cProfile`` can see."""

    max_workers = 1

    def submit(self, fn: Any, /, *args: object) -> Future[Any]:
        future: Future[Any] = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as exc:  # noqa: BLE001 (handed to the caller through the future)
            future.set_exception(exc)
        return future

    def restart(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


def profile(pipeline: Pipeline, data: SpectralDataset, seed: int, top: int) -> dict[str, Any]:
    """One run in this process under cProfile: own time by area and the top functions."""
    profiler = cProfile.Profile()
    profiler.enable()
    run = pipeline.run({"bench": data}, seed=seed, executor=InlineExecutor())
    profiler.disable()
    if run.status != "succeeded":
        raise RuntimeError(f"profiled run {run.status}: {dict(run.errors)}")
    stats = pstats.Stats(profiler)
    entries = cast("dict[tuple[str, int, str], tuple[Any, ...]]", stats.stats)  # type: ignore[attr-defined]
    total = sum(v[2] for v in entries.values())
    by_area: dict[str, float] = defaultdict(float)
    for (filename, _line, _name), v in entries.items():
        path = filename.replace("\\", "/")
        area = next((a for a, key in AREAS if f"/{key}/" in path or f"/{key}." in path), "other")
        by_area[area] += v[2]
    rows = sorted(entries.items(), key=lambda kv: kv[1][2], reverse=True)[:top]
    return {
        "total_s": total,
        "by_area": {
            a: round(100 * t / total, 1) for a, t in sorted(by_area.items(), key=lambda kv: -kv[1])
        },
        "top": [
            {
                "function": f"{name} ({Path(f).name}:{line})",
                "calls": v[1],
                "own_s": round(v[2], 3),
                "own_pct": round(100 * v[2] / total, 1),
            }
            for (f, line, name), v in rows
        ],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--workers", default="1,2,4,8", help="worker counts, comma separated")
    p.add_argument("--rows", type=int, default=600)
    p.add_argument("--cols", type=int, default=800)
    p.add_argument("--outer", type=int, default=5, help="outer folds")
    p.add_argument("--inner", type=int, default=4, help="inner folds")
    p.add_argument("--repeats", type=int, default=2)
    p.add_argument("--seed", type=int, default=20261128)
    p.add_argument("--profile", action="store_true", help="also profile one run in this process")
    p.add_argument("--top", type=int, default=15, help="functions listed by --profile")
    p.add_argument("--quick", action="store_true", help="tiny data, 1 and 2 workers (smoke test)")
    p.add_argument("--json", help="write the results to this file")
    args = p.parse_args(argv)
    if args.quick:
        args.rows, args.cols, args.workers, args.repeats = 60, 80, "1,2", 1
    counts = sorted({int(w) for w in args.workers.split(",")} | {1})
    cpus = os.cpu_count() or 1

    data = synthetic_dataset(args.rows, args.cols, args.seed)
    pipeline = nested_pipeline(args.outer, args.inner)
    print(f"{platform.platform()}, {cpus} logical CPUs, Python {platform.python_version()}")
    print(
        f"nested CV {args.outer}x{args.inner}, 3 chains, {args.rows} x {args.cols}, seed {args.seed}"
    )

    configs = [Config(f"loky-{n}", n) for n in counts]
    with tempfile.TemporaryDirectory(prefix="vibechem_bench_") as spill:
        for cfg in configs:
            pool, cfg.startup_s = warm_pool(cfg.workers, Path(spill))
            try:
                for _ in range(args.repeats):
                    wall, d = run_once(pipeline, data, pool, args.seed)
                    cfg.wall_s.append(wall)
                    cfg.digests.append(d)
            finally:
                pool.shutdown()
    base = min(configs[0].wall_s)
    for cfg in configs:
        cfg.speedup = base / min(cfg.wall_s)
    all_digests = {d for cfg in configs for d in cfg.digests}
    deterministic = len(all_digests) == 1

    print(f"{'config':<9}{'start s':>9}{'best s':>9}{'speed-up':>10}   digests")
    for cfg in configs:
        same = "same" if len(set(cfg.digests)) == 1 else "DIFFERENT"
        print(
            f"{cfg.name:<9}{cfg.startup_s:>9.2f}{min(cfg.wall_s):>9.2f}{cfg.speedup or 0:>9.2f}x   {cfg.digests[0][:12]} ({same} over repeats)"
        )
    print(f"determinism (all worker counts, all repeats): {'PASS' if deterministic else 'FAIL'}")

    target = next((c for c in configs if c.workers == TARGET_WORKERS), None)
    if target is None or cpus < TARGET_WORKERS:
        verdict = f"not judged (needs {TARGET_WORKERS} workers on >= {TARGET_WORKERS} CPUs; this machine has {cpus})"
    else:
        ok = (target.speedup or 0) >= TARGET_SPEEDUP
        verdict = f"{'PASS' if ok else 'FAIL'} ({target.speedup:.2f}x at {TARGET_WORKERS} workers, target {TARGET_SPEEDUP}x)"
    print(f"speed-up target: {verdict}")

    report: dict[str, Any] = {
        "platform": platform.platform(),
        "cpus": cpus,
        "args": vars(args),
        "configs": [asdict(c) for c in configs],
        "deterministic": deterministic,
        "speedup_verdict": verdict,
    }
    if args.profile:
        report["profile"] = profile(pipeline, data, args.seed, args.top)
        print(
            f"\nprofile (one run in this process, {report['profile']['total_s']:.2f} s of own time)"
        )
        for area, pct in report["profile"]["by_area"].items():
            print(f"  {area:<18}{pct:>6.1f} %")
        for row in report["profile"]["top"]:
            print(
                f"  {row['own_pct']:>5.1f} %  {row['own_s']:>7.3f} s  {row['calls']:>8}  {row['function']}"
            )
    if args.json:
        with Path(args.json).open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
    return 0 if deterministic and not verdict.startswith("FAIL") else 1


if __name__ == "__main__":
    # loky workers re-import this module; keep the guard so they do not run the benchmark.
    sys.exit(main())
