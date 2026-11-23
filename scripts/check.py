# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/check.py
"""Local quality check: format, lint, types, tests; prints the health summary.

Usage::

    uv run python scripts/check.py [--fast] [--only AREA] [--verbose]

``--fast`` skips tests marked ``slow``. ``--only`` limits the run to one area
(``core``, ``engine``, ``native``, ``app``); without it every area runs, plus the
tests of ``scripts/``. By default only the health summary (QA.md §4) and the
output of failed checks are printed; ``--verbose`` prints every command's output.
The full log is always written to ``reports/check.log``.

Checks that need tooling from later steps print ``SKIP`` with the step that adds
them; ``SKIP`` does not fail the run. Exit codes: 0 all PASS/SKIP · 1 any FAIL.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "reports" / "check.log"
FAILURE_TAIL_LINES = 40
PYTEST_NO_TESTS_COLLECTED = 5  # pytest exit code: nothing collected or everything deselected

# Python source and test folders per area. Areas without folders are not set up yet.
PYTHON_AREAS: dict[str, tuple[str, ...]] = {
    "core": ("packages/core/src", "packages/core/tests"),
    "engine": ("packages/engine/src", "packages/engine/tests"),
}
NOT_SET_UP: dict[str, str] = {"native": "T0.05", "app": "T0.04"}
AREAS = (*PYTHON_AREAS, *NOT_SET_UP)
SCRIPTS_PATHS = ("scripts",)

# Summary lines after "tests" whose tooling arrives in a later step.
LATER_CHECKS: tuple[tuple[str, str], ...] = (
    ("reference report", "T0.07"),
    ("leakage suite", "T2.05"),
    ("golden pipeline", "T2.13"),
    ("coverage", "T0.07"),
)
SUMMARY_ORDER = ("format/lint", "types", "boundaries", "tests", *(n for n, _ in LATER_CHECKS))


@dataclass(frozen=True)
class CommandResult:
    """Return code and combined stdout/stderr of one command."""

    returncode: int
    output: str


@dataclass(frozen=True)
class SectionResult:
    """Outcome of one summary line."""

    name: str
    status: str  # "PASS", "FAIL" or "SKIP"
    detail: str = ""
    output: str = ""


Runner = Callable[[Sequence[str]], CommandResult]


def run_command(args: Sequence[str]) -> CommandResult:
    """Run ``args`` from the repository root and capture its output."""
    proc = subprocess.run(  # fixed tool commands, no shell
        list(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return CommandResult(proc.returncode, proc.stdout + proc.stderr)


def tool(*args: str) -> list[str]:
    """Command line for a Python tool installed in the current environment."""
    return [sys.executable, "-m", *args]


def summary_line(name: str, status: str, detail: str = "") -> str:
    """One aligned line of the health summary, e.g. ``types .............. PASS``."""
    line = f"{name} {'.' * (19 - len(name))} {status}"
    return f"{line}  {detail}" if detail else line


def parse_pytest_counts(output: str) -> str:
    """Return ``(N passed, M failed)`` from pytest's final summary line."""
    counts: dict[str, int] = {}
    for number, word in re.findall(r"(\d+) (passed|failed|errors?|deselected)\b", output):
        key = "errors" if word.startswith("error") else word
        counts[key] = counts.get(key, 0) + int(number)
    text = f"{counts.get('passed', 0)} passed, {counts.get('failed', 0)} failed"
    if counts.get("errors"):
        text += f", {counts['errors']} errors"
    return f"({text})"


def run_section(
    name: str, commands: Sequence[Sequence[str]], runner: Runner, detail: str = ""
) -> SectionResult:
    """Run commands in order; the section fails if any command fails."""
    outputs: list[str] = []
    failed = False
    for args in commands:
        result = runner(args)
        outputs.append(f"$ {' '.join(args)}\n{result.output}")
        failed = failed or result.returncode != 0
    return SectionResult(name, "FAIL" if failed else "PASS", detail, "\n".join(outputs))


def run_checks(areas: Sequence[str], *, fast: bool, runner: Runner) -> list[SectionResult]:
    """Run every summary section for ``areas`` (``scripts`` is a pseudo-area)."""
    paths = [p for a in areas for p in PYTHON_AREAS.get(a, ())]
    if "scripts" in areas:
        paths += SCRIPTS_PATHS
    if not paths:
        reason = "; ".join(not_set_up_notes(areas))
        return [SectionResult(name, "SKIP", f"({reason})") for name in SUMMARY_ORDER]

    results = [
        run_section(
            "format/lint",
            [tool("ruff", "format", "--check", *paths), tool("ruff", "check", *paths)],
            runner,
        ),
        run_section("types", [tool("pyright", *paths)], runner),
        SectionResult("boundaries", "SKIP", "(import-linter arrives in T0.07)"),
    ]

    test_paths = [p for p in paths if p.endswith("tests")] + [
        f"{p}/tests" for p in paths if p in SCRIPTS_PATHS
    ]
    pytest_args = tool("pytest", "-q", *test_paths)
    if fast:
        pytest_args += ["-m", "not slow"]
    result = runner(pytest_args)
    output = f"$ {' '.join(pytest_args)}\n{result.output}"
    if result.returncode == PYTEST_NO_TESTS_COLLECTED:
        results.append(SectionResult("tests", "SKIP", "(no tests collected)", output))
    else:
        status = "FAIL" if result.returncode != 0 else "PASS"
        results.append(SectionResult("tests", status, parse_pytest_counts(output), output))
    results += [SectionResult(name, "SKIP", f"(arrives in {step})") for name, step in LATER_CHECKS]
    return results


def not_set_up_notes(areas: Sequence[str]) -> list[str]:
    """``<area> not set up yet, arrives in <step>`` for each requested area without code."""
    return [f"{a} not set up yet, arrives in {NOT_SET_UP[a]}" for a in areas if a in NOT_SET_UP]


def format_summary(results: Sequence[SectionResult]) -> str:
    """The health summary block from QA.md §4."""
    lines = ["VibeChem health summary"]
    lines += [summary_line(r.name, r.status, r.detail) for r in results]
    return "\n".join(lines)


def tail(text: str, n: int = FAILURE_TAIL_LINES) -> str:
    """Last ``n`` lines of ``text``."""
    return "\n".join(text.rstrip().splitlines()[-n:])


def main(argv: Sequence[str] | None = None, runner: Runner = run_command) -> int:
    """Command-line entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(
        description="VibeChem local quality check (health summary, QA.md §4)"
    )
    parser.add_argument("--fast", action="store_true", help="skip tests marked slow")
    parser.add_argument("--only", choices=AREAS, help="check one area only")
    parser.add_argument("--verbose", action="store_true", help="print every command's output")
    args = parser.parse_args(argv)

    areas = [args.only] if args.only else [*AREAS, "scripts"]
    results = run_checks(areas, fast=args.fast, runner=runner)
    summary = format_summary(results)

    log_parts = [f"## {r.name}: {r.status}\n{r.output}" for r in results if r.output]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n\n".join([*log_parts, summary]) + "\n", encoding="utf-8")

    for r in results:
        if r.output and (args.verbose or r.status == "FAIL"):
            shown = r.output if args.verbose else tail(r.output)
            print(f"---- {r.name}: {r.status} ----\n{shown}\n")
    print(summary)
    for note in not_set_up_notes(areas) if len(areas) > 1 else []:
        print(f"note: {note}")
    print(f"Full log: {LOG_PATH.relative_to(ROOT).as_posix()}")
    return 1 if any(r.status == "FAIL" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
