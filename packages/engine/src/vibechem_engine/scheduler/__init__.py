# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/scheduler/__init__.py
"""Scheduler: runs a run's jobs on an executor (ARCHITECTURE.md §2.2 step 5, §3.4-3.6).

:func:`run_jobs` dispatches every :class:`Job` whose dependencies are done, within

- the **core budget**: the ``threads`` of the running jobs add up to at most ``cores``,
  and at most ``executor.max_workers`` jobs run at once;
- the **memory budget**: the ``memory_bytes`` estimates (:func:`estimate_memory`) of the
  running jobs add up to at most ``memory_budget_bytes``. A job over the budget runs
  alone. When only memory holds a ready job back, ``memory.throttled`` is emitted.

Seeds: job *i* of the list gets seed *i* of :func:`~vibechem_engine.executor.task_seeds`,
so the dispatch order never changes a job's seed or its result. A job runs in a worker as
``fn(seed, *args, *dependency results)``. A failed job's dependants are not run;
independent branches go on. Setting ``cancel`` stops dispatching; running jobs finish, and
workers still busy ``cancel_timeout_s`` later are killed and replaced (``executor.restart``).

Recovery (§3.6), one retry per job, run alone:

- a worker dies (native crash; on Linux also an OOM kill): loky fails every running job,
  so the pool is restarted and each of them is retried, with its :class:`Fallback`
  (Python reference, ``native.fallback`` event) if it has one. Which job crashed is
  unknown, so a bystander with a fallback uses it too (same numbers by the reference tests);
- a job raises ``MemoryError``: the concurrency cap is halved (``memory.throttled``) and the
  job retried; a second ``MemoryError`` is the node error ``RUN_OUT_OF_MEMORY``.

Events (DATA_MODEL.md §3, ``emit(type, data)``; the WebSocket layer adds ``seq``):
``node.state`` (``queued`` at start, ``running``, ``done``, ``error``), ``node.progress``
(nodes with more than one job), ``run.progress``, ``memory.throttled``. Progress is sent
at most every 0.25 s per node and for the run; the last update always goes out.
``run.started`` / ``run.finished`` carry pipeline fields the caller owns; it sends them
from the returned :class:`RunResult`.
"""

from __future__ import annotations

import graphlib
import logging
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, BrokenExecutor, Future, wait
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from vibechem_core.errors import VibeChemError
from vibechem_engine.executor import Executor, task_seeds

__all__ = [
    "PROGRESS_INTERVAL_S",
    "RUN_OUT_OF_MEMORY",
    "Emit",
    "Fallback",
    "Job",
    "RunResult",
    "estimate_memory",
    "run_jobs",
]

_log = logging.getLogger(__name__)

PROGRESS_INTERVAL_S = 0.25
"""At most 4 progress events per second per node (DATA_MODEL.md §3)."""
RUN_OUT_OF_MEMORY = "RUN_OUT_OF_MEMORY"
_CANCEL_POLL_S = 0.1

