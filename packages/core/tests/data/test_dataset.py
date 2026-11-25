# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/data/test_dataset.py
"""Tests for ``vibechem_core.data.dataset`` (DATA_MODEL.md §4.2 ``Spectra``)."""

import dataclasses
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

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


# --- with_X -------------------------------------------------------------------


def test_with_x_replaces_signal_and_keeps_annotations() -> None:
    ds = make_dataset(n=4, p=3)
    new = ds.with_X(ds.X * 2.0, step="Scale(2)")
    assert new is not ds
    np.testing.assert_array_equal(new.X, ds.X * 2.0)
    assert not new.X.flags.writeable
    assert new.history == ("Cut(1100-1104)", "Scale(2)")
    assert new.axis is ds.axis
    assert new.sample_ids == ds.sample_ids
    np.testing.assert_array_equal(new.row_index, ds.row_index)
    assert new.metadata is not None
    assert ds.metadata is not None
    assert new.metadata.keys() == ds.metadata.keys()
    assert new.classes == ds.classes
    assert new.spatial is ds.spatial
    np.testing.assert_array_equal(ds.X, np.arange(12.0).reshape(4, 3))  # original unchanged


def test_with_x_without_step_keeps_history() -> None:
    ds = make_dataset()
    assert ds.with_X(ds.X).history == ds.history


def test_with_x_changing_p_needs_a_new_axis() -> None:
    ds = make_dataset(n=4, p=3)
    with pytest.raises(ValueError, match="axis has 3"):
        ds.with_X(ds.X[:, :2])
    cut = ds.with_X(ds.X[:, :2], axis=Axis(ds.axis.values[:2], "nm"), step="Cut")
    assert cut.n_variables == 2
    assert cut.axis.p == 2


def test_with_x_rejects_a_different_row_count() -> None:
    ds = make_dataset(n=4, p=3)
    with pytest.raises(ValueError, match="sample_ids has 4"):
        ds.with_X(ds.X[:3])


# --- subset -------------------------------------------------------------------


def test_subset_selects_rows_in_the_given_order() -> None:
    ds = make_dataset(n=4, p=3)
    sub = ds.subset([3, 0])
    np.testing.assert_array_equal(sub.X, ds.X[[3, 0]])
    assert sub.sample_ids == ("S003", "S000")
    np.testing.assert_array_equal(sub.row_index, [13, 10])
    assert sub.group_ids == ("G1", "G0")
    assert sub.y is not None
    assert ds.y is not None
    np.testing.assert_array_equal(sub.y, ds.y[[3, 0]])
    assert sub.classes == ("a", "b")
    assert sub.metadata is not None
    assert sub.metadata["origin"].tolist() == ["o3", "o0"]
    assert sub.spatial is not None
    np.testing.assert_array_equal(sub.spatial.pixel, [6, 0])
    assert (sub.spatial.height, sub.spatial.width, sub.spatial.cube_id) == (4, 2, "cube_1")
    # unchanged fields
    assert sub.axis is ds.axis
    assert (sub.signal_unit, sub.source_id, sub.history) == (
        ds.signal_unit,
        ds.source_id,
        ds.history,
    )
    assert (sub.y_columns, sub.y_units, sub.class_column) == (ds.y_columns, ds.y_units, "kind")


def test_subset_of_minimal_dataset_and_empty_selection() -> None:
    ds = minimal_dataset(n=3)
    assert ds.subset(np.array([2])).sample_ids == ("2",)
    empty = make_dataset().subset([])
    assert (empty.n_samples, empty.n_variables) == (0, 3)
    assert empty.row_index.dtype == np.int64


