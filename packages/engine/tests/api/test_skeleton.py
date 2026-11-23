# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/api/test_skeleton.py
"""``POST /skeleton/run`` (DATA_MODEL.md §2.12) and its SNV / decimation helpers."""
# pyarrow has no type information (see vibechem_engine/api/arrow.py).
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from numpy.typing import NDArray

from vibechem_core.reference_datasets import load_reference_dataset
from vibechem_core.testing import assert_close
from vibechem_engine.api.arrow import ARROW_STREAM
from vibechem_engine.api.skeleton import decimate_minmax, snv

RUN = "/api/v1/skeleton/run"


def read_arrow(content: bytes) -> dict[str, NDArray[np.float32]]:
    """Decode an Arrow IPC stream; check every column is float32."""
    table = pa.ipc.open_stream(content).read_all()
    assert all(field.type == pa.float32() for field in table.schema)
    columns: dict[str, NDArray[np.float32]] = {
        name: table.column(name).to_numpy() for name in table.column_names
    }
    return columns


# --- SNV -------------------------------------------------------------------------------


def test_snv_hand_computed_values() -> None:
    # [1, 2, 3]: mean 2, sample SD 1 → [-1, 0, 1]; [2, 4, 6, 8]: mean 5, SD sqrt(20/3).
    spectra = np.array([[1.0, 2.0, 3.0], [10.0, 20.0, 30.0]])
    assert_close(
        snv(spectra), np.array([[-1.0, 0.0, 1.0], [-1.0, 0.0, 1.0]]), rtol=1e-12, atol=1e-12
    )
    sd = np.sqrt(20.0 / 3.0)
    expected = np.array([[-3.0, -1.0, 1.0, 3.0]]) / sd
    assert_close(snv(np.array([[2.0, 4.0, 6.0, 8.0]])), expected, rtol=1e-12, atol=0)


@given(
    st.lists(
        st.lists(st.floats(-1e3, 1e3), min_size=3, max_size=30).filter(lambda r: np.ptp(r) > 1e-3),
        min_size=1,
        max_size=5,
    ).filter(lambda rows: len({len(r) for r in rows}) == 1)
)
def test_snv_rows_have_zero_mean_and_unit_sd(rows: list[list[float]]) -> None:
    out = snv(np.array(rows))
    assert_close(out.mean(axis=1), np.zeros(len(rows)), rtol=0, atol=1e-9)
    assert_close(out.std(axis=1, ddof=1), np.ones(len(rows)), rtol=1e-9, atol=0)


# --- decimation ------------------------------------------------------------------------


def test_decimate_is_a_no_op_when_points_fit() -> None:
    x = np.arange(10.0)
    y = np.arange(20.0).reshape(2, 10)
    x_out, y_out = decimate_minmax(x, y, width=10)
    assert x_out is x
    assert y_out is y


def test_decimate_keeps_extrema_in_order_of_occurrence() -> None:
    x = np.arange(8.0)
    y = np.array([[0.0, 5.0, 1.0, 2.0, 9.0, -3.0, 4.0, 4.0]])
    x_out, y_out = decimate_minmax(x, y, width=4)  # 2 buckets of 4 points
    assert x_out.tolist() == [0.0, 3.0, 4.0, 7.0]
    assert y_out.tolist() == [[0.0, 5.0, 9.0, -3.0]]


@given(st.integers(2, 600), st.integers(64, 300))
def test_decimate_size_and_range(n_points: int, width: int) -> None:
    rng = np.random.default_rng(n_points)
    x = np.linspace(400.0, 2500.0, n_points)
    y = rng.normal(size=(3, n_points))
    x_out, y_out = decimate_minmax(x, y, width)
    expected = n_points if n_points <= width else 2 * (width // 2)
    assert x_out.shape == (expected,)
    assert y_out.shape == (3, expected)
    assert np.all(np.diff(x_out) >= 0)
    assert_close(y_out.max(axis=1), y.max(axis=1), rtol=0, atol=0)
    assert_close(y_out.min(axis=1), y.min(axis=1), rtol=0, atol=0)


# --- endpoint --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dataset", "shape"), [("gasoline_nir", (60, 401)), ("olive_oil_ftir", (120, 570))]
)
@pytest.mark.parametrize("apply_snv", [False, True])
def test_run_returns_raw_or_snv_spectra_as_arrow(
    client: TestClient,
    auth: dict[str, str],
    dataset: str,
    shape: tuple[int, int],
    *,
    apply_snv: bool,
) -> None:
    response = client.post(RUN, headers=auth, json={"dataset": dataset, "apply_snv": apply_snv})
    assert response.status_code == 200
    assert response.headers["content-type"] == ARROW_STREAM
    assert response.headers["x-vibechem-preview-mode"] == "lines"

    columns = read_arrow(response.content)
    n, p = shape
    assert list(columns) == ["x", *(f"y_{i}" for i in range(n))]
    assert columns["x"].shape == (p,)  # default width 1200 > p: no decimation

    data = load_reference_dataset(dataset)
    expected = snv(data.spectra) if apply_snv else data.spectra
    # Tolerances: float32 transport (relative rounding ≈ 6e-8; atol for SNV values near 0).
    assert_close(columns["x"], data.axis, rtol=1e-6, atol=0)
    y = np.stack([columns[f"y_{i}"] for i in range(n)])
    assert_close(y, expected, rtol=1e-6, atol=1e-6)


def test_run_decimates_to_width(client: TestClient, auth: dict[str, str]) -> None:
    body = {"dataset": "olive_oil_ftir", "apply_snv": True, "width": 100}
    columns = read_arrow(client.post(RUN, headers=auth, json=body).content)
    assert columns["x"].shape == (100,)


@pytest.mark.parametrize(
    "body",
    [
        {"dataset": "unknown", "apply_snv": True},
        {"apply_snv": True},
        {"dataset": "gasoline_nir"},
        {"dataset": "gasoline_nir", "apply_snv": True, "width": 63},
        {"dataset": "gasoline_nir", "apply_snv": True, "width": 4097},
    ],
)
def test_run_rejects_invalid_body(
    client: TestClient, auth: dict[str, str], body: dict[str, object]
) -> None:
    assert client.post(RUN, headers=auth, json=body).status_code == 422