type Emit = Callable[[str, dict[str, object]], None]
type RunStatus = Literal["succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class Fallback:
    """Python reference of a job's native kernel, run if the kernel takes its worker down."""

    fn: Callable[..., object]
    block_id: str
    kernel: str


@dataclass(frozen=True, slots=True)
class Job:
    """One task to run: ``fn`` must be importable by the workers (module-level)."""

    task_id: str
    node_id: str
    fn: Callable[..., object]
    args: tuple[object, ...] = ()
    deps: tuple[str, ...] = ()  # task ids; their results follow ``args``
    memory_bytes: int = 0
    threads: int = 1  # cores the job uses itself (a C++ kernel's width)
    fallback: Fallback | None = None


@dataclass(frozen=True, slots=True)
class RunResult:
    """Outcome of :func:`run_jobs`; ``unfinished_nodes`` were neither done nor failed."""

    status: RunStatus
    duration_s: float
    results: Mapping[str, object]
    errors: Mapping[str, BaseException]
    failed_nodes: tuple[str, ...]
    unfinished_nodes: tuple[str, ...]


def estimate_memory(*arrays: NDArray[np.generic]) -> int:
    """Memory estimate of a job: its input arrays plus one working copy of each."""
    # shortcut: 2 x input bytes, replace with per-block estimates if OOM throttling (T2.09) misfires.
    return 2 * sum(a.nbytes for a in arrays)


def _ignore(_type: str, _data: dict[str, object]) -> None:
    pass


def run_jobs(
    jobs: Sequence[Job],
    executor: Executor,
    *,
    root_seed: int,
    cores: int | None = None,
    memory_budget_bytes: int | None = None,
    emit: Emit = _ignore,
    cancel: threading.Event | None = None,
    cancel_timeout_s: float = 5.0,
    clock: Callable[[], float] = time.monotonic,
) -> RunResult:
    """Run ``jobs`` on ``executor``; see the module docstring.

    ``cores`` defaults to ``executor.max_workers``; ``memory_budget_bytes=None`` means no
    memory limit. Raises ``ValueError`` for a repeated task id, an unknown dependency, a
    cycle, or a job with ``threads`` outside ``1..cores``.
    """
    started = clock()
    cores = executor.max_workers if cores is None else cores
    budget = memory_budget_bytes
    by_id = {j.task_id: j for j in jobs}
    if len(by_id) != len(jobs):
        raise ValueError("repeated task_id")
    for j in jobs:
        if unknown := set(j.deps) - by_id.keys():
            raise ValueError(f"job {j.task_id!r} depends on unknown tasks {sorted(unknown)}")
        if not 1 <= j.threads <= cores:
            raise ValueError(f"job {j.task_id!r} wants {j.threads} threads, budget is {cores}")
    seeds = dict(zip(by_id, task_seeds(root_seed, len(jobs)), strict=True))
    position = {tid: i for i, tid in enumerate(by_id)}
    sorter = graphlib.TopologicalSorter({j.task_id: j.deps for j in jobs})
    sorter.prepare()  # graphlib.CycleError is a ValueError

    node_total = Counter(j.node_id for j in jobs)
    node_ok: Counter[str] = Counter()
    node_settled: Counter[str] = Counter()
    failed: dict[str, None] = {}  # failed nodes, in failure order
    started_nodes: set[str] = set()
    results: dict[str, object] = {}
    errors: dict[str, BaseException] = {}
    blocked: set[str] = set()  # failed jobs and the jobs that depend on them
    ready: list[str] = []
    running: dict[Future[object], Job] = {}
    threads_used = memory_used = 0
    settled = 0
    last_sent: dict[str | None, float] = {}  # node_id (None = run) -> time of last progress
    throttled_to: int | None = None
    limit = min(executor.max_workers, cores)  # concurrency cap, halved on a MemoryError
    retried: set[str] = set()  # jobs that used their one retry (a retry runs alone)
    crashed: set[str] = set()  # retried after a worker crash: run the fallback
    cancelled_at: float | None = None

    def requeue(job: Job, exc: BaseException) -> None:
        nonlocal limit
        _log.warning("task %s of node %s: retry alone", job.task_id, job.node_id, exc_info=exc)
        retried.add(job.task_id)
        if isinstance(exc, MemoryError):
            if limit > 1:
                emit("memory.throttled", {"old_workers": limit, "new_workers": limit // 2})
                limit //= 2
        else:
            crashed.add(job.task_id)
            if (fb := job.fallback) is not None:
                emit(
                    "native.fallback",
                    {"block_id": fb.block_id, "kernel": fb.kernel, "reason": "worker_crashed"},
                )
        ready.insert(0, job.task_id)

    def progress(key: str | None, event: str, data: dict[str, object], last: bool) -> None:
        now = clock()
        if last or now - last_sent.get(key, -PROGRESS_INTERVAL_S) >= PROGRESS_INTERVAL_S:
            last_sent[key] = now
            emit(event, data)

    def settle(job: Job) -> None:
        nonlocal settled
        settled += 1
        node_settled[job.node_id] += 1
        sorter.done(job.task_id)
        per_job_s = (clock() - started) / settled  # run throughput, also used for node ETAs
        n, total, done = job.node_id, node_total[job.node_id], node_settled[job.node_id]
        data: dict[str, object]
        if total > 1:
            eta_s = round(per_job_s * (total - done), 1)
            data = {"node_id": n, "done": done, "total": total, "eta_s": eta_s}
            progress(n, "node.progress", data, done == total)
        eta_s = round(per_job_s * (len(jobs) - settled), 1)
        data = {"done_tasks": settled, "total_tasks": len(jobs), "eta_s": eta_s}
        progress(None, "run.progress", data, settled == len(jobs))

    for node_id in node_total:
        emit("node.state", {"node_id": node_id, "state": "queued"})

    try:
        while sorter.is_active():
            cancelled = cancel is not None and cancel.is_set()
            if cancelled and cancelled_at is None:
                cancelled_at = clock()
            if not cancelled:
                # Step 1: move newly ready jobs in; dependants of a failed job settle unrun.
                for tid in sorted(sorter.get_ready(), key=position.__getitem__):
                    if blocked.intersection(by_id[tid].deps):
                        blocked.add(tid)
                        settle(by_id[tid])
                    else:
                        ready.append(tid)
                if not ready and not running:
                    continue  # settling skipped jobs made others ready
                # Step 2: start ready jobs in list order while the budgets allow (no overtaking).
                while ready:
                    job = by_id[ready[0]]
                    if running and (
                        job.task_id in retried
                        or any(j.task_id in retried for j in running.values())
                    ):
                        break  # a retry runs alone
                    if len(running) >= limit or threads_used + job.threads > cores:
                        break
                    if running and budget is not None and memory_used + job.memory_bytes > budget:
                        if len(running) < limit and throttled_to != len(running):
                            throttled_to = len(running)
                            emit(
                                "memory.throttled",
                                {"old_workers": limit, "new_workers": throttled_to},
                            )
                        break
                    ready.pop(0)
                    dep_results = [results[d] for d in job.deps]
                    fn = job.fn
                    if job.fallback is not None and job.task_id in crashed:
                        fn = job.fallback.fn
                    future = executor.submit(fn, seeds[job.task_id], *job.args, *dep_results)
                    running[future] = job
                    threads_used += job.threads
                    memory_used += job.memory_bytes
                    if job.node_id not in started_nodes:
                        started_nodes.add(job.node_id)
                        emit("node.state", {"node_id": job.node_id, "state": "running"})
            if not running:
                if cancelled:
                    break
                raise RuntimeError("scheduler stalled: no job ready or running")
            # Step 3: wait for a job to finish (polling for a cancel) and record it.
            poll = None if cancel is None else _CANCEL_POLL_S
            finished, _ = wait(running, timeout=poll, return_when=FIRST_COMPLETED)
            if (
                cancelled_at is not None
                and not finished
                and clock() - cancelled_at >= cancel_timeout_s
            ):
                _log.warning("cancel: killing %d stuck workers", len(running))
                executor.restart()
                running.clear()
                break
            broken = False
            for future in finished:
                job = running.pop(future)
                threads_used -= job.threads
                memory_used -= job.memory_bytes
                exc = future.exception()
                broken = broken or isinstance(exc, BrokenExecutor)
                if isinstance(exc, BrokenExecutor | MemoryError) and job.task_id not in retried:
                    requeue(job, exc)
                    continue
                if isinstance(exc, MemoryError):
                    error = VibeChemError(RUN_OUT_OF_MEMORY)
                    error.__cause__ = exc
                    exc = error
                if exc is None:
                    results[job.task_id] = future.result()
                    node_ok[job.node_id] += 1
                    if node_ok[job.node_id] == node_total[job.node_id]:
                        emit("node.state", {"node_id": job.node_id, "state": "done"})
                else:
                    errors[job.task_id] = exc
                    _log.error("task %s of node %s failed", job.task_id, job.node_id, exc_info=exc)
                    blocked.add(job.task_id)
                    if job.node_id not in failed:
                        failed[job.node_id] = None
                        emit("node.state", _error_state(job.node_id, exc))
                settle(job)
            if broken:
                # The pool is dead: running jobs that have not reported yet died with it.
                executor.restart()
                for job in running.values():
                    requeue(job, BrokenExecutor("worker crashed"))
                running.clear()
                threads_used = memory_used = 0
    except BaseException:
        wait(running)  # let running jobs end before the error leaves the run
        raise
    if settled < len(jobs):
        # The throttle may have held back the last update (cancel).
        emit("run.progress", {"done_tasks": settled, "total_tasks": len(jobs), "eta_s": None})

    status: RunStatus = (
        "cancelled"
        if cancel is not None and cancel.is_set() and sorter.is_active()
        else "failed"
        if failed
        else "succeeded"
    )
    unfinished = tuple(n for n in node_total if n not in failed and node_ok[n] < node_total[n])
    return RunResult(status, clock() - started, results, errors, tuple(failed), unfinished)


def _error_state(node_id: str, exc: BaseException) -> dict[str, object]:
    data: dict[str, object] = {"node_id": node_id, "state": "error"}
    if isinstance(exc, VibeChemError):
        data |= {"code": exc.code, "message_key": exc.message_key, "params": dict(exc.params)}
    return data