@pytest.mark.parametrize(
    ("indices", "match"),
    [
        ([0, 0], "unique"),
        ([4], r"\[0, 4\)"),
        ([-1], r"\[0, 4\)"),
        ([0.0, 1.0], "integers"),
        ([[0, 1]], "1-D"),
        ([True, False, True, False], "integers"),
    ],
    ids=["duplicate", "too-large", "negative", "float", "2-d", "bool-mask"],
)
def test_subset_rejects_invalid_indices(indices: list[Any], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        make_dataset(n=4).subset(indices)


# --- properties (hypothesis) --------------------------------------------------


@st.composite
def datasets_and_indices(draw: st.DrawFn) -> tuple[SpectralDataset, list[int]]:
    n = draw(st.integers(min_value=1, max_value=12))
    p = draw(st.integers(min_value=1, max_value=6))
    X = draw(hnp.arrays(np.float64, (n, p), elements=st.floats(allow_nan=True, width=64)))
    row_index = draw(st.lists(st.integers(0, 10_000), min_size=n, max_size=n, unique=True))
    ds = make_dataset(n=n, p=p, X=X, row_index=row_index)
    indices = draw(st.permutations(range(n)).map(lambda perm: perm[: draw(st.integers(0, n))]))
    return ds, list(indices)


def _same_rows(sub: SpectralDataset, ds: SpectralDataset, indices: list[int]) -> None:
    np.testing.assert_array_equal(sub.X, ds.X[indices])
    np.testing.assert_array_equal(sub.row_index, ds.row_index[indices])
    assert sub.sample_ids == tuple(ds.sample_ids[i] for i in indices)
    assert ds.group_ids is not None
    assert ds.classes is not None
    assert sub.group_ids == tuple(ds.group_ids[i] for i in indices)
    assert sub.classes == tuple(ds.classes[i] for i in indices)
    assert sub.y is not None
    assert ds.y is not None
    np.testing.assert_array_equal(sub.y, ds.y[indices])
    assert sub.metadata is not None
    assert ds.metadata is not None
    for name, column in ds.metadata.items():
        np.testing.assert_array_equal(sub.metadata[name], column[indices])
    assert sub.spatial is not None
    assert ds.spatial is not None
    np.testing.assert_array_equal(sub.spatial.pixel, ds.spatial.pixel[indices])


@given(datasets_and_indices())
def test_property_subset_keeps_every_row_field_aligned(
    case: tuple[SpectralDataset, list[int]],
) -> None:
    ds, indices = case
    sub = ds.subset(indices)
    assert (sub.n_samples, sub.n_variables) == (len(indices), ds.n_variables)
    _same_rows(sub, ds, indices)
    # row_index maps each subset row back to the same source row as in the parent
    position = {int(r): i for i, r in enumerate(ds.row_index)}
    for k, r in enumerate(sub.row_index):
        assert ds.sample_ids[position[int(r)]] == sub.sample_ids[k]


@given(datasets_and_indices(), st.data())
def test_property_subset_composes(
    case: tuple[SpectralDataset, list[int]], data: st.DataObject
) -> None:
    ds, outer = case
    inner = data.draw(st.permutations(range(len(outer))))
    inner = inner[: data.draw(st.integers(0, len(inner)))]
    twice = ds.subset(outer).subset(inner)
    _same_rows(twice, ds, [outer[i] for i in inner])


@given(datasets_and_indices())
def test_property_operations_never_mutate_and_stay_read_only(
    case: tuple[SpectralDataset, list[int]],
) -> None:
    ds, indices = case
    before = (ds.X.copy(), ds.row_index.copy(), ds.sample_ids, ds.history)
    results = [ds.subset(indices), ds.with_X(ds.X + 1.0, step="AddOne")]
    np.testing.assert_array_equal(ds.X, before[0])
    np.testing.assert_array_equal(ds.row_index, before[1])
    assert (ds.sample_ids, ds.history) == before[2:]
    for result in results:
        assert ds.y is not None
        arrays = [result.X, result.row_index, result.y]
        assert result.metadata is not None
        arrays += list(result.metadata.values())
        assert all(a is not None and not a.flags.writeable for a in arrays)
