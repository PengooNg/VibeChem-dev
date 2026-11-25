# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/multifile.py
"""Read one or several files into one table (DATA_MODEL.md §2.5 step 1, ``paths``).

The multi-file behaviour follows orange-spectroscopy's Multifile widget
(``widgets/owmultifile.py``, behaviour only, no code): rows of all files, a
file-name column, and the union of the spectral axes.

Rules
-----
- Format from ``format_hint``, else from the extension: ``.jdx``, ``.dx``,
  ``.jcamp`` → JCAMP-DX; ``.spc`` → SPC; ``.spa`` → OMNIC SPA;
  ``.sp`` → PerkinElmer; anything else → ``read_table``
  (CSV/TSV/Excel; it rejects unknown extensions with ``IMPORT_FORMAT_UNKNOWN``).
- One path → that reader's result, unchanged.
- Several paths → the rows of every file in path order and a text column
  ``source_file`` (the file name) first. Other columns are matched by name in
  first-seen order; a file without the column gets NaN (number column) or ``""``
  (text column; a column that is text in any file becomes text, numbers written
  as ``repr``). Spectral columns are matched by axis value (``"1100"`` and
  ``"1100.0"`` are the same point; the first file's name is kept) on the union
  axis, ordered like the first file's axis; points a file lacks are NaN, with an
  ``IMPORT_AXIS_MISMATCH`` warning (``axes``: number of distinct file axes) and
  ``needs_interpolation``. An axis and its reverse are the same axis; a file
  without spectral columns does not count (its rows are NaN there). A file that
  already has a ``source_file`` column cannot be merged (``duplicate_column``).
- Roles are suggested again for the merged table (axis unit: the first file's).
  Each file's warnings are kept, except duplicate sample IDs, which are counted
  again over all files. ``detected_format`` is the first file's.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from pathlib import Path
from types import MappingProxyType

import numpy as np
from numpy.typing import NDArray

from vibechem_core.errors import VibeChemError
from vibechem_core.io.jcamp import read_jcamp
from vibechem_core.io.perkinelmer import read_perkinelmer
from vibechem_core.io.spa import read_spa
from vibechem_core.io.spc import read_spc
from vibechem_core.io.table import (
    IMPORT_AXIS_MISMATCH,
    IMPORT_DUPLICATE_SAMPLE_IDS,
    IMPORT_FILE_INVALID,
    ImportWarning,
    TableImport,
    _duplicate_id_warnings,  # pyright: ignore[reportPrivateUsage]
    _suggest_roles,  # pyright: ignore[reportPrivateUsage]
    _union_axis,  # pyright: ignore[reportPrivateUsage]
    _warning,  # pyright: ignore[reportPrivateUsage]
    read_table,
)

SOURCE_FILE = "source_file"
"""Name of the file-name column added when several files are read."""

# Spectral-file readers: format_hint → (reader, file extensions).
_READERS: dict[str, tuple[Callable[[Path], TableImport], frozenset[str]]] = {
    "jcamp": (read_jcamp, frozenset({".jdx", ".dx", ".jcamp"})),
    "spc": (read_spc, frozenset({".spc"})),
    "spa": (read_spa, frozenset({".spa"})),
    "perkinelmer": (read_perkinelmer, frozenset({".sp"})),
}


def read_file(path: str | Path, format_hint: str = "auto") -> TableImport:
    """Read one file with the reader for its format (see module rules)."""
    path = Path(path)
    ext = path.suffix.lower()
    for hint, (reader, extensions) in _READERS.items():
        if format_hint == hint or (format_hint == "auto" and ext in extensions):
            return reader(path)
    return read_table(path, format_hint)


def read_files(paths: Sequence[str | Path], format_hint: str = "auto") -> TableImport:
    """Read every path and concatenate them (one path → its table unchanged).

    Raises
    ------
    ValueError
        ``paths`` is empty.
    VibeChemError
        As the readers; ``IMPORT_FILE_INVALID`` reason ``duplicate_column``
        (+ ``column``) when a merged column name occurs twice.
    """
    if not paths:
        raise ValueError("paths must not be empty")
    imports = [read_file(path, format_hint) for path in paths]
    if len(imports) == 1:
        return imports[0]
    return _concatenate(imports, [Path(path).name for path in paths])


def _concatenate(imports: Sequence[TableImport], file_names: Sequence[str]) -> TableImport:
    # Step 1: split each table into its spectral columns and the other columns.
    spectral = [_spectral_names(table) for table in imports]
    axes = [np.array([float(n) for n in names]) for names in spectral]
    axis, n_axes = _union_axis(axes)
    first_name: dict[float, str] = {}
    for names in spectral:
        for name in names:
            first_name.setdefault(float(name), name)
    other_names: list[str] = []
    for table, names in zip(imports, spectral, strict=True):
        other_names += [n for n in table.columns if n not in names and n not in other_names]
    # Step 2: merged columns.
    columns: dict[str, NDArray[np.float64] | NDArray[np.str_]] = {
        SOURCE_FILE: np.array(
            [
                name
                for table, name in zip(imports, file_names, strict=True)
                for _ in range(table.n_rows)
            ],
            dtype=np.str_,
        )
    }
    for name in other_names:
        _add_column(columns, name, _merged_other(imports, name))
    position = {value: i for i, value in enumerate(axis.tolist())}
    blocks: list[NDArray[np.float64]] = []
    for table, names, file_axis in zip(imports, spectral, axes, strict=True):
        block = np.full((table.n_rows, len(axis)), np.nan)
        for name, value in zip(names, file_axis.tolist(), strict=True):
            block[:, position[value]] = table.columns[name]
        blocks.append(block)
    matrix = np.concatenate(blocks)
    for i, value in enumerate(axis.tolist()):
        _add_column(columns, first_name[value], matrix[:, i].copy())
    # Step 3: roles and warnings for the merged table.
    header = list(columns)
    roles = _suggest_roles(header, range(len(header) - len(axis), len(header)), columns)
    unit = next(
        (
            t.suggested_roles["spectral_columns"]["axis_unit"]
            for t in imports
            if t.suggested_roles["spectral_columns"] is not None
        ),
        None,
    )
    if unit is not None and roles["spectral_columns"] is not None:
        roles["spectral_columns"]["axis_unit"] = unit
    warnings: list[ImportWarning] = [
        w for t in imports for w in t.warnings if w["code"] != IMPORT_DUPLICATE_SAMPLE_IDS
    ]
    sample_id = roles["sample_id"]
    if isinstance(sample_id, str) and columns[sample_id].dtype.kind == "U":
        warnings.extend(_duplicate_id_warnings(columns[sample_id].tolist()))
    if n_axes > 1:
        warnings.append(_warning(IMPORT_AXIS_MISMATCH, axes=n_axes))
    for array in columns.values():
        array.flags.writeable = False
    return TableImport(
        detected_format=imports[0].detected_format,
        columns=MappingProxyType(columns),
        suggested_roles=roles,
        warnings=tuple(warnings),
        needs_interpolation=n_axes > 1 or any(t.needs_interpolation for t in imports),
    )


def _spectral_names(table: TableImport) -> list[str]:
    spectral = table.suggested_roles["spectral_columns"]
    if spectral is None:
        return []
    names = list(table.columns)
    return names[names.index(spectral["from"]) : names.index(spectral["to"]) + 1]


def _merged_other(
    imports: Sequence[TableImport], name: str
) -> NDArray[np.float64] | NDArray[np.str_]:
    parts = [table.columns.get(name) for table in imports]
    if any(part is not None and part.dtype.kind == "U" for part in parts):
        texts: list[str] = []
        for table, part in zip(imports, parts, strict=True):
            if part is None:
                texts += [""] * table.n_rows
            elif part.dtype.kind == "U":
                texts += part.tolist()
            else:
                texts += ["" if math.isnan(v) else repr(v) for v in part.tolist()]
        return np.array(texts, dtype=np.str_)
    return np.concatenate(
        [np.full(t.n_rows, np.nan) if p is None else p for t, p in zip(imports, parts, strict=True)]
    )


def _add_column(
    columns: dict[str, NDArray[np.float64] | NDArray[np.str_]],
    name: str,
    values: NDArray[np.float64] | NDArray[np.str_],
) -> None:
    if name in columns:
        raise VibeChemError(IMPORT_FILE_INVALID, {"reason": "duplicate_column", "column": name})
    columns[name] = values
