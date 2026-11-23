# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_check.py
"""Unit tests for scripts/check.py with a fake command runner (no tools run)."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check

REAL_APP_SETUP_PROBLEM = check.app_setup_problem


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
    # check.main sets this for its pytest child; restore it after each test.
    monkeypatch.setenv(check.REFERENCE_LOG_ENV, "")
    monkeypatch.setattr(
        check, "app_setup_problem", lambda: None
    )  # pretend pnpm + node_modules exist
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
    assert "boundaries ......... PASS" in out
    assert "----" not in out  # no command output on success
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


def test_boundary_violation_fails_with_import_linter_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert check.main(["--fast", "--only", "core"], runner=FakeRunner(fail_on="--no-cache")) == 1
    out = capsys.readouterr().out
    assert "---- boundaries: FAIL ----" in out
    assert "boom from --no-cache" in out
    assert "boundaries ......... FAIL" in out


def test_full_run_includes_scripts_tests_and_keeps_slow_tests() -> None:
    runner = FakeRunner()
    check.main([], runner=runner)
    pytest_call = next(c for c in runner.calls if "pytest" in c)
    assert "scripts/tests" in pytest_call
    assert "not slow" not in pytest_call


def test_only_native_checks_the_native_python_wrapper_and_tests() -> None:
    runner = FakeRunner()
    assert check.main(["--fast", "--only", "native"], runner=runner) == 0
    pytest_call = next(c for c in runner.calls if "pytest" in c)
    assert "packages/native/tests" in pytest_call
    assert all("packages/native/python" in c for c in runner.calls if "pyright" in c)
    assert not any("packages/core" in arg or arg == "app" for c in runner.calls for arg in c)


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (" Test Files  1 passed (1)\n      Tests  2 passed (2)\n", "(app: 2 passed, 0 failed)"),
        ("      Tests  1 failed | 4 passed (5)\n", "(app: 4 passed, 1 failed)"),
        (
            "\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[31m1 failed\x1b[39m (1)",
            "(app: 0 passed, 1 failed)",
        ),
        ("No test files found", "(app: 0 passed, 0 failed)"),
    ],
)
def test_parse_vitest_counts(output: str, expected: str) -> None:
    assert check.parse_vitest_counts(output) == expected


def test_only_app_runs_the_three_pnpm_scripts(capsys: pytest.CaptureFixture[str]) -> None:
    runner = FakeRunner()
    assert check.main(["--fast", "--only", "app"], runner=runner) == 0
    assert [c[1:] for c in runner.calls] == [
        ["--dir", "app", "lint"],
        ["--dir", "app", "typecheck"],
        ["--dir", "app", "test"],
    ]
    out = capsys.readouterr().out
    assert "format/lint ........ PASS" in out
    assert "tests .............. PASS  (app: 0 passed, 0 failed)" in out
    assert "boundaries ......... SKIP\n" in out  # import-linter checks Python packages only
    assert "coverage ........... SKIP\n" in out


def test_full_run_merges_python_and_app_results(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main(["--fast"], runner=FakeRunner(fail_on="typecheck")) == 1
    out = capsys.readouterr().out
    assert "types .............. FAIL" in out
    assert "tests .............. PASS  (3 passed, 0 failed) (app: 0 passed, 0 failed)" in out


def test_app_without_dependencies_fails_with_hint(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(check, "app_setup_problem", lambda: "run `pnpm --dir app install`")
    runner = FakeRunner()
    assert check.main(["--only", "app"], runner=runner) == 1
    assert runner.calls == []
    assert "tests .............. FAIL  (run `pnpm --dir app install`)" in capsys.readouterr().out


def _which_found(name: str) -> str:
    return name


def _which_missing(_name: str) -> None:
    return None


def test_app_setup_problem_detects_missing_node_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(check.shutil, "which", _which_found)
    problem = REAL_APP_SETUP_PROBLEM()
    assert problem is not None
    assert "pnpm --dir app install" in problem
    (tmp_path / "app" / "node_modules").mkdir(parents=True)
    assert REAL_APP_SETUP_PROBLEM() is None
    monkeypatch.setattr(check.shutil, "which", _which_missing)
    assert "corepack enable" in (REAL_APP_SETUP_PROBLEM() or "")


def test_no_tests_collected_is_skip_not_fail(capsys: pytest.CaptureFixture[str]) -> None:
    def runner(args: Sequence[str]) -> check.CommandResult:
        code = check.PYTEST_NO_TESTS_COLLECTED if "pytest" in args else 0
        return check.CommandResult(code, "1 deselected in 0.01s")

    assert check.main(["--fast", "--only", "core"], runner=runner) == 0
    assert "tests .............. SKIP  (no tests collected)" in capsys.readouterr().out


def _row(method: str, actual: float, *, passed: bool) -> dict[str, object]:
    return {
        "method": method,
        "dataset": "hand calculation",
        "expected": 2.0,
        "actual": actual,
        "difference": actual - 2.0,
        "rtol": 0.0,
        "atol": 1e-9,
        "source": "worked example",
        "passed": passed,
    }


def _reference_runner(rows: Sequence[dict[str, object]]) -> FakeRunner:
    """A fake runner whose pytest call writes ``rows`` like ``assert_reference`` does."""

    class Runner(FakeRunner):
        def __call__(self, args: Sequence[str]) -> check.CommandResult:
            if "pytest" in args:
                log = Path(os.environ[check.REFERENCE_LOG_ENV])
                log.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            return super().__call__(args)

    return Runner()


def test_reference_report_lists_rows_sorted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _reference_runner([_row("SNV", 2.0, passed=True), _row("MSC", 2.0, passed=True)])
    assert check.main(["--fast"], runner=runner) == 0
    assert "reference report ... PASS  (2/2 within tolerance)" in capsys.readouterr().out
    report = (tmp_path / "reports" / "reference_report.md").read_text(encoding="utf-8")
    assert report.index("| MSC |") < report.index("| SNV |")
    assert (
        "| SNV | hand calculation | 2 | 2 | 0 | rtol=0, atol=1e-09 | worked example | PASS |"
        in report
    )


def test_reference_value_outside_tolerance_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _reference_runner([_row("SNV", 2.0, passed=True), _row("PLS", 2.5, passed=False)])
    assert check.main(["--fast"], runner=runner) == 1
    out = capsys.readouterr().out
    assert "reference report ... FAIL  (1/2 within tolerance)" in out
    assert "outside tolerance: PLS on hand calculation: VibeChem 2.5, expected 2.0" in out
    report = (tmp_path / "reports" / "reference_report.md").read_text(encoding="utf-8")
    assert "| PLS | hand calculation | 2 | 2.5 | 0.5 |" in report
    assert report.index("| PLS |") < report.index("| SNV |")


def _coverage_runner(tmp_path: Path, lines: dict[str, tuple[int, int]]) -> FakeRunner:
    """A fake runner whose pytest call writes a pytest-cov JSON report."""
    files = {
        name: {"summary": {"covered_lines": c, "num_statements": n}}
        for name, (c, n) in lines.items()
    }

    class Runner(FakeRunner):
        def __call__(self, args: Sequence[str]) -> check.CommandResult:
            if "pytest" in args:
                path = tmp_path / check.COVERAGE_JSON
                path.write_text(json.dumps({"files": files}), encoding="utf-8")
            return super().__call__(args)

    return Runner()


def test_coverage_per_package_with_thresholds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _coverage_runner(
        tmp_path,
        {
            "packages\\core\\src\\vibechem_core\\a.py": (9, 10),
            "packages/core/src/vibechem_core/b.py": (10, 10),
            "packages/engine/src/vibechem_engine/__init__.py": (2, 2),
            "packages/native/python/vibechem_native/__init__.py": (1, 3),
        },
    )
    assert check.main(["--fast"], runner=runner) == 0
    assert (
        "coverage ........... PASS  core 95% | engine 100% | native 33%" in capsys.readouterr().out
    )
    pytest_call = next(c for c in runner.calls if "pytest" in c)
    assert "--cov=vibechem_core" in pytest_call
    assert "--cov-report=json:reports/coverage.json" in pytest_call


def test_coverage_below_threshold_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # 179/200 = 89.5 % is floored to 89 % (< 90 %), never rounded up to 90 %.
    runner = _coverage_runner(tmp_path, {"packages/core/src/vibechem_core/a.py": (179, 200)})
    assert check.main(["--fast", "--only", "core"], runner=runner) == 1
    out = capsys.readouterr().out
    assert "coverage ........... FAIL  core 89%" in out
    assert "core 89% is below the 90% threshold" in out


def test_coverage_without_data_is_skip(capsys: pytest.CaptureFixture[str]) -> None:
    assert check.main(["--fast", "--only", "engine"], runner=FakeRunner()) == 0
    assert "coverage ........... SKIP  (no coverage data" in capsys.readouterr().out


def test_reference_report_escapes_table_cells(tmp_path: Path) -> None:
    row = {**_row("norm |r|", 2.0, passed=True), "source": "Eq. 3\nTable 2"}
    assert check.main(["--fast"], runner=_reference_runner([row])) == 0
    report = (tmp_path / "reports" / "reference_report.md").read_text(encoding="utf-8")
    assert r"| norm \|r\| | hand calculation |" in report
    assert "| Eq. 3 Table 2 | PASS |" in report


def test_only_run_checks_references_but_keeps_the_committed_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _reference_runner([_row("PLS", 2.5, passed=False)])
    assert check.main(["--fast", "--only", "core"], runner=runner) == 1
    assert "reference report ... FAIL  (0/1 within tolerance)" in capsys.readouterr().out
    assert not (tmp_path / "reports" / "reference_report.md").exists()


def test_coverage_package_without_measured_files_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = _coverage_runner(tmp_path, {".venv/site-packages/vibechem_engine/x.py": (0, 50)})
    assert check.main(["--fast", "--only", "engine"], runner=runner) == 1
    out = capsys.readouterr().out
    assert "coverage ........... FAIL  engine no data" in out
    assert "no measured files under packages/engine/src" in out


def test_no_reference_rows_writes_placeholder_report(tmp_path: Path) -> None:
    assert check.main(["--fast"], runner=FakeRunner()) == 0
    report = (tmp_path / "reports" / "reference_report.md").read_text(encoding="utf-8")
    assert report.endswith("No reference tests yet.\n")
