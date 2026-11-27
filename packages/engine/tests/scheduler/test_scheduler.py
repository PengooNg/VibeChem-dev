# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/scheduler/test_scheduler.py
"""Scheduler (T2.08): dependencies, seeds, core and memory budgets, failures, cancel, events."""
# cloudpickle ships no type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import cloudpickle
import numpy as np
import pytest

from vibechem_core.errors import BlockInputError
from vibechem_engine.executor import ProcessExecutor, task_seeds
from vibechem_engine.scheduler import Job, estimate_memory, run_jobs

# Workers cannot import this test module (pytest --import-mode=importlib).
cloudpickle.register_pickle_by_value(sys.modules[__name__])


class ThreadExecutor:
    """In-process executor; ``track`` records the peak of a summed load (jobs, threads, bytes)."""

    def __init__(self, max_workers: int) -> None:
        self._pool = ThreadPoolExecutor(max_workers)
        self._max_workers = max_workers
        self._lock = threading.Lock()
        self.load: dict[str, int] = {}
        self.peak: dict[str, int] = {}

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def submit[R](self, fn: Callable[..., R], /, *args: object) -> Future[R]:
        return self._pool.submit(fn, *args)

    def shutdown(self) -> None:
        self._pool.shutdown()

    def track(self, amounts: dict[str, int], sign: int) -> None:
        with self._lock:
            for tag, amount in amounts.items():
                self.load[tag] = self.load.get(tag, 0) + sign * amount
                self.peak[tag] = max(self.peak.get(tag, 0), self.load[tag])


@pytest.fixture
def pool() -> Iterator[ThreadExecutor]:
    executor = ThreadExecutor(4)
    yield executor
    executor.shutdown()


def busy(pool: ThreadExecutor, **amounts: int) -> Callable[..., int]:
    def work(seed: int, *_: object) -> int:
        pool.track({"jobs": 1, **amounts}, 1)
        time.sleep(0.02)
        pool.track({"jobs": 1, **amounts}, -1)
        return seed

    return work


def echo(seed: int, *inputs: object) -> tuple[int, tuple[object, ...]]:
    return seed, inputs


def draw(seed: int, scale: float, *upstream: float) -> float:
    return float(np.random.default_rng(seed).normal() * scale + sum(upstream))


def fail(_seed: int, *_: object) -> None:
    raise BlockInputError("BLOCK_CONSTANT_SPECTRA", {"rows": 3})


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def __call__(self, type_: str, data: dict[str, object]) -> None:
        self.events.append((type_, data))

    def of(self, type_: str) -> list[dict[str, object]]:
        return [d for t, d in self.events if t == type_]


def test_dependency_results_follow_args_and_seeds_follow_list_position(
    pool: ThreadExecutor,
) -> None:
    jobs = [
        Job("c", "nd_c", echo, ("z",), ("a", "b")),  # listed first, runs last
        Job("a", "nd_a", echo, ("x",)),
        Job("b", "nd_b", echo, (), ("a",)),
    ]
    run = run_jobs(jobs, pool, root_seed=11)
    seeds = task_seeds(11, 3)
    a, b = run.results["a"], run.results["b"]
    assert a == (seeds[1], ("x",))
    assert b == (seeds[2], (a,))
    assert run.results["c"] == (seeds[0], ("z", a, b))
    assert (run.status, run.failed_nodes, run.unfinished_nodes) == ("succeeded", (), ())


def test_bad_job_lists_are_rejected(pool: ThreadExecutor) -> None:
    with pytest.raises(ValueError, match="unknown"):
        run_jobs([Job("a", "n", echo, deps=("zz",))], pool, root_seed=0)
    with pytest.raises(ValueError, match="cycle"):
        run_jobs(
            [Job("a", "n", echo, deps=("b",)), Job("b", "n", echo, deps=("a",))], pool, root_seed=0
        )
    with pytest.raises(ValueError, match="threads"):
        run_jobs([Job("a", "n", echo, threads=3)], pool, root_seed=0, cores=2)
    with pytest.raises(ValueError, match="repeated"):
        run_jobs([Job("a", "n", echo), Job("a", "m", echo)], pool, root_seed=0)


