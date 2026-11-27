# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_quiet_hooks.py
"""Unit tests for .claude/hooks/quiet_tests.py and run_quiet.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "hooks"))

import quiet_tests
import run_quiet


def test_wrap_matches_only_plain_allowed_commands() -> None:
    assert quiet_tests.wrap("uv run pytest scripts/tests -q") == (
        quiet_tests.WRAPPER + "uv run pytest scripts/tests -q"
    )
    assert quiet_tests.wrap("uv run python scripts/check.py --fast") is not None
    assert quiet_tests.wrap("pnpm --dir app test") is not None
    assert quiet_tests.wrap("git status") is None
    assert quiet_tests.wrap("uv run python scripts/merge_step.py 5") is None
    assert quiet_tests.wrap("uv run pytest x; rm -rf y") is None
    assert quiet_tests.wrap("uv run pytest $(evil)") is None
    assert quiet_tests.wrap("uv run pytest x | tail") is None


def test_run_quiet_refuses_other_commands() -> None:
    # The wrapper's allowlist is the guard for the rewritten command (the gate judged the original).
    assert run_quiet.main(["--", "git", "push", "--force", "origin", "main"]) == 2
    assert run_quiet.main(["--", "uv", "run", "python", "scripts/merge_step.py", "1"]) == 2
    assert run_quiet.main(["--", "gh", "pr", "merge", "1"]) == 2


def test_run_quiet_keeps_exit_code_and_failure_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(run_quiet, "LOG_DIR", tmp_path)
    test = tmp_path / "test_x.py"
    test.write_text(
        "def test_ok():\n    pass\n\ndef test_bad():\n    assert 1 == 2\n", encoding="utf-8"
    )
    code = run_quiet.main(["--", "uv", "run", "pytest", str(test), "-q", "-p", "no:cacheprovider"])
    out = capsys.readouterr().out
    assert code == 1
    assert "FAILED" in out
    assert out.rstrip().endswith("exit=1 · full log: .cache/test-logs/latest.log")
    assert "test_bad" in (tmp_path / "latest.log").read_text(encoding="utf-8")


def test_shorten_keeps_health_summary_verbatim() -> None:
    lines = ["noise"] * 20 + [
        run_quiet.SUMMARY_START,
        "tests ... PASS",
        run_quiet.SUMMARY_END,
        "Full log: x",
    ]
    assert run_quiet.shorten(lines) == [
        run_quiet.SUMMARY_START,
        "tests ... PASS",
        run_quiet.SUMMARY_END,
        "Full log: x",
    ]
