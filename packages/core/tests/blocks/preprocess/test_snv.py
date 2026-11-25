# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/preprocess/test_snv.py
"""Tests for ``preprocess.snv`` (docs/METHODS.md#snv)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from vibechem_core.block import BLOCK_PARAM_INVALID, parse_params
from vibechem_core.blocks.preprocess import BLOCK_CONSTANT_SPECTRA
from vibechem_core.blocks.preprocess.snv import SNV, SNVParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError, ParamError
from vibechem_core.testing import assert_close, assert_reference


def assert_exact(actual: np.typing.ArrayLike, expected: np.typing.ArrayLike, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-exact (METHODS §1)


def make_dataset(X: np.typing.ArrayLike) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = int(x.shape[0]), int(x.shape[1])
    return SpectralDataset(
        x,
        Axis(np.linspace(1000.0, 2000.0, p), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
    )


def run(X: np.typing.ArrayLike, ddof: int = 1) -> np.typing.NDArray[np.float64]:
    return SNV().apply(make_dataset(X), parse_params(SNVParams, {"ddof": ddof})).X


def test_metadata() -> None:
    meta = SNV.metadata()
    assert meta.block_id == "preprocess.snv"
    assert meta.fitted is False
    detail = meta.to_detail_dict()
    assert detail["params"] == [
        {
            "param_id": "ddof",
            "type": "enum",
            "default": 1,
            "choices": [0, 1],
            "label_key": "blocks.preprocess.snv.params.ddof",
            "tooltip_key": "blocks.preprocess.snv.params.ddof.tip",
            "advanced": False,
        }
    ]


@pytest.mark.parametrize(
    ("ddof", "sd1", "sd2"),
    [(1, math.sqrt(5 / 3), math.sqrt(19 / 3)), (0, math.sqrt(5 / 4), math.sqrt(19 / 4))],
)
def test_hand_calculation(ddof: int, sd1: float, sd2: float) -> None:
    # Row 1: mean 2.5, squared deviations 2.25 + 0.25 + 0.25 + 2.25 = 5.
    # Row 2: mean 4.5, squared deviations 6.25 + 0.25 + 0.25 + 12.25 = 19.
    X = [[1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 4.0, 8.0]]
    expected = [
        [-1.5 / sd1, -0.5 / sd1, 0.5 / sd1, 1.5 / sd1],
        [-2.5 / sd2, -0.5 / sd2, -0.5 / sd2, 3.5 / sd2],
    ]
    actual = run(X, ddof)
    assert_exact(actual, expected, "SNV")
    for i, j in ((0, 0), (1, 3)):
        assert_reference(
            method=f"SNV (ddof={ddof}, element [{i}, {j}])",
            dataset="hand calculation 2x4",
            actual=float(actual[i, j]),
            expected=expected[i][j],
            rtol=1e-10,
            atol=1e-12,
            source="hand calculation (METHODS.md#snv)",
        )


def test_default_ddof_is_one_and_history() -> None:
    out = SNV().apply(make_dataset([[1.0, 2.0, 4.0]]), parse_params(SNVParams, {}))
    assert out.history == ("SNV(ddof=1)",)
    assert_exact(out.X.std(axis=1, ddof=1), [1.0], "SD")


def test_other_fields_kept() -> None:
    data = make_dataset([[1.0, 2.0, 4.0], [3.0, 1.0, 0.0]])
    out = SNV().apply(data, SNVParams())
    assert out.axis == data.axis
    assert out.sample_ids == data.sample_ids


rows = arrays(
    np.float64,
    st.tuples(st.integers(1, 5), st.integers(3, 30)),
    elements=st.floats(-1e3, 1e3, allow_nan=False),
)


@given(rows, st.sampled_from([0, 1]))
def test_rows_have_mean_zero_and_sd_one(X: np.typing.NDArray[np.float64], ddof: int) -> None:
    if (X.std(axis=1) < 1e-3).any():  # avoid flat or near-flat rows
        return
    Z = run(X, ddof)
    assert_close(Z.mean(axis=1), np.zeros(X.shape[0]), rtol=0, atol=1e-10)
    assert_close(Z.std(axis=1, ddof=ddof), np.ones(X.shape[0]), rtol=1e-10, atol=0)


@given(rows, st.floats(0.01, 100.0), st.floats(-100.0, 100.0))
def test_affine_invariance(X: np.typing.NDArray[np.float64], a: float, b: float) -> None:
    if (X.std(axis=1) < 1e-3).any():
        return
    assert_close(run(a * X + b), run(X), rtol=1e-8, atol=1e-8, name="SNV(aX + b)")


def test_constant_row_is_rejected_with_row_list() -> None:
    with pytest.raises(BlockInputError) as info:
        run([[1.0, 2.0, 3.0], [5.0, 5.0, 5.0], [0.0, 1.0, 0.0], [2.0, 2.0, 2.0]])
    assert info.value.code == BLOCK_CONSTANT_SPECTRA
    assert info.value.params["rows"] == [1, 3]


@pytest.mark.parametrize("ddof", [0, 1])
def test_single_point_is_rejected(ddof: int) -> None:
    # p = 1: with ddof = 1 the SD is undefined (p - ddof = 0); with ddof = 0 it is 0.
    with pytest.raises(BlockInputError) as info:
        run([[3.0], [4.0]], ddof)
    assert info.value.params["rows"] == [0, 1]


def test_invalid_ddof() -> None:
    with pytest.raises(ParamError) as info:
        parse_params(SNVParams, {"ddof": 2})
    assert info.value.code == BLOCK_PARAM_INVALID
    assert info.value.params["reason"] == "not_a_choice"


@pytest.mark.parametrize("value", [0.1, 1.1, 2.3])
def test_constant_row_with_inexact_mean_is_rejected(value: float) -> None:
    # Regression (code review): the mean of 0.1s is off by one ulp, so std is 1e-17, not 0.
    with pytest.raises(BlockInputError) as info:
        run([[value] * 7, [1.0, 2.0, 3.0, 1.0, 2.0, 3.0, 4.0]])
    assert info.value.params["rows"] == [0]
