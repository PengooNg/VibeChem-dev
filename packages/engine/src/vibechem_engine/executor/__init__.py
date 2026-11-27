# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/executor/__init__.py
"""Task executor (ARCHITECTURE.md §3.4, ADR-004; measured in ``docs/spikes/parallel.md``).

:class:`ProcessExecutor` runs tasks in a warm loky process pool. Every worker caps BLAS at
one thread, so results do not depend on the core count: the thread-count variables of
OpenBLAS, OpenMP, MKL and Accelerate are set to 1 before anything loads (this also covers
SciPy's own OpenBLAS, loaded later), and threadpoolctl caps what NumPy loaded. :meth:`ProcessExecutor.share`
saves a large array once as ``.npy``; workers open it memory-mapped instead of receiving a
pickled copy per task. :func:`task_seeds` gives each task its own seed from the run's
root seed. The scheduler (T2.08) owns the core budget and the task order; other
executors (Dask, Ray, HPC) implement :class:`Executor`.
"""
# loky and threadpoolctl ship no type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false

from __future__ import annotations

import importlib
import logging
import uuid
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self, cast

import loky
import numpy as np
from numpy.typing import NDArray
from threadpoolctl import threadpool_limits

from vibechem_engine.executor.freeze import loky_freeze_support

__all__ = [
    "SHARE_THRESHOLD_BYTES",
    "Executor",
    "MappedArray",
    "ProcessExecutor",
    "loky_freeze_support",
    "task_seeds",
]

_log = logging.getLogger(__name__)
SHARE_THRESHOLD_BYTES = 1 << 20
"""Arrays of at least this many bytes are passed to workers as memory-mapped files."""

_WORKER_ENV = dict.fromkeys(
    ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"), "1"
)
_limiter: object = None  # keeps the worker's thread limit alive for the worker's life


class Executor(Protocol):
    """What the scheduler needs from an executor."""

    @property
    def max_workers(self) -> int: ...

    def submit[R](self, fn: Callable[..., R], /, *args: object) -> Future[R]: ...

    def restart(self) -> None:
        """Kill the workers (their tasks fail) and start fresh ones: crash and cancel recovery."""
        ...

    def shutdown(self) -> None: ...


@dataclass(frozen=True)
class MappedArray:
    """A ``.npy`` file a worker opens with ``np.load(mmap_mode="r")`` (read-only)."""

    path: str


def task_seeds(root_seed: int, n_tasks: int) -> list[int]:
    """One seed per task: child *i* of ``SeedSequence(root_seed).spawn(n_tasks)``.

    Each child becomes one 53-bit ``int`` (the cache key's ``seed``; exact as a JSON number
    in the UI); a task builds its generator with ``numpy.random.default_rng(seed)``. Call it
    once per run over the whole task list in a stable order: task *i* must be the same task
    on every run, and two calls with the same root give the same seeds.
    """
    children = np.random.SeedSequence(root_seed).spawn(n_tasks)
    return [int(child.generate_state(1, np.uint64)[0] >> 11) for child in children]


def _init_worker() -> None:
    """loky initializer: cap BLAS and OpenMP at one thread in this worker."""
    global _limiter  # noqa: PLW0603
    # threadpoolctl only limits libraries already loaded (spike finding 2).
    importlib.import_module("numpy")
    _limiter = threadpool_limits(limits=1)


def _run[R](fn: Callable[..., R], args: tuple[object, ...]) -> R:
    """Worker side of :meth:`ProcessExecutor.submit`: open shared arrays, call ``fn``."""
    opened = [
        np.load(a.path, mmap_mode="r", allow_pickle=False) if isinstance(a, MappedArray) else a
        for a in args
    ]
    return fn(*opened)


class ProcessExecutor:
    """Warm loky process pool; see the module docstring.

    ``spill_dir`` holds the shared ``.npy`` files (the run's cache folder); they are
    deleted on :meth:`shutdown`. Idle workers exit after ``idle_timeout`` seconds and are
    started again on the next task.
    """

    def __init__(self, max_workers: int, spill_dir: Path, *, idle_timeout: float = 300) -> None:
        self._max_workers = max_workers
        self._spill_dir = spill_dir
        self._spilled: list[Path] = []
        self._idle_timeout = idle_timeout
        self._pool = self._new_pool()

    def _new_pool(self) -> loky.ProcessPoolExecutor:
        return loky.ProcessPoolExecutor(
            max_workers=self._max_workers,
            timeout=self._idle_timeout,
            initializer=_init_worker,
            env=_WORKER_ENV,
        )

    @property
    def max_workers(self) -> int:
        return self._max_workers

    def share(self, array: NDArray[np.generic]) -> NDArray[np.generic] | MappedArray:
        """Return ``array`` itself if small, else save it once and return its :class:`MappedArray`.

        Pass the result as a top-level task argument (inside a list or dataclass it stays a
        :class:`MappedArray`); the task receives an array either way. A small array is pickled
        when the task is sent, so do not change it in place after :meth:`submit`.
        """
        if array.nbytes < SHARE_THRESHOLD_BYTES:
            return array
        # shortcut: shared files live until shutdown, add release() once a pool serves many runs.
        self._spill_dir.mkdir(parents=True, exist_ok=True)
        path = self._spill_dir / f"shared_{uuid.uuid4().hex}.npy"
        np.save(path, array, allow_pickle=False)
        self._spilled.append(path)
        return MappedArray(str(path))

    def submit[R](self, fn: Callable[..., R], /, *args: object) -> Future[R]:
        """Run ``fn(*args)`` in a worker; :class:`MappedArray` arguments arrive memory-mapped."""
        return cast("Future[R]", self._pool.submit(_run, fn, args))

    def restart(self) -> None:
        """Kill the workers and start a new pool; running and queued tasks fail.

        Used after a worker crash (loky then refuses new tasks) and for stuck workers on
        cancel. Shared files stay.
        """
        self._pool.shutdown(wait=False, kill_workers=True)
        self._pool = self._new_pool()

    def shutdown(self, *, kill: bool = False) -> None:
        """Stop the workers and delete the shared files.

        Waits for every submitted task; ``kill`` terminates the workers instead (running and
        queued tasks then fail).
        """
        try:
            # Workers hold the memory maps open; Windows cannot delete the files before they exit.
            self._pool.shutdown(wait=True, kill_workers=kill)
        finally:
            for path in self._spilled:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    _log.warning("could not delete shared array %s", path, exc_info=True)
            self._spilled.clear()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.shutdown(kill=exc is not None)  # an error: don't run the rest of the queue
