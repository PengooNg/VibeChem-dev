# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/reference_datasets.py
"""Loaders for the bundled reference datasets in ``testdata/`` (QA.md §3).

The datasets, their file format, sources, licences and published results are
described in ``testdata/datasets/PROVENANCE.md``; the published values are JSON
files in ``testdata/expected/``.

- :func:`load_reference_dataset` reads one dataset CSV into numpy arrays and checks
  its shape.
- :func:`load_expected` reads one expected-values JSON file.

``testdata/`` lives in the repository and is not shipped in the wheel. By default
it is found by walking up from this file (works in the uv workspace); pass
``testdata_dir`` to use another location.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

__all__ = [
    "REFERENCE_DATASETS",
    "ReferenceDataset",
    "find_testdata_dir",
    "load_expected",
    "load_reference_dataset",
]


@dataclass(frozen=True)
class _Spec:
    file: str
    shape: tuple[int, int]
    axis_unit: str
    metadata: tuple[str, ...]  # metadata column names, in file order
    target: str
    numeric_target: bool
    groups: str | None


_SPECS: dict[str, _Spec] = {
    "gasoline_nir": _Spec(
        file="gasoline_nir.csv",
        shape=(60, 401),
        axis_unit="nm",
        metadata=("sample", "octane"),
        target="octane",
        numeric_target=True,
        groups=None,
    ),
    "olive_oil_ftir": _Spec(
        file="olive_oil_ftir.csv",
        shape=(120, 570),
        axis_unit="cm-1",
        metadata=("sample", "oil", "country"),
        target="country",
        numeric_target=False,
        groups="oil",
    ),
}

REFERENCE_DATASETS: tuple[str, ...] = tuple(_SPECS)
"""Names accepted by :func:`load_reference_dataset`."""


@dataclass(frozen=True)
class ReferenceDataset:
    """One reference dataset as numpy arrays.

    Attributes
    ----------
    name : str
        Dataset name, one of :data:`REFERENCE_DATASETS`.
    spectra : ndarray of float64, shape (n_samples, n_points)
        One spectrum per row.
    axis : ndarray of float64, shape (n_points,)
        Spectral axis values (the CSV header), in ``axis_unit``.
    axis_unit : str
        ``"nm"`` or ``"cm-1"``.
    target : ndarray, shape (n_samples,)
        float64 for regression targets, str for class labels.
    target_name : str
        Column name of the target.
    sample_ids : ndarray of int64, shape (n_samples,)
        The ``sample`` column (1-based row numbers of the source).
    groups : ndarray of int64, shape (n_samples,), or None
        Samples that must stay in the same CV fold (e.g. replicate spectra of one
        oil); ``None`` when every sample is independent.
    """

    name: str
    spectra: NDArray[np.float64]
    axis: NDArray[np.float64]
    axis_unit: str
    target: NDArray[np.float64] | NDArray[np.str_]
    target_name: str
    sample_ids: NDArray[np.int64]
    groups: NDArray[np.int64] | None


def find_testdata_dir(start: Path | None = None) -> Path:
    """Return the repository's ``testdata/`` directory.

    Walks up from ``start`` (default: this file) to the first directory that holds
    ``testdata/datasets/PROVENANCE.md``.

    Raises
    ------
    FileNotFoundError
        If no such directory exists (e.g. an installed wheel outside the repository).
    """
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        candidate = parent / "testdata"
        if (candidate / "datasets" / "PROVENANCE.md").is_file():
            return candidate
    msg = (
        f"testdata/datasets/PROVENANCE.md not found above {here}; the reference "
        "datasets are in the repository, not in the wheel. Pass testdata_dir."
    )
    raise FileNotFoundError(msg)


def load_reference_dataset(name: str, *, testdata_dir: Path | None = None) -> ReferenceDataset:
    """Load reference dataset ``name`` from ``testdata/datasets/``.

    Raises
    ------
    KeyError
        If ``name`` is not one of :data:`REFERENCE_DATASETS`.
    ValueError
        If the file's header, row lengths or shape differ from the documented ones.
    """
    if name not in _SPECS:
        msg = f"unknown reference dataset {name!r}; available: {', '.join(REFERENCE_DATASETS)}"
        raise KeyError(msg)
    spec = _SPECS[name]
    path = (testdata_dir or find_testdata_dir()) / "datasets" / spec.file

    # Step 1: read the CSV as text; check the metadata header.
    with path.open(newline="", encoding="utf-8") as f:
        lines = [row for row in csv.reader(f) if row]  # skip blank lines
    if not lines:
        msg = f"{path.name}: file is empty"
        raise ValueError(msg)
    header, *rows = lines
    n_meta = len(spec.metadata)
    if tuple(header[:n_meta]) != spec.metadata:
        msg = f"{path.name}: metadata columns {header[:n_meta]} != {list(spec.metadata)}"
        raise ValueError(msg)
    bad = [i for i, row in enumerate(rows, start=2) if len(row) != len(header)]
    if bad:
        msg = f"{path.name}: line {bad[0]} has a different number of fields than the header"
        raise ValueError(msg)

    # Step 2: convert to arrays and check the documented shape.
    axis = np.array(header[n_meta:], dtype=np.float64)
    spectra = np.array([row[n_meta:] for row in rows], dtype=np.float64).reshape(len(rows), -1)
    if spectra.shape != spec.shape:
        msg = f"{path.name}: shape {spectra.shape} != documented {spec.shape}"
        raise ValueError(msg)

    def column(col: str) -> list[str]:
        j = spec.metadata.index(col)
        return [row[j] for row in rows]

    target_text = column(spec.target)
    target = (
        np.array(target_text, dtype=np.float64)
        if spec.numeric_target
        else np.array(target_text, dtype=np.str_)
    )
    groups = None if spec.groups is None else np.array(column(spec.groups), dtype=np.int64)
    return ReferenceDataset(
        name=name,
        spectra=spectra,
        axis=axis,
        axis_unit=spec.axis_unit,
        target=target,
        target_name=spec.target,
        sample_ids=np.array(column("sample"), dtype=np.int64),
        groups=groups,
    )


def load_expected(name: str, *, testdata_dir: Path | None = None) -> dict[str, Any]:
    """Load ``testdata/expected/<name>.json`` (published values for a reference test).

    Raises
    ------
    KeyError
        If there is no such file; the message lists the available names.
    """
    expected_dir = (testdata_dir or find_testdata_dir()) / "expected"
    available = sorted(p.stem for p in expected_dir.glob("*.json"))
    if name not in available:
        msg = f"unknown expected-values file {name!r}; available: {', '.join(available)}"
        raise KeyError(msg)
    path = expected_dir / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        expected: dict[str, Any] = json.load(f)
    return expected
