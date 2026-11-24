# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_bench_parallel.py
"""Tests for scripts/bench_parallel.py (parallel spike, TASKS.md T0.13) and the
``--entry``/``--name`` options of scripts/build_engine.py."""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import loky
import loky.backend.resource_tracker
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bench_parallel as bp


@pytest.fixture
def matrix_path(tmp_path: Path) -> str:
    path = tmp_path / "matrix.npy"
    np.save(path, bp.synthetic_matrix(60, 20, np.random.default_rng(0)))
    return str(path)


def test_task_result_depends_only_on_its_seed(matrix_path: str) -> None:
    first = [bp.run_task(t) for t in bp.make_tasks(3, 7, matrix_path)]
    again = [bp.run_task(t) for t in bp.make_tasks(3, 7, matrix_path)]
    other_seed = [bp.run_task(t) for t in bp.make_tasks(3, 8, matrix_path)]
    assert [r.digest for r in first] == [r.digest for r in again]
    assert len({r.digest for r in first}) == 3  # spawned children differ
    assert {r.digest for r in first}.isdisjoint(r.digest for r in other_seed)


def test_memory_map_and_array_give_the_same_bits(matrix_path: str) -> None:
    mapped = bp.run_task(bp.make_tasks(1, 7, matrix_path)[0])
    array = bp.run_task(bp.make_tasks(1, 7, np.load(matrix_path))[0])
    assert mapped.memmapped
    assert not array.memmapped
    assert mapped.digest == array.digest


def test_loky_workers_match_serial_and_limit_blas(matrix_path: str) -> None:
    tasks = bp.make_tasks(6, 7, matrix_path)
    serial = bp.run_serial("serial", tasks, 1, 1, "")
    pool = bp.run_loky("loky-2", tasks, 2, 1, 2, serial.digest)
    assert pool.repeatable
    assert pool.same_as_serial
    assert pool.digest == serial.digest
    assert 1 <= pool.distinct_pids <= 2
    assert pool.blas_threads_seen in ([1], [0])  # 0: no BLAS library reported
    assert pool.memmapped
    assert len(pool.wall_s) == 2


def test_record_flags_a_digest_that_differs_from_the_reference(matrix_path: str) -> None:
    results = [bp.run_task(t) for t in bp.make_tasks(2, 7, matrix_path)]
    config = bp.ConfigResult(name="x", workers=0, blas="1", startup_s=None)
    bp.record(config, 1.0, results, "not-the-reference")
    assert config.repeatable
    assert not config.same_as_serial


def test_freeze_support_does_nothing_when_not_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "argv", ["x", "-m", "loky.backend.popen_loky_posix"])
    bp.loky_freeze_support()  # returns, no SystemExit


def test_freeze_support_ignores_a_normal_frozen_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["bundle", "--workers", "2"])
    bp.loky_freeze_support()


def test_freeze_support_routes_the_resource_tracker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[int, bool]] = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["bundle", "-c", "from loky.backend.resource_tracker import main; main(5, False)"],
    )
    monkeypatch.setattr(loky.backend.resource_tracker, "main", lambda fd, v: calls.append((fd, v)))
    with pytest.raises(SystemExit):
        bp.loky_freeze_support()
    assert calls == [(5, False)]


def test_freeze_support_leaves_other_c_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["bundle", "-c", "import os; os.remove('x')"])
    bp.loky_freeze_support()  # not loky's command: no exec, no exit


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX worker command line")
def test_freeze_support_routes_a_posix_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        sys, "argv", ["bundle", "-m", "loky.backend.popen_loky_posix", "--pipe", "9"]
    )
    monkeypatch.setattr(
        bp.runpy, "run_module", lambda name, **_: seen.append((name, list(sys.argv)))
    )
    with pytest.raises(SystemExit):
        bp.loky_freeze_support()
    assert seen == [("loky.backend.popen_loky_posix", ["bundle", "--pipe", "9"])]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows worker command line")
def test_freeze_support_routes_a_windows_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    import loky.backend.popen_loky_win32 as win  # noqa: PLC0415

    seen: list[tuple[int, int | None]] = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["bundle", "--multiprocessing-fork", "1234"])
    monkeypatch.setattr(win, "main", lambda handle, parent_pid: seen.append((handle, parent_pid)))
    bp.loky_freeze_support()
    assert seen == [(1234, bp.os.getppid())]


def test_parse_args_validates_workers() -> None:
    assert bp.parse_args(["--workers", "4,1,2,2"]).workers == [1, 2, 4]
    with pytest.raises(SystemExit):
        bp.parse_args(["--workers", "two"])
    with pytest.raises(SystemExit):
        bp.parse_args(["--workers", "0"])


def test_markdown_lists_every_config(matrix_path: str) -> None:
    tasks = bp.make_tasks(2, 7, matrix_path)
    config = bp.run_serial("serial", tasks, 1, 1, "")
    report = {
        "platform": "test",
        "frozen": False,
        "loky_cpu_count": loky.cpu_count(),
        "loky_physical_cores": 1,
        "configs": [{**bp.asdict(config), "median_s": 1.0, "speedup": 1.0}],
    }
    text = bp.markdown(report)
    assert "| serial | in-process | 1 |" in text
    assert text.isascii()


@pytest.mark.skipif(
    importlib.util.find_spec("vibechem_native._core") is None, reason="native extension not built"
)
def test_build_engine_freezes_another_entry_with_the_same_options() -> None:
    import build_engine  # noqa: PLC0415

    default = build_engine.pyinstaller_args()
    spike = build_engine.pyinstaller_args(Path("bench.py"), "spike")
    assert spike[:3] == ["bench.py", "--name", "spike"]
    assert spike[3:] == default[3:]
