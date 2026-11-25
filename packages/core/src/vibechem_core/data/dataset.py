# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/data/dataset.py
"""``SpectralDataset``: the Python object behind the ``Spectra`` port type.

Fields follow DATA_MODEL.md §4.2 (``Spectra``). The object is immutable: fields
cannot be reassigned, every array is a private read-only copy, and ``metadata`` is
a read-only mapping. Operations return new datasets.

``row_index`` holds, per row, the row's index in the source dataset
(``source_id``); it travels with the rows through every operation so folds can be
mapped onto any downstream object (leakage safety, ARCHITECTURE.md §3.2).

``metadata`` is the logical "Table (n rows)" of DATA_MODEL.md §4.2, kept in core as
``column name -> 1-D array`` so core does not import pyarrow (TECH_STACK.md §3.1).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from vibechem_core.data.axis import Axis, Spatial, frozen_array


def _strings(name: str, values: Iterable[object]) -> tuple[str, ...]:
    """Check run-time types too: callers may pass ids read from files."""
    items = tuple(values)
    if not all(isinstance(item, str) for item in items):
        raise TypeError(f"{name} must be strings")
    return tuple(str(item) for item in items)


def _check_length(name: str, size: int, n: int) -> None:
    if size != n:
        raise ValueError(f"{name} has {size} entries, expected one per sample (n = {n})")


def _numeric_2d(name: str, values: ArrayLike) -> NDArray[np.float64]:
    array = np.asarray(values)
    if array.ndim != 2:
        raise ValueError(f"{name} must be 2-D (samples x columns), got shape {array.shape}")
    if not np.issubdtype(array.dtype, np.number):
        raise ValueError(f"{name} must be numeric, got dtype {array.dtype}")
    return frozen_array(array, np.float64)


@dataclass(frozen=True, eq=False)
class SpectralDataset:
    """n samples x p variables on one spectral axis, plus sample annotations.

    Parameters
    ----------
    X : array_like, shape (n, p)
        Signal values, stored as float64. NaN is allowed (missing values).
    axis : Axis
        Spectral axis with ``p`` values.
    signal_unit : str
        e.g. ``absorbance``, ``reflectance``, ``counts``, ``arbitrary``.
    sample_ids : iterable of str, length n
        Unique sample identifiers.
    row_index : array_like of int, length n
        Row of each sample in the source dataset; unique, >= 0.
    source_id : str
        ``dataset_id`` of the source dataset.
    group_ids : iterable of str, length n, optional
        Replicate / batch groups (group CV).
    y : array_like, shape (n, k), optional
        Response values, stored as float64. NaN is allowed.
    y_columns, y_units : iterable of str, length k
        Names and units of the ``y`` columns; empty when ``y`` is None.
    classes : iterable of str, length n, optional
        Class label per sample; requires ``class_column``.
    class_column : str, optional
        Name of the class column; set exactly when ``classes`` is set.
    metadata : mapping of str to 1-D array_like (length n), optional
        Other columns kept from import.
    spatial : Spatial, optional
        Pixel positions when the rows were unfolded from an ``ImageCube``.
    history : iterable of str
        Applied steps, e.g. ``"SNV(ddof=1)"``.
    """

    X: NDArray[np.float64]
    axis: Axis
    signal_unit: str
    sample_ids: tuple[str, ...]
    row_index: NDArray[np.int64]
    source_id: str
    group_ids: tuple[str, ...] | None
    y: NDArray[np.float64] | None
    y_columns: tuple[str, ...]
    y_units: tuple[str, ...]
    classes: tuple[str, ...] | None
    class_column: str | None
    metadata: Mapping[str, NDArray[Any]] | None
    spatial: Spatial | None
    history: tuple[str, ...]

    def __init__(
        self,
        X: ArrayLike,
        axis: Axis,
        *,
        signal_unit: str,
        sample_ids: Iterable[str],
        row_index: ArrayLike,
        source_id: str,
        group_ids: Iterable[str] | None = None,
        y: ArrayLike | None = None,
        y_columns: Iterable[str] = (),
        y_units: Iterable[str] = (),
        classes: Iterable[str] | None = None,
        class_column: str | None = None,
        metadata: Mapping[str, ArrayLike] | None = None,
        spatial: Spatial | None = None,
        history: Iterable[str] = (),
    ) -> None:
        # Signal values and axis
        x = _numeric_2d("X", X)
        n = x.shape[0]
        if not isinstance(axis, Axis):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(f"axis must be an Axis, got {type(axis).__name__}")
        if x.shape[1] != axis.p:
            raise ValueError(f"X has {x.shape[1]} variables but the axis has {axis.p} values")
        if not signal_unit:
            raise ValueError("signal_unit must be a non-empty string")
        if not source_id:
            raise ValueError("source_id must be a non-empty string")

        # Sample identity and provenance
        ids = _strings("sample_ids", sample_ids)
        _check_length("sample_ids", len(ids), n)
        if len(set(ids)) != n:
            raise ValueError("sample_ids must be unique")
        rows = np.asarray(row_index)
        if rows.ndim != 1:
            raise ValueError(f"row_index must be 1-D, got shape {rows.shape}")
        _check_length("row_index", rows.size, n)
        if n and not np.issubdtype(rows.dtype, np.integer):
            raise ValueError(f"row_index must be integers, got dtype {rows.dtype}")
        rows_frozen = frozen_array(rows, np.int64)
        if n and rows_frozen.min() < 0:
            raise ValueError("row_index must be >= 0")
        if np.unique(rows_frozen).size != n:
            raise ValueError("row_index must be unique")

        groups = None if group_ids is None else _strings("group_ids", group_ids)
        if groups is not None:
            _check_length("group_ids", len(groups), n)

        # Responses
        y_cols = _strings("y_columns", y_columns)
        y_unit_names = _strings("y_units", y_units)
        y_frozen = None
        if y is None:
            if y_cols or y_unit_names:
                raise ValueError("y_columns and y_units must be empty when y is None")
        else:
            y_frozen = _numeric_2d("y", y)
            if y_frozen.shape[0] != n:
                raise ValueError(f"y has {y_frozen.shape[0]} rows, expected n = {n}")
            k = y_frozen.shape[1]
            if len(y_cols) != k:
                raise ValueError(f"y_columns has {len(y_cols)} names, y has {k} columns")
            if len(set(y_cols)) != k:
                raise ValueError("y_columns must be unique")
            if len(y_unit_names) != k:
                raise ValueError(f"y_units has {len(y_unit_names)} units, y has {k} columns")

        labels = None if classes is None else _strings("classes", classes)
        if labels is not None:
            _check_length("classes", len(labels), n)
        if (labels is None) != (class_column is None):
            raise ValueError("class_column must be set exactly when classes is set")

        # Other annotations
        meta = None
        if metadata is not None:
            columns: dict[str, NDArray[Any]] = {}
            for name, values in metadata.items():
                column = np.array(values, copy=True)
                if column.ndim != 1:
                    raise ValueError(f"metadata column {name!r} must be 1-D")
                _check_length(f"metadata column {name!r}", column.size, n)
                column.flags.writeable = False
                columns[name] = column
            meta = MappingProxyType(columns)

        if spatial is not None:
            _check_length("spatial pixel", spatial.pixel.size, n)

        steps = _strings("history", history)

        for field, value in (
            ("X", x),
            ("axis", axis),
            ("signal_unit", signal_unit),
            ("sample_ids", ids),
            ("row_index", rows_frozen),
            ("source_id", source_id),
            ("group_ids", groups),
            ("y", y_frozen),
            ("y_columns", y_cols),
            ("y_units", y_unit_names),
            ("classes", labels),
            ("class_column", class_column),
            ("metadata", meta),
            ("spatial", spatial),
            ("history", steps),
        ):
            object.__setattr__(self, field, value)

    @property
    def n_samples(self) -> int:
        """Number of rows (samples)."""
        return int(self.X.shape[0])

    @property
    def n_variables(self) -> int:
        """Number of variables (axis points)."""
        return int(self.X.shape[1])
