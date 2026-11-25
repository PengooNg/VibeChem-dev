# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/data/test_axis.py
"""Tests for ``vibechem_core.data.axis`` (DATA_MODEL.md §4.2 ``axis`` and ``spatial``)."""

import dataclasses

import numpy as np
import pytest

from vibechem_core.data.axis import Axis, Spatial


def test_axis_holds_read_only_float64_copy() -> None:
    source = np.array([1100, 1102, 1104])
    axis = Axis(source, "nm")
    assert axis.values.dtype == np.float64
    assert axis.p == 3
    assert axis.unit == "nm"
    assert not axis.values.flags.writeable
    source[0] = 0
    assert axis.values[0] == 1100.0
    with pytest.raises(ValueError, match="read-only"):
        axis.values[0] = 5.0


def test_axis_accepts_decreasing_values() -> None:
    axis = Axis([4000.0, 3998.0, 3996.0], "cm-1")
    assert axis.values.tolist() == [4000.0, 3998.0, 3996.0]


def test_axis_is_frozen() -> None:
    axis = Axis([1.0, 2.0], "index")
    with pytest.raises(dataclasses.FrozenInstanceError):
        axis.unit = "nm"  # type: ignore[misc]


@pytest.mark.parametrize(
    "values",
    [[1.0, 1.0, 2.0], [1.0, 3.0, 2.0], [1.0, np.nan], [1.0, np.inf], [], [[1.0, 2.0]]],
    ids=["repeated", "not-monotonic", "nan", "inf", "empty", "2-d"],
)
def test_axis_rejects_invalid_values(values: list[float]) -> None:
    with pytest.raises(ValueError, match="axis"):
        Axis(values, "nm")


def test_axis_rejects_unknown_unit() -> None:
    with pytest.raises(ValueError, match="unit"):
        Axis([1.0, 2.0], "nanometre")  # type: ignore[arg-type]


def test_single_point_axis_is_allowed() -> None:
    assert Axis([1500.0], "nm").p == 1


def test_axis_equality_compares_values() -> None:
    assert Axis([1.0, 2.0], "nm") == Axis(np.array([1.0, 2.0]), "nm")
    assert Axis([1.0, 2.0], "nm") != Axis([1.0, 2.0], "cm-1")
    assert Axis([1.0, 2.0], "nm") != Axis([1.0, 3.0], "nm")


def test_spatial_holds_read_only_int64_pixels() -> None:
    spatial = Spatial(height=2, width=3, pixel=[5, 0, 2], cube_id="cube_1")
    assert spatial.pixel.dtype == np.int64
    assert not spatial.pixel.flags.writeable
    assert spatial == Spatial(height=2, width=3, pixel=np.array([5, 0, 2]), cube_id="cube_1")


@pytest.mark.parametrize(
    ("height", "width", "pixel"),
    [(0, 3, []), (2, 3, [6]), (2, 3, [-1]), (2, 3, [1, 1]), (2, 3, [[1]]), (2, 3, [1.5])],
    ids=["zero-height", "too-large", "negative", "duplicate", "2-d", "not-integer"],
)
def test_spatial_rejects_invalid(height: int, width: int, pixel: list[float]) -> None:
    with pytest.raises(ValueError, match="spatial"):
        Spatial(height=height, width=width, pixel=pixel, cube_id="c")
