# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_smoke_engine.py
"""Tests for scripts/smoke_engine.py, run against the unfrozen engine."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import smoke_engine

DEV_ENGINE = [sys.executable, "-m", "vibechem_engine.api"]


def test_smoke_passes_against_the_dev_engine() -> None:
    summary = smoke_engine.smoke(DEV_ENGINE, bundle_dir=None, timeout=120)
    assert "'status': 'ready'" in summary


def test_smoke_fails_when_the_engine_exits_before_announcing() -> None:
    with pytest.raises(RuntimeError, match="exited with code 3"):
        smoke_engine.smoke(
            [sys.executable, "-c", "import sys; print('log line'); sys.exit(3)"],
            bundle_dir=None,
            timeout=30,
        )


def test_smoke_fails_on_timeout() -> None:
    with pytest.raises(RuntimeError, match=r"no engine\.listening line"):
        smoke_engine.smoke(
            [sys.executable, "-c", "import time; time.sleep(30)"], bundle_dir=None, timeout=1
        )


def test_native_extension_is_found_only_in_its_package_folder(tmp_path: Path) -> None:
    (tmp_path / "_internal" / "other").mkdir(parents=True)
    (tmp_path / "_internal" / "other" / "_core.pyd").write_bytes(b"")
    assert smoke_engine.native_extension_files(tmp_path) == []
    with pytest.raises(RuntimeError, match="no vibechem_native"):
        smoke_engine.smoke(DEV_ENGINE, bundle_dir=tmp_path, timeout=1)

    native = tmp_path / "_internal" / "vibechem_native"
    native.mkdir()
    (native / "_core.cp312-win_amd64.pyd").write_bytes(b"")
    assert smoke_engine.native_extension_files(tmp_path) == [native / "_core.cp312-win_amd64.pyd"]


def test_main_reports_failure_with_exit_code_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke_engine.main(["--timeout", "5", "--", sys.executable, "-c", "pass"]) == 1
    assert "smoke test FAILED" in capsys.readouterr().err
