# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_check.py
"""Unit tests for scripts/check.py with a fake command runner (no tools run)."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check


class FakeRunner:
    """Records commands; fails those containing ``fail_on`` and prints ``pytest_output``."""

    def __init__(self, fail_on: str | None = None, pytest_output: str = "3 passed in 0.1s") -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on
        self.pytest_output = pytest_output

    def __call__(self, args: Sequence[str]) -> check.CommandResult:
        self.calls.append(list(args))
        output = self.pytest_output if "pytest" in args else "ok"
        if self.fail_on is not None and self.fail_on in args:
            return check.CommandResult(1, f"{output}\nboom from {self.fail_on}")
        return check.CommandResult(0, output)


@pytest.fixture(autouse=True)
def tmp_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    log = tmp_path / "reports" / "check.log"
    monkeypatch.setattr(check, "LOG_PATH", log)
    monkeypatch.setattr(check, "ROOT", tmp_path)
    return log


def test_summary_line_aligns_status_at_column_21() -> None:
    assert check.summary_line("types", "PASS") == "types .............. PASS"
    assert check.summary_line("reference report", "SKIP", "(x)") == "reference report ... SKIP  (x)"


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("30 passed, 13 subtests passed in 0.08s", "(30 passed, 0 failed)"),
        ("2 failed, 5 passed, 1 deselected in 1s", "(5 passed, 2 failed)"),
        ("1 passed, 1 error in 1s", "(1 passed, 0 failed, 1 errors)"),
        ("no tests ran", "(0 passed, 0 failed)"),
    ],
)
def test_parse_pytest_counts(output: str, expected: str) -> None:
    assert check.parse_pytest_counts(output) == expected


def test_all_pass_prints_summary_only_and_writes_log(
    tmp_log: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert check.main(["--fast"], runner=FakeRunner()) == 0
    out = capsys.readouterr().out
    assert out.startswith("VibeChem health summary\nformat/lint ........ PASS\n")
    assert "tests .............. PASS  (3 passed, 0 failed)" in out
    assert "boundaries ......... SKIP" in out
    assert "----" not in out  # no command output on success
    assert "note: native not set up yet, arrives in T0.05" in out
    assert "ruff" in tmp_log.read_text(encoding="utf-8")


def test_failure_sets_exit_code_and_prints_failed_output_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check.main([], runner=FakeRunner(fail_on="pyright")) == 1
    out = capsys.readouterr().out
    assert "---- types: FAIL ----" in out
    assert "boom from pyright" in out
    assert "---- format/lint" not in out
    assert "types .............. FAIL" in out


def test_verbose_prints_every_command_output(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main(["--verbose"], runner=FakeRunner()) == 0
    out = capsys.readouterr().out
    assert "---- format/lint: PASS ----" in out
    assert "---- tests: PASS ----" in out


def test_fast_deselects_slow_tests_and_only_limits_paths() -> None:
    runner = FakeRunner()
    check.main(["--fast", "--only", "core"], runner=runner)
    pytest_call = next(c for c in runner.calls if "pytest" in c)
    assert pytest_call[-2:] == ["-m", "not slow"]
    assert "packages/core/tests" in pytest_call
    assert not any("engine" in arg or "scripts" in arg for c in runner.calls for arg in c)


def test_full_run_includes_scripts_tests_and_keeps_slow_tests() -> None:
    runner = FakeRunner()
    check.main([], runner=runner)
    pytest_call = next(c for c in runner.calls if "pytest" in c)
    assert "scripts/tests" in pytest_call
    assert "not slow" not in pytest_call


def test_area_not_set_up_skips_everything_without_running_tools(
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = FakeRunner()
    assert check.main(["--only", "app"], runner=runner) == 0
    assert runner.calls == []
    out = capsys.readouterr().out
    assert "tests .............. SKIP  (app not set up yet, arrives in T0.04)" in out
