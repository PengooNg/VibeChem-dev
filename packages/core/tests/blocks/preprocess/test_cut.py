# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/preprocess/test_cut.py
"""Tests for ``preprocess.cut`` (docs/METHODS.md#cut)."""

from __future__ import annotations

from typing import cast

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from vibechem_core.block import BLOCK_PARAM_INVALID, parse_params
from vibechem_core.blocks.preprocess.cut import Cut, CutParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import ParamError

ASCENDING = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]


def make_dataset(axis: list[float]) -> SpectralDataset:
    p = len(axis)
    X = np.arange(2 * p, dtype=np.float64).reshape(2, p)  # column j holds j and p + j
    return SpectralDataset(
        X,
        Axis(axis, "cm-1"),
        signal_unit="absorbance",
        sample_ids=["a", "b"],
        row_index=[0, 1],
        source_id="ds_test",
    )


def cut(axis: list[float], ranges: object) -> SpectralDataset:
    return Cut().apply(make_dataset(axis), parse_params(CutParams, {"ranges": ranges}))


def kept_columns(axis: list[float], ranges: object) -> list[int]:
    return [int(v) for v in cut(axis, ranges).X[0]]


def test_metadata_and_default_keeps_everything() -> None:
    meta = Cut.metadata()
    assert meta.fitted is False
    (entry,) = cast(list[object], meta.to_detail_dict()["params"])
    assert entry == {
        "param_id": "ranges",
        "type": "wavelength_ranges",
        "default": [[-1e6, 1e6]],
        "label_key": "blocks.preprocess.cut.params.ranges",
        "tooltip_key": "blocks.preprocess.cut.params.ranges.tip",
        "advanced": False,
    }
    data = make_dataset(ASCENDING)
    out = Cut().apply(data, CutParams())
    assert out.axis == data.axis
    np.testing.assert_array_equal(out.X, data.X)


@pytest.mark.parametrize("ranges", [[[20, 40]], [[40, 20]]], ids=["lo-hi", "hi-lo"])
def test_bounds_are_inclusive_in_either_order(ranges: object) -> None:
    out = cut(ASCENDING, ranges)
    np.testing.assert_array_equal(out.axis.values, [20.0, 30.0, 40.0])
    np.testing.assert_array_equal(out.X, [[1, 2, 3], [7, 8, 9]])
    assert out.axis.unit == "cm-1"
    assert out.history == ("Cut(ranges=[[20.0, 40.0]])",)
    assert out.sample_ids == ("a", "b")


def test_overlapping_ranges_give_the_union_without_duplicates() -> None:
    assert kept_columns(ASCENDING, [[30, 50], [20, 40]]) == [1, 2, 3, 4]


def test_descending_axis_keeps_its_order() -> None:
    descending = ASCENDING[::-1]  # 60 ... 10 (wavenumbers)
    out = cut(descending, [[20, 30], [60, 50]])
    np.testing.assert_array_equal(out.axis.values, [60.0, 50.0, 30.0, 20.0])
    assert [int(v) for v in out.X[0]] == [0, 1, 3, 4]


def test_range_outside_the_axis_is_allowed_next_to_one_that_selects() -> None:
    assert kept_columns(ASCENDING, [[100, 200], [10, 10]]) == [0]


@pytest.mark.parametrize("ranges", [[[100, 200]], [[21, 29]], [[61, 1e6], [-5, 9.99]]])
def test_empty_selection_is_rejected(ranges: object) -> None:
    with pytest.raises(ParamError) as info:
        cut(ASCENDING, ranges)
    assert info.value.code == BLOCK_PARAM_INVALID
    assert dict(info.value.params) == {"param_id": "ranges", "reason": "constraint"}


@given(
    st.lists(st.tuples(st.floats(-10.0, 80.0), st.floats(-10.0, 80.0)), min_size=1, max_size=4),
    st.booleans(),
)
def test_kept_points_are_exactly_those_inside_a_range(
    ranges: list[tuple[float, float]], descending: bool
) -> None:
    axis = ASCENDING[::-1] if descending else ASCENDING
    inside = [j for j, v in enumerate(axis) if any(min(a, b) <= v <= max(a, b) for a, b in ranges)]
    if not inside:
        with pytest.raises(ParamError):
            cut(axis, [list(r) for r in ranges])
        return
    assert kept_columns(axis, [list(r) for r in ranges]) == inside
