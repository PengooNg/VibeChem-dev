# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_smoke_core_wheel.py
"""Tests for scripts/smoke_core_wheel.py, run against the workspace (editable) install."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import smoke_core_wheel


def test_smoke_reproduces_the_published_value_and_refuses_the_source_tree() -> None:
    assert smoke_core_wheel.main(["--allow-source"]) == 0
    assert smoke_core_wheel.main([]) == 1  # editable install: not a wheel