def test_core_budget_counts_kernel_threads(pool: ThreadExecutor) -> None:
    jobs = [Job(f"w{i}", "nd", busy(pool, threads=2), threads=2) for i in range(6)]
    jobs += [Job(f"s{i}", "nd", busy(pool, threads=1)) for i in range(4)]
    run = run_jobs(jobs, pool, root_seed=0, cores=3)
    assert run.status == "succeeded"
    assert pool.peak["threads"] == 3  # budget used, never exceeded
    assert pool.peak["jobs"] <= 3


def test_memory_budget_throttles_and_oversize_job_runs_alone(pool: ThreadExecutor) -> None:
    events = Recorder()
    jobs = [Job(f"m{i}", "nd", busy(pool, bytes=60), memory_bytes=60) for i in range(4)]
    jobs.append(Job("big", "nd_big", busy(pool, bytes=500), memory_bytes=500))
    run = run_jobs(jobs, pool, root_seed=0, memory_budget_bytes=130, emit=events)
    assert run.status == "succeeded"
    assert pool.peak["jobs"] == 2  # 2 x 60 fit in 130, a third does not
    assert pool.peak["bytes"] == 500  # the big job alone
    assert events.of("memory.throttled")[0] == {"old_workers": 4, "new_workers": 2}


def test_estimate_memory_is_inputs_plus_one_copy() -> None:
    assert estimate_memory(np.zeros((10, 5)), np.zeros(3, np.float32)) == 2 * (400 + 12)


def test_failure_skips_dependants_and_keeps_independent_branches(pool: ThreadExecutor) -> None:
    events = Recorder()
    jobs = [
        Job("a", "nd_a", echo),
        Job("b", "nd_b", fail, (), ("a",)),
        Job("c", "nd_c", echo, (), ("b",)),
        Job("d", "nd_d", echo, (), ("a",)),
    ]
    run = run_jobs(jobs, pool, root_seed=0, emit=events)
    assert run.status == "failed"
    assert set(run.results) == {"a", "d"}
    assert isinstance(run.errors["b"], BlockInputError)
    assert (run.failed_nodes, run.unfinished_nodes) == (("nd_b",), ("nd_c",))
    error = {"node_id": "nd_b", "state": "error", "code": "BLOCK_CONSTANT_SPECTRA"}
    assert any(error.items() <= e.items() for e in events.of("node.state"))
    assert events.of("run.progress")[-1]["done_tasks"] == 4


def test_cancel_stops_dispatch_and_lets_running_jobs_finish(pool: ThreadExecutor) -> None:
    cancel = threading.Event()

    def first(_seed: int) -> str:
        cancel.set()
        return "finished"

    jobs = [Job("a", "nd_a", first), Job("b", "nd_b", echo, (), ("a",))]
    run = run_jobs(jobs, pool, root_seed=0, cancel=cancel)
    assert run.status == "cancelled"
    assert run.results == {"a": "finished"}
    assert run.unfinished_nodes == ("nd_b",)


def test_node_states_and_throttled_progress(pool: ThreadExecutor) -> None:
    events = Recorder()
    jobs = [Job(f"f{i}", "nd_cv", echo) for i in range(5)] + [
        Job("m", "nd_m", echo, (), tuple(f"f{i}" for i in range(5)))
    ]
    run_jobs(jobs, pool, root_seed=0, emit=events, clock=lambda: 0.0)  # time stands still
    states = [(d["node_id"], d["state"]) for d in events.of("node.state")]
    assert states[:2] == [("nd_cv", "queued"), ("nd_m", "queued")]
    assert states.index(("nd_cv", "running")) < states.index(("nd_cv", "done"))
    assert states[-2:] == [("nd_m", "running"), ("nd_m", "done")]
    # Within one throttle interval only the first and the last update are sent.
    assert [(d["done"], d["total"]) for d in events.of("node.progress")] == [(1, 5), (5, 5)]
    assert [d["done_tasks"] for d in events.of("run.progress")] == [1, 6]


def test_results_identical_on_one_and_three_workers(tmp_path: Path) -> None:
    jobs = [Job(f"f{i}", "nd_f", draw, (float(i),)) for i in range(8)]
    jobs.append(Job("sum", "nd_sum", draw, (0.0,), tuple(f"f{i}" for i in range(8))))
    runs = []
    for workers in (1, 3):
        with ProcessExecutor(workers, tmp_path) as executor:
            runs.append(run_jobs(jobs, executor, root_seed=20261117).results)
    assert runs[0] == runs[1]
