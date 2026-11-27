# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/executor/test_executor.py
"""Executor (T2.07): warm workers, memory-mapped inputs, per-task seeds, BLAS = 1."""
# cloudpickle and threadpoolctl ship no type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import cloudpickle
import numpy as np
import pytest
from numpy.typing import NDArray
from threadpoolctl import threadpool_info, threadpool_limits

from vibechem_engine.executor import MappedArray, ProcessExecutor, task_seeds

# Workers cannot import this test module (pytest --import-mode=importlib): send its
# task functions by value.
cloudpickle.register_pickle_by_value(sys.modules[__name__])


def worker_facts(_: int) -> tuple[int, int, str | None]:
    """pid, largest BLAS thread count, VECLIB_MAXIMUM_THREADS in this worker."""
    blas = max(
        (int(lib["num_threads"]) for lib in threadpool_info() if lib["user_api"] == "blas"),
        default=0,
    )
    return os.getpid(), blas, os.environ.get("VECLIB_MAXIMUM_THREADS")


def is_memmap(matrix: NDArray[np.float64]) -> tuple[bool, float]:
    return isinstance(matrix, np.memmap), float(matrix.sum())


def ridge_digest(matrix: NDArray[np.float64], seed: int) -> str:
    """Fold-like task: seeded 80 % row draw, ridge solve; SHA-256 of the coefficients."""
    rng = np.random.default_rng(seed)
    rows, cols = matrix.shape
    picked = np.sort(rng.choice(rows, size=int(0.8 * rows), replace=False))
    x: NDArray[np.float64] = np.asarray(matrix[picked])
    y = x @ rng.normal(size=cols) + rng.normal(0.0, 0.1, size=picked.size)
    coef = np.linalg.solve(x.T @ x + 1e-3 * np.eye(cols), x.T @ y)
    return hashlib.sha256(coef.tobytes()).hexdigest()


@pytest.fixture(scope="module")
def matrix() -> NDArray[np.float64]:
    return np.random.default_rng(7).normal(size=(600, 300))  # 1.4 MB: above the threshold


def test_workers_stay_warm_with_one_blas_thread(tmp_path: Path) -> None:
    with ProcessExecutor(2, tmp_path) as executor:
        first = [executor.submit(worker_facts, i).result() for i in range(6)]
        second = [executor.submit(worker_facts, i).result() for i in range(6)]
    pids = {pid for pid, _, _ in first}
    assert pids == {pid for pid, _, _ in second}  # same processes, no respawn
    assert len(pids) <= 2
    assert os.getpid() not in pids
    # threadpoolctl sees OpenBLAS (capped at 1); it cannot see macOS Accelerate (env cap).
    allowed = {0, 1} if sys.platform == "darwin" else {1}
    assert all(blas in allowed for _, blas, _ in first + second)
    assert all(veclib == "1" for _, _, veclib in first + second)


def test_large_inputs_arrive_memory_mapped(tmp_path: Path, matrix: NDArray[np.float64]) -> None:
    with ProcessExecutor(1, tmp_path) as executor:
        shared = executor.share(matrix)
        small = executor.share(matrix[:10])
        assert isinstance(shared, MappedArray)
        assert isinstance(small, np.ndarray)
        mapped, total = executor.submit(is_memmap, shared).result()
        assert executor.submit(is_memmap, small).result()[0] is False
    assert mapped
    assert total == pytest.approx(float(matrix.sum()))
    assert list(tmp_path.iterdir()) == []  # spill files removed on shutdown


def test_task_seeds_are_spawned_children_of_the_root_seed() -> None:
    seeds = task_seeds(20261117, 4)
    children = np.random.SeedSequence(20261117).spawn(4)
    assert seeds == [int(c.generate_state(1, np.uint64)[0]) for c in children]
    assert len(set(seeds)) == 4
    assert task_seeds(20261117, 4) == seeds


def test_results_identical_on_1_and_3_workers_and_in_process(
    tmp_path: Path, matrix: NDArray[np.float64]
) -> None:
    seeds = task_seeds(20261117, 9)
    with threadpool_limits(limits=1, user_api="blas"):
        reference = [ridge_digest(matrix, seed) for seed in seeds]
    results: dict[int, list[str]] = {}
    for workers in (1, 3):
        with ProcessExecutor(workers, tmp_path / str(workers)) as executor:
            shared = executor.share(matrix)
            futures = [executor.submit(ridge_digest, shared, seed) for seed in seeds]
            results[workers] = [f.result() for f in futures]
    assert results[1] == reference
    assert results[3] == reference
    assert len(set(reference)) == 9  # the seeds really differ per task
