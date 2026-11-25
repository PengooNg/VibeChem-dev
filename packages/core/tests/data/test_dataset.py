# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/data/test_dataset.py
"""Tests for ``vibechem_core.data.dataset`` (DATA_MODEL.md §4.2 ``Spectra``)."""

import dataclasses
from typing import Any

import numpy as np
import pytest

from vibechem_core.data import Axis, Spatial, SpectralDataset


def make_dataset(n: int = 4, p: int = 3, **overrides: Any) -> SpectralDataset:
    """Fully annotated n x p dataset; ``overrides`` replace constructor arguments."""
    kwargs: dict[str, Any] = {
        "X": np.arange(n * p, dtype=np.float64).reshape(n, p),
        "axis": Axis(np.linspace(1100.0, 1100.0 + 2.0 * (p - 1), p), "nm"),
        "signal_unit": "absorbance",
        "sample_ids": [f"S{i:03d}" for i in range(n)],
        "row_index": np.arange(n) + 10,
        "source_id": "ds_test",
        "group_ids": [f"G{i // 2}" for i in range(n)],
        "y": np.column_stack([np.arange(n, dtype=float), np.arange(n, dtype=float) * 2]),
        "y_columns": ["fat", "water"],
        "y_units": ["%", "%"],
        "classes": ["a" if i % 2 else "b" for i in range(n)],
        "class_column": "kind",
        "metadata": {"origin": np.array([f"o{i}" for i in range(n)]), "temp": np.arange(n) * 1.5},
        "spatial": Spatial(height=max(n, 1), width=2, pixel=np.arange(n) * 2, cube_id="cube_1"),
        "history": ["Cut(1100-1104)"],
    }
    kwargs.update(overrides)
    return SpectralDataset(**kwargs)


def minimal_dataset(n: int = 3, p: int = 2) -> SpectralDataset:
    return SpectralDataset(
        X=np.ones((n, p)),
        axis=Axis(np.arange(p), "index"),
        signal_unit="arbitrary",
        sample_ids=[str(i) for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_min",
    )


def test_fields_shapes_and_defaults() -> None:
    ds = make_dataset(n=4, p=3)
    assert (ds.n_samples, ds.n_variables) == (4, 3)
    assert ds.X.dtype == np.float64
    assert ds.row_index.dtype == np.int64
    assert ds.sample_ids == ("S000", "S001", "S002", "S003")
    assert ds.group_ids == ("G0", "G0", "G1", "G1")
    assert ds.y is not None
    assert ds.y.shape == (4, 2)
    assert ds.y_columns == ("fat", "water")
    assert ds.y_units == ("%", "%")
    assert ds.classes == ("b", "a", "b", "a")
    assert ds.metadata is not None
    assert list(ds.metadata) == ["origin", "temp"]
    assert ds.history == ("Cut(1100-1104)",)

    m = minimal_dataset()
    assert m.group_ids is None
    assert m.y is None
    assert m.y_columns == ()
    assert m.y_units == ()
    assert m.classes is None
    assert m.class_column is None
    assert m.metadata is None
    assert m.spatial is None
    assert m.history == ()


def test_fields_cannot_be_reassigned() -> None:
    ds = make_dataset()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ds.X = np.zeros((4, 3))  # type: ignore[misc]


def test_arrays_are_read_only_and_independent_of_inputs() -> None:
    X = np.zeros((2, 2))
    y = np.zeros((2, 1))
    row_index = np.array([0, 1])
    temp = np.array([1.0, 2.0])
    ds = make_dataset(
        n=2, p=2, X=X, y=y, y_columns=["c"], y_units=["u"], row_index=row_index,
        metadata={"temp": temp},
    )  # fmt: skip
    X[0, 0] = y[0, 0] = temp[0] = 9.0
    row_index[0] = 7
    assert ds.y is not None
    assert ds.metadata is not None
    assert ds.X[0, 0] == 0.0
    assert ds.y[0, 0] == 0.0
    assert ds.row_index[0] == 0
    assert ds.metadata["temp"][0] == 1.0
    for array in (ds.X, ds.y, ds.row_index, ds.metadata["temp"]):
        assert not array.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            array[0] = 1


def test_metadata_mapping_is_read_only() -> None:
    ds = make_dataset()
    assert ds.metadata is not None
    with pytest.raises(TypeError):
        ds.metadata["new"] = np.zeros(4)  # type: ignore[index]


def test_numpy_strings_are_stored_as_str() -> None:
    ds = make_dataset(n=2, sample_ids=np.array(["a", "b"]).tolist())
    assert all(type(s) is str for s in ds.sample_ids)


N = 4  # rows of make_dataset() in the cases below


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"X": np.zeros(3)}, "X must be 2-D"),
        ({"X": np.zeros((N, 2))}, "axis has 3"),
        ({"X": np.full((N, 3), "a")}, "X must be numeric"),
        ({"signal_unit": ""}, "signal_unit"),
        ({"source_id": ""}, "source_id"),
        ({"sample_ids": ["a", "b", "c"]}, "sample_ids has 3"),
        ({"sample_ids": ["a", "b", "c", "a"]}, "sample_ids must be unique"),
        ({"sample_ids": ["a", "b", "c", 4]}, "sample_ids must be strings"),
        ({"row_index": np.arange(3)}, "row_index has 3"),
        ({"row_index": np.array([0, 1, 1, 2])}, "row_index must be unique"),
        ({"row_index": np.array([-1, 0, 1, 2])}, "row_index must be >= 0"),
        ({"row_index": np.array([0.0, 1.0, 2.0, 3.0])}, "row_index must be integers"),
        ({"group_ids": ["g"] * 3}, "group_ids has 3"),
        ({"y": np.zeros(N)}, "y must be 2-D"),
        ({"y": np.zeros((3, 2))}, "y has 3 rows"),
        ({"y_columns": ["fat"]}, "y_columns has 1"),
        ({"y_columns": ["fat", "fat"]}, "y_columns must be unique"),
        ({"y_units": ["%"]}, "y_units has 1"),
        ({"y": None}, "y_columns and y_units must be empty"),
        ({"classes": ["a"] * 3}, "classes has 3"),
        ({"class_column": None}, "class_column"),
        ({"classes": None}, "class_column"),
        ({"metadata": {"t": np.zeros(3)}}, "metadata column 't' has 3"),
        ({"metadata": {"t": np.zeros((N, 2))}}, "metadata column 't' must be 1-D"),
        ({"spatial": Spatial(height=2, width=2, pixel=[0, 1, 2], cube_id="c")}, "spatial"),
        ({"history": ["ok", 3]}, "history must be strings"),
    ],
)
def test_invalid_inputs_are_rejected(overrides: dict[str, Any], match: str) -> None:
    with pytest.raises((ValueError, TypeError), match=match):
        make_dataset(n=N, p=3, **overrides)


def test_axis_must_be_an_axis() -> None:
    with pytest.raises(TypeError, match="axis"):
        make_dataset(axis=[1.0, 2.0, 3.0])


def test_zero_rows_are_allowed() -> None:
    ds = make_dataset(n=0, p=3)
    assert (ds.n_samples, ds.n_variables) == (0, 3)
