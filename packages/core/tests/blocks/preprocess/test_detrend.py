# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/preprocess/test_detrend.py
"""Tests for ``preprocess.detrend`` (docs/METHODS.md#detrend)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from vibechem_core.block import BLOCK_PARAM_INVALID, parse_params
from vibechem_core.blocks.preprocess.detrend import Detrend, DetrendParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.testing import assert_close, assert_reference


def assert_exact(actual: np.typing.ArrayLike, expected: np.typing.ArrayLike, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-exact (METHODS §1)


def make_dataset(X: np.typing.ArrayLike, axis: np.typing.ArrayLike) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n = int(x.shape[0])
    return SpectralDataset(
        x,
        Axis(axis, "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
    )


def run(
    X: np.typing.ArrayLike, axis: np.typing.ArrayLike, degree: int = 2
) -> np.typing.NDArray[np.float64]:
    params = parse_params(DetrendParams, {"degree": degree})
    return Detrend().apply(make_dataset(X, axis), params).X


LAM = np.linspace(1000.0, 2000.0, 60)


def test_metadata_and_default() -> None:
    meta = Detrend.metadata()
    assert meta.fitted is False
    assert meta.to_detail_dict()["params"] == [
        {
            "param_id": "degree",
            "type": "int",
            "default": 2,
            "min": 1,
            "label_key": "blocks.preprocess.detrend.params.degree",
            "tooltip_key": "blocks.preprocess.detrend.params.degree.tip",
            "advanced": False,
        }
    ]
    out = Detrend().apply(
        make_dataset([[1.0, 3.0, 2.0, 5.0]], [1.0, 2.0, 3.0, 4.0]), DetrendParams()
    )
    assert out.history == ("Detrend(degree=2)",)


def test_hand_calculation_degree_one() -> None:
    # lambda = [1, 2, 3], x = [1, 3, 2]: line 2 + 0.5 (lambda - 2) = [1.5, 2, 2.5].
    out = run([[1.0, 3.0, 2.0]], [1.0, 2.0, 3.0], degree=1)
    expected = [-0.5, 1.0, -0.5]
    assert_exact(out[0], expected, "detrend")
    assert_reference(
        method="Detrend (degree 1, element [0, 1])",
        dataset="hand calculation 1x3",
        actual=float(out[0, 1]),
        expected=1.0,
        rtol=1e-10,
        atol=1e-12,
        source="hand calculation (METHODS.md#detrend)",
    )


@pytest.mark.parametrize("degree", [1, 2, 3])
def test_polynomial_in_axis_value_gives_zero(degree: int) -> None:
    # Coefficients in lambda (nm), small enough that values stay of order 1.
    coefs = [0.5, 2e-3, -1e-6, 3e-10][: degree + 1]
    rows = np.vstack([sum(c * LAM**d for d, c in enumerate(coefs)), 4.0 - 1e-3 * LAM])
    out = run(rows, LAM, degree)
    assert_exact(out, np.zeros_like(rows), f"detrend of degree-{degree} polynomial")
    assert_reference(
        method=f"Detrend (degree {degree} polynomial in the axis, max abs output)",
        dataset="synthetic 60 points",
        actual=float(np.abs(out).max()),
        expected=0.0,
        rtol=0.0,
        atol=1e-12,
        source="algebraic identity (METHODS.md#detrend)",
    )


def test_orthogonal_component_comes_back() -> None:
    rng = np.random.default_rng(11)
    u = (LAM - 1500.0) / 500.0
    # Project random noise off the polynomial space with a QR basis (independent of lstsq).
    q, _ = np.linalg.qr(np.vander(u, 3, increasing=True))
    noise = rng.normal(size=(3, LAM.size))
    component = noise - (noise @ q) @ q.T
    trend = 1.0 + 0.4 * u - 0.7 * u**2
    out = run(component + trend, LAM, degree=2)
    assert_exact(out, component, "orthogonal component")


@given(st.integers(1, 4), st.integers(0, 2**32 - 1))
def test_independent_of_axis_direction(degree: int, seed: int) -> None:
    X = np.random.default_rng(seed).normal(size=(2, 25))
    lam = np.linspace(400.0, 4000.0, 25)
    forward = run(X, lam, degree)
    backward = run(X[:, ::-1], lam[::-1], degree)
    assert_close(backward[:, ::-1], forward, rtol=1e-9, atol=1e-11, name="reversed axis")


def test_degree_not_below_points_is_rejected() -> None:
    with pytest.raises(ParamError) as info:
        run([[1.0, 2.0, 4.0]], [1.0, 2.0, 3.0], degree=3)
    assert info.value.code == BLOCK_PARAM_INVALID
    assert dict(info.value.params) == {"param_id": "degree", "reason": "constraint", "value": 3}


def test_degree_zero_is_below_min() -> None:
    with pytest.raises(ParamError) as info:
        parse_params(DetrendParams, {"degree": 0})
    assert info.value.params["reason"] == "below_min"
