# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/cli/data.py
"""A table file as a ``SpectralDataset`` for ``vibechem run --data`` (T2.11).

Columns take the roles ``read_table`` suggests (DATA_MODEL.md §2.5): sample ID, group,
class, Y, metadata and the run of spectral columns. The user confirms roles in the app;
the CLI takes the suggestion as is.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vibechem_core.data import AXIS_UNITS, Axis, SpectralDataset
from vibechem_core.io import TableImport, read_table

__all__ = ["dataset_from_file", "dataset_from_table"]


def dataset_from_file(path: str | Path, dataset_id: str) -> SpectralDataset:
    """Read ``path`` with ``read_table`` and build the dataset ``dataset_id`` from it."""
    return dataset_from_table(read_table(path), dataset_id)


def dataset_from_table(table: TableImport, dataset_id: str) -> SpectralDataset:
    """The suggested roles of ``table`` as a dataset.

    Raises ``ValueError`` when the table has no spectral columns.
    """
    roles = table.suggested_roles
    spectral = roles["spectral_columns"]
    if spectral is None:
        raise ValueError("the file has no spectral columns")
    names = list(table.columns)
    first = names.index(spectral["from"])
    axis_names = names[first : first + spectral["count"]]
    X = np.column_stack([np.asarray(table.columns[n], dtype=np.float64) for n in axis_names])
    unit = spectral["axis_unit"]
    n = table.n_rows
    sample_col = roles["sample_id"]
    sample_ids = (
        [str(v) for v in table.columns[sample_col]]
        if sample_col
        else [f"s{i + 1}" for i in range(n)]
    )
    group_col = roles["group_id"]
    class_col = roles["class_label"]
    y_names = roles["y"]
    return SpectralDataset(
        X,
        Axis([float(name) for name in axis_names], unit if unit in AXIS_UNITS else "index"),  # pyright: ignore[reportArgumentType]
        signal_unit="arbitrary",
        sample_ids=sample_ids,
        row_index=np.arange(n),
        source_id=dataset_id,
        group_ids=[str(v) for v in table.columns[group_col]] if group_col else None,
        y=np.column_stack([table.columns[c] for c in y_names]) if y_names else None,
        y_columns=y_names,
        y_units=[""] * len(y_names),
        classes=[str(v) for v in table.columns[class_col]] if class_col else None,
        class_column=class_col,
        metadata={c: table.columns[c] for c in roles["metadata"]} or None,
    )
