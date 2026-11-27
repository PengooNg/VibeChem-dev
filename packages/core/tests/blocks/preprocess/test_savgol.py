# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/preprocess/test_savgol.py
"""Tests for ``preprocess.savgol`` (docs/METHODS.md#savgol)."""

from __future__ import annotations

import warnings
from typing import Any, cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy.signal import savgol_filter  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import BLOCK_PARAM_INVALID, parse_params
from vibechem_core.blocks.preprocess import BLOCK_AXIS_NOT_UNIFORM
from vibechem_core.blocks.preprocess.savgol import MODES, SavitzkyGolay, SavitzkyGolayParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import ParamError, VibeChemWarning
from vibechem_core.testing import assert_close, assert_reference


def assert_exact(actual: np.typing.ArrayLike, expected: np.typing.ArrayLike, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-exact / T-lib


def make_dataset(X: np.typing.ArrayLike, axis: np.typing.ArrayLike) -> SpectralDataset:
    x = np.atleast_2d(np.asarray(X, dtype=np.float64))
    n = int(x.shape[0])
    return SpectralDataset(
        x,
        Axis(axis, "cm-1"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
    )


def run(X: np.typing.ArrayLike, axis: np.typing.ArrayLike, **values: Any) -> SpectralDataset:
    params = parse_params(SavitzkyGolayParams, values)
    return SavitzkyGolay().apply(make_dataset(X, axis), params)


NU = np.linspace(4000.0, 400.0, 41)  # descending wavenumber axis, step -90 cm-1


def test_metadata_and_defaults() -> None:
    meta = SavitzkyGolay.metadata()
    assert meta.fitted is False
    entries = cast(list[dict[str, Any]], meta.to_detail_dict()["params"])
    params = {p["param_id"]: p for p in entries}
    assert params["window"]["default"] == 11
    assert params["window"]["odd_only"] is True
    assert params["polyorder"]["default"] == 2
    assert params["polyorder"]["constraint"] == "polyorder < window"
    assert params["deriv"]["default"] == 0
    assert params["deriv"]["constraint"] == "deriv <= polyorder"
    assert params["mode"]["default"] == "interp"
    assert params["mode"]["choices"] == list(MODES)


def test_history_records_the_axis_step() -> None:
    out = run(np.ones((1, NU.size)), NU, deriv=1)
    assert out.history == (
        "SavitzkyGolay(window=11, polyorder=2, deriv=1, mode=interp, delta=-90 cm-1)",
    )
    assert out.signal_unit == "absorbance"


@pytest.mark.parametrize(
    ("deriv", "published"),
    [
        (0, np.array([-3.0, 12.0, 17.0, 12.0, -3.0]) / 35.0),  # 5-point quadratic smoothing
        (1, np.array([-2.0, -1.0, 0.0, 1.0, 2.0]) / 10.0),  # 5-point first derivative
    ],
)
def test_published_coefficients_on_interior_points(deriv: int, published: np.ndarray) -> None:
    # Savitzky & Golay 1964 with Steinier et al. 1972; unit step axis, so delta = 1.
    # A unit impulse at position k gives output[j] = c[k - j]: the coefficients, read
    # in window order around the impulse.
    x = np.zeros(15)
    x[7] = 1.0
    out = run(x, np.arange(15.0), window=5, polyorder=2, deriv=deriv).X[0]
    response = out[5:10][::-1]  # output at j = 9..5 sees the impulse at window offset -2..2
    assert_exact(response, published, f"SG coefficients d={deriv}")
    assert_reference(
        method=f"Savitzky-Golay 5-point quadratic, d={deriv} (centre-adjacent coefficient)",
        dataset="unit impulse, 15 points",
        actual=float(response[3]),
        expected=float(published[3]),
        rtol=1e-10,
        atol=1e-12,
        source="Savitzky & Golay 1964, corrected by Steinier et al. 1972",
    )


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize(("window", "polyorder", "deriv"), [(5, 2, 0), (11, 2, 1), (9, 3, 2)])
def test_matches_scipy(mode: str, window: int, polyorder: int, deriv: int) -> None:
    X = np.random.default_rng(3).normal(size=(4, NU.size))
    out = run(X, NU, window=window, polyorder=polyorder, deriv=deriv, mode=mode).X
    rows = [
        np.asarray(savgol_filter(row, window, polyorder, deriv=deriv, delta=-90.0, mode=mode))  # pyright: ignore[reportUnknownArgumentType]
        for row in X
    ]
    expected = np.vstack(rows)
    assert_exact(out, expected, "savgol vs scipy, row by row")


@pytest.mark.parametrize("axis", [NU, NU[::-1]], ids=["descending", "ascending"])
@pytest.mark.parametrize("deriv", [0, 1, 2, 3])
def test_polynomial_and_its_derivatives_in_axis_units(axis: np.ndarray, deriv: int) -> None:
    # Cubic in u = nu / 1000 (values of order 1); polyorder 3 reproduces it exactly
    # everywhere with mode interp, and its derivatives are the analytic ones per cm-1.
    c = np.array([0.3, -0.8, 0.5, -0.05])  # coefficients of u^0..u^3
    u = axis / 1000.0
    poly = np.polynomial.Polynomial(c)
    expected = poly.deriv(deriv)(u) / 1000.0**deriv if deriv else poly(u)
    out = run(poly(u), axis, window=7, polyorder=3, deriv=deriv).X[0]
    assert_close(out, expected, rtol=1e-9, atol=1e-12 / 1000.0**deriv, name=f"d{deriv}")
    if deriv == 1 and axis[0] > axis[-1]:
        assert_reference(
            method="Savitzky-Golay first derivative of a cubic (descending cm-1 axis, mid point)",
            dataset="synthetic cubic, 41 points",
            actual=float(out[20]),
            expected=float(expected[20]),
            rtol=1e-9,
            atol=1e-15,
            source="analytic derivative (METHODS.md#savgol)",
        )


@given(st.integers(0, 2**32 - 1))
def test_derivative_sign_follows_the_axis_direction(seed: int) -> None:
    # Reversing both axis and data must give the same d/dnu at the same wavenumbers.
    X = np.random.default_rng(seed).normal(size=(2, NU.size))
    forward = run(X, NU, deriv=1).X
    backward = run(X[:, ::-1], NU[::-1], deriv=1).X
    assert_close(backward[:, ::-1], forward, rtol=1e-9, atol=1e-12, name="reversed axis")


def test_window_longer_than_spectrum_is_rejected() -> None:
    with pytest.raises(ParamError) as info:
        run(np.ones((1, 9)), np.arange(9.0), window=11)
    assert info.value.code == BLOCK_PARAM_INVALID
    assert dict(info.value.params) == {"param_id": "window", "reason": "constraint", "value": 11}


@pytest.mark.parametrize(
    ("values", "param_id", "reason"),
    [
        ({"window": 10}, "window", "not_odd"),
        ({"window": 1}, "window", "below_min"),
        ({"window": 5, "polyorder": 5}, "polyorder", "constraint"),
        ({"polyorder": 2, "deriv": 3}, "deriv", "constraint"),
        ({"mode": "reflect"}, "mode", "not_a_choice"),
    ],
)
def test_invalid_parameters(values: dict[str, Any], param_id: str, reason: str) -> None:
    with pytest.raises(ParamError) as info:
        parse_params(SavitzkyGolayParams, values)
    assert info.value.params["param_id"] == param_id
    assert info.value.params["reason"] == reason


def test_slightly_uneven_axis_uses_the_mean_step_without_warning() -> None:
    # Deviation 0.9 % of the mean step: within the 1 % limit (METHODS.md N4).
    lam = np.arange(21.0) * 2.0
    lam[10] += 0.018
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the test
        out = run(2.0 + 0.5 * lam, lam, window=5, polyorder=2, deriv=1)
    assert out.history[-1].endswith("delta=2 cm-1)")


def test_uneven_axis_falls_back_to_per_point_with_warning() -> None:
    # Steps 1, ..., 1, 0.5, 1, ...: the 0.5 step deviates from the mean step 0.975 by 49 %.
    lam = np.concatenate([np.arange(10.0), 9.5 + np.arange(11.0)])
    mean_step = (lam[-1] - lam[0]) / (lam.size - 1)
    expected_deviation = float(np.abs(np.diff(lam) - mean_step).max() / mean_step)
    X = np.vstack([np.arange(lam.size, dtype=float) * 3.0])  # slope 3 per point
    with pytest.warns(VibeChemWarning) as record:
        out = run(X, lam, window=5, polyorder=1, deriv=1)
    (warning,) = [w.message for w in record]
    assert isinstance(warning, VibeChemWarning)
    assert warning.code == BLOCK_AXIS_NOT_UNIFORM
    assert warning.message_key == "warnings.block.axis_not_uniform"
    assert warning.params["max_deviation"] == pytest.approx(expected_deviation)
    assert_exact(out.X[0], np.full(lam.size, 3.0), "per-point derivative")
    assert out.history[-1].endswith("delta=1 per point)")
    assert out.signal_unit == "absorbance"
