# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_bench_transport.py
"""Tests for scripts/bench_transport.py (transport spike, TASKS.md T0.12)."""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bench_transport as bt


def test_density_raster_counts_every_point_in_the_right_cell() -> None:
    # 2 spectra x 4 points into 2 columns; y range 0..1 → bins of width 1/256.
    y = np.array([[0.0, 1.0, 0.5, 0.5], [0.0, 0.0, 1.0, 1.0]])
    counts, y_min, y_max = bt.density_raster(y, width=2)
    assert counts.shape == (2, bt.DENSITY_BINS)
    assert counts.dtype == np.uint16
    assert (y_min, y_max) == (0.0, 1.0)
    assert int(counts.sum()) == y.size
    # Column 0 holds points 0–1: three zeros (bin 0) and one maximum (top bin).
    assert counts[0, 0] == 3
    assert counts[0, -1] == 1
    # Column 1 holds points 2–3: two 0.5 values (bin 128) and two maxima.
    assert counts[1, 128] == 2
    assert counts[1, -1] == 2


def test_density_to_arrow_layout() -> None:
    x, y = bt.synthetic_spectra(30, 200, np.random.default_rng(0))
    table = pa.ipc.open_stream(bt.density_to_arrow(x, y, width=50)).read_all()
    names = table.schema.names
    assert names[:4] == ["x", "mean", "sd_lo", "sd_hi"]
    assert names[4 : 4 + bt.N_SELECTED] == [f"y_{i}" for i in range(bt.N_SELECTED)]
    assert names[-1] == "density"
    assert table.num_rows == 50
    assert table.schema.field("density").type == pa.list_(pa.uint16(), bt.DENSITY_BINS)
    assert table.schema.metadata[b"n_spectra"] == b"30"
    # Pixel column 0 averages points 0–3 (200 points / 50 columns).
    mean = np.asarray(table.column("mean").to_numpy())
    np.testing.assert_allclose(mean[0], y[:, :4].mean(), rtol=1e-6)


def test_run_reports_every_mode_through_the_secured_app() -> None:
    report = bt.run(n=20, points=200, repeats=2, width=64, node=False)
    assert [(r["client"], r["mode"]) for r in report["results"]] == [
        ("python", "lines"),
        ("python", "density"),
    ]
    for r in report["results"]:
        assert r["bytes"] > 0
        assert r["total_ms_median"] >= r["server_ms_median"] > 0
    assert "| python | density |" in bt.markdown(report)


def test_node_client_decodes_both_modes() -> None:
    report = bt.run(n=20, points=200, repeats=1, width=64, node=True)
    node = [r for r in report["results"] if r["client"] == "node"]
    assert [r["mode"] for r in node] == ["lines", "density"]
    python_bytes = {r["mode"]: r["bytes"] for r in report["results"] if r["client"] == "python"}
    assert {r["mode"]: r["bytes"] for r in node} == python_bytes


def test_spike_route_still_needs_the_session_token() -> None:
    x, y = bt.synthetic_spectra(5, 100, np.random.default_rng(1))
    with bt.serve(x, y) as (port, _token):
        url = f"http://127.0.0.1:{port}/api/v1/spike/preview?mode=lines"
        with pytest.raises(urllib.error.HTTPError) as info:
            urllib.request.urlopen(url)
        assert info.value.code == 401
        info.value.close()


@pytest.mark.parametrize(
    "argv",
    [["--points", "100", "--width", "200"], ["--width", "1"], ["--n", "1"], ["--repeats", "0"]],
)
def test_invalid_arguments_are_rejected(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        bt.main(argv)
