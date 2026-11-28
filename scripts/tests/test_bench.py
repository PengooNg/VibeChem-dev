# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_bench.py
"""Tests for scripts/bench.py (TASKS.md T2.12)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.data import Results

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bench


def test_digest_sees_every_bit_of_a_result() -> None:
    table = {"y": np.array([1.0, 2.0])}
    base = bench.digest(Results("cv", {"rmsecv": 0.5}, predictions=table))
    assert base == bench.digest(Results("cv", {"rmsecv": 0.5}, predictions=dict(table)))
    assert base != bench.digest(Results("cv", {"rmsecv": 0.5000000001}, predictions=table))
    assert base != bench.digest(
        Results("cv", {"rmsecv": 0.5}, predictions={"y": np.array([1.0, np.nextafter(2.0, 3.0)])})
    )


def test_quick_run_gives_the_same_bits_for_1_and_2_workers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "bench.json"
    assert bench.main(["--quick", "--profile", "--top", "3", "--json", str(out)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    digests = {d for c in report["configs"] for d in c["digests"]}
    assert [c["workers"] for c in report["configs"]] == [1, 2]
    assert len(digests) == 1
    assert report["deterministic"] is True
    assert report["profile"]["top"]  # the profiled run found functions
    assert "determinism" in capsys.readouterr().out
