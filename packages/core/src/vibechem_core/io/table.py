# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/table.py
"""CSV/TSV and Excel table reader with role suggestions (DATA_MODEL.md §2.5, step 1).

``read_table`` reads one file into named columns and suggests a role for each
column: sample ID, group, class label, Y, metadata, and the run of spectral
columns whose headers are the axis values. The user confirms or changes the
roles when the import is committed (step 2), so the guesses here only need to be
good defaults.

Text files are parsed with the standard library ``csv`` module (no pyarrow in
core, TECH_STACK.md §3.1); ``.xlsx`` files with openpyxl, imported lazily.

Rules
-----
- Lines whose first non-blank character is ``#`` are comments, and so are lines
  starting with ``;`` unless ``;`` is the delimiter; blank lines and empty rows
  are skipped. A line is one row: quoted cells cannot span lines.
- Delimiter: tab for ``.tsv``/``.tab``; otherwise the one of tab, ``,``, ``;`` that
  splits the first line not starting with ``;`` into most fields, else runs of
  whitespace. Decimal commas are not supported.
- The file has no header (e.g. Bruker ``.dpt``) when every cell of the first row
  and of the first column is a finite number, the first column is strictly
  monotonic and there are more rows than columns: the first column is the axis
  and every further column is one spectrum. The result then has one row per
  spectrum.
- Otherwise the first row is the header. An empty header cell is named
  ``column_<n>`` (1-based); such a column is dropped if all its cells are empty.
- Spectral columns: the longest run (at least 2) of adjacent columns whose
  headers are finite numbers in strictly increasing or decreasing order. Their
  cells become float64; an empty cell or one that is not a finite number becomes
  NaN and is counted in an ``IMPORT_NON_NUMERIC_VALUES`` warning.
- Other columns are float64 when every non-empty cell is a number (empty → NaN),
  else text. The suggested sample-ID column always stays text, so IDs such as
  ``007`` keep their leading zeros.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from itertools import pairwise
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypedDict

import numpy as np
from numpy.typing import ArrayLike, NDArray

from vibechem_core.errors import ErrorParam, VibeChemError

IMPORT_FORMAT_UNKNOWN = "IMPORT_FORMAT_UNKNOWN"
"""The file type is not recognised (DATA_MODEL.md §7); params ``format``."""
IMPORT_FILE_INVALID = "IMPORT_FILE_INVALID"
"""The file cannot be read as a table (DATA_MODEL.md §7); params ``reason`` (+ details)."""
IMPORT_DUPLICATE_SAMPLE_IDS = "IMPORT_DUPLICATE_SAMPLE_IDS"
"""Warning: sample IDs occur more than once; params ``count`` = number of such IDs."""
IMPORT_NON_NUMERIC_VALUES = "IMPORT_NON_NUMERIC_VALUES"
"""Warning: spectral cells that are empty or not finite numbers (read as NaN); params ``count``, ``column``."""
IMPORT_AXIS_MISMATCH = "IMPORT_AXIS_MISMATCH"
"""Warning: spectra on different axes were put on the union axis (missing points NaN); params ``axes``."""

TableFormat = Literal["csv", "tsv", "xlsx", "jcamp", "spc"]

_TEXT_EXTENSIONS = {".csv": None, ".txt": None, ".dpt": None, ".tsv": "\t", ".tab": "\t"}
_EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}

# Normalised header names (lower case, without spaces, "_" and "-") per role.
_SAMPLE_ID_NAMES = {"sample", "sampleid", "samplename", "id", "name", "specimen"}
_GROUP_NAMES = {"group", "groupid", "batch", "subject"}
_CLASS_NAMES = {"class", "classlabel", "label", "category"}

# Axis-unit guess: decreasing axes and values above this are wavenumbers (cm-1).
_MAX_NM = 2600.0


# Suggested spectral run (``suggested_roles.spectral_columns``, DATA_MODEL.md §2.5).
# "from" is a Python keyword, hence the functional TypedDict form.
SpectralColumns = TypedDict(
    "SpectralColumns", {"from": str, "to": str, "count": int, "axis_unit": str}
)


class SuggestedRoles(TypedDict):
    """``suggested_roles`` of DATA_MODEL.md §2.5."""

    sample_id: str | None
    group_id: str | None
    y: list[str]
    class_label: str | None
    metadata: list[str]
    spectral_columns: SpectralColumns | None


class ImportWarning(TypedDict):
    """One ``warnings`` item of DATA_MODEL.md §2.5."""

    code: str
    params: dict[str, ErrorParam]


@dataclass(frozen=True, eq=False)
class TableImport:
    """A file read as a table, with suggested roles (DATA_MODEL.md §2.5 step 1).

    Attributes
    ----------
    detected_format : {"csv", "tsv", "xlsx", "jcamp", "spc"}
        Format actually read (``tsv`` when the delimiter was a tab).
    columns : mapping of str to ndarray
        Column name → 1-D array (float64 or text), all of length ``n_rows``,
        in file order. This is the core ``Table`` form (DATA_MODEL.md §4.1).
    suggested_roles : mapping
        ``sample_id``, ``group_id``, ``class_label`` (column name or None),
        ``y``, ``metadata`` (lists of names) and ``spectral_columns``
        (``{"from", "to", "count", "axis_unit"}`` or None), as in §2.5.
    warnings : tuple of mapping
        ``{"code": ..., "params": {...}}`` items.
    needs_interpolation : bool
        True when spectra on different axes were put on their union axis
        (``IMPORT_AXIS_MISMATCH``, DATA_MODEL.md §2.5).
    """

    detected_format: TableFormat
    columns: Mapping[str, NDArray[np.float64] | NDArray[np.str_]]
    suggested_roles: SuggestedRoles
    warnings: tuple[ImportWarning, ...]
    needs_interpolation: bool = False

    @property
    def n_rows(self) -> int:
        """Number of data rows (spectra)."""
        return len(next(iter(self.columns.values())))

    @property
    def n_columns(self) -> int:
        """Number of columns."""
        return len(self.columns)


def read_table(
    path: str | Path,
    format_hint: str = "auto",
    *,
    delimiter: str | None = None,
) -> TableImport:
    """Read a CSV/TSV or Excel file and suggest column roles.

    Parameters
    ----------
    path : str or Path
        File to read.
    format_hint : {"auto", "csv", "tsv", "xlsx"}
        ``auto`` chooses by file extension (``.csv``, ``.txt``, ``.dpt``,
        ``.tsv``, ``.tab``, ``.xlsx``, ``.xlsm``).
    delimiter : str, optional
        Delimiter for text files; default: tab for ``tsv``, else sniffed.

    Raises
    ------
    VibeChemError
        ``IMPORT_FORMAT_UNKNOWN`` for an unsupported format or extension;
        ``IMPORT_FILE_INVALID`` when the content is not a readable table.
    OSError
        The file cannot be opened.
    """
    path = Path(path)
    if delimiter is not None and len(delimiter) != 1:
        raise ValueError(f"delimiter must be one character, got {delimiter!r}")
    # Step 1: choose the reader from the hint or the extension.
    fmt, delimiter = _choose_format(path, format_hint, delimiter)
    # Step 2: read the raw cells as text, one list per row.
    if fmt == "xlsx":
        rows = _read_xlsx_rows(path)
    else:
        rows, delimiter = _read_text_rows(path, delimiter)
        fmt = "tsv" if delimiter == "\t" else "csv"
    # Step 3: header, column types and role suggestions.
    return _build_table(fmt, rows)


def _invalid(reason: str, **params: ErrorParam) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason, **params})


def _choose_format(
    path: Path, format_hint: str, delimiter: str | None
) -> tuple[TableFormat, str | None]:
    if format_hint == "auto":
        ext = path.suffix.lower()
        if ext in _EXCEL_EXTENSIONS:
            return "xlsx", None
        if ext not in _TEXT_EXTENSIONS:
            raise VibeChemError(IMPORT_FORMAT_UNKNOWN, {"format": ext or path.name})
        return "csv", delimiter if delimiter is not None else _TEXT_EXTENSIONS[ext]
    if format_hint == "xlsx":
        return "xlsx", None
    if format_hint == "tsv":
        return "tsv", delimiter if delimiter is not None else "\t"
    if format_hint == "csv":
        return "csv", delimiter
    raise VibeChemError(IMPORT_FORMAT_UNKNOWN, {"format": format_hint})


def _read_text_rows(path: Path, delimiter: str | None) -> tuple[list[list[str]], str | None]:
    """Data lines of a text file split into cells; returns the delimiter used."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise _invalid("encoding") from exc
    # Split on line ends only: str.splitlines() would also break at form feeds etc.
    lines = [line.removesuffix("\r") for line in text.split("\n")]
    lines = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if delimiter is None and lines:
        first = next((line for line in lines if not line.lstrip().startswith(";")), lines[0])
        delimiter = _sniff_delimiter(first)
    if delimiter != ";":
        lines = [line for line in lines if not line.lstrip().startswith(";")]
    if delimiter is None:
        return [line.split() for line in lines], None
    return list(csv.reader(lines, delimiter=delimiter)), delimiter


def _sniff_delimiter(first_line: str) -> str | None:
    """Tab, ``,`` or ``;``: whichever splits the line into most fields; None = whitespace."""
    fields = {d: len(next(csv.reader([first_line], delimiter=d))) for d in ("\t", ",", ";")}
    best = max(fields, key=fields.__getitem__)  # ties: first in order
    return best if fields[best] > 1 else None


def _read_xlsx_rows(path: Path) -> list[list[str]]:
    """Cells of the first worksheet as text (cached values; formulas are not evaluated)."""
    import openpyxl  # noqa: PLC0415  (lazy: keeps `import vibechem_core` light)

    try:
        # A file object, not the path: openpyxl refuses paths without an Excel extension.
        with path.open("rb") as file:
            workbook = openpyxl.load_workbook(
                file, read_only=True, data_only=True, keep_links=False
            )
            try:
                sheet = workbook.worksheets[0]
                sheet.reset_dimensions()  # do not trust the stored sheet size (may be stale)
                rows = [[_cell_text(v) for v in row] for row in sheet.iter_rows(values_only=True)]
            finally:
                workbook.close()
    except OSError:
        raise
    except Exception as exc:  # untrusted file: any parser failure is "invalid"
        raise _invalid("corrupt") from exc
    # Without a trusted size, rows end at their last stored cell: pad them.
    width = max((len(row) for row in rows), default=0)
    return [row + [""] * (width - len(row)) for row in rows]


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)  # round-trips exactly
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return str(value)


def _to_number(cell: str) -> float | None:
    """A cell as float: empty → NaN, not a finite number → None."""
    cell = cell.strip()
    if not cell:
        return math.nan
    if "_" in cell:  # float() accepts "1_000"; a table cell with "_" is text
        return None
    try:
        value = float(cell)
    except ValueError:
        return None
    return None if math.isinf(value) else value


def _finite_number(cell: str) -> float | None:
    value = _to_number(cell)
    return None if value is None or math.isnan(value) else value


def _build_table(fmt: TableFormat, rows: list[list[str]]) -> TableImport:
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise _invalid("empty")
    width = len(rows[0])
    for number, row in enumerate(rows, start=1):
        if len(row) != width:
            raise _invalid("row_length", row=number, expected=width, found=len(row))

    # Step 3a: headerless numeric file → first column is the axis, columns are spectra.
    if _is_headerless(rows):
        if width < 2:
            raise _invalid("no_spectra")
        header = [row[0].strip() for row in rows]
        cells = [row[1:] for row in rows]  # column-major: one axis point, one cell per spectrum
    else:
        if len(rows) < 2:
            raise _invalid("empty")
        cells = [list(column) for column in zip(*rows[1:], strict=True)]
        # An empty header cell over an empty column (e.g. a trailing delimiter) is dropped.
        keep = [
            i for i, cell in enumerate(rows[0]) if cell.strip() or any(c.strip() for c in cells[i])
        ]
        header = [rows[0][i].strip() or f"column_{i + 1}" for i in keep]
        cells = [cells[i] for i in keep]
    counts = Counter(header)
    duplicates = [name for name in header if counts[name] > 1]
    if duplicates:
        raise _invalid("duplicate_column", column=duplicates[0])

    # Step 3b: spectral run, column types, roles and warnings.
    spectral = _spectral_run(header)
    warnings: list[ImportWarning] = []
    columns: dict[str, NDArray[np.float64] | NDArray[np.str_]] = {}
    bad_count, bad_column = 0, None
    for i, name in enumerate(header):
        if i in spectral:
            values = [_finite_number(c) for c in cells[i]]
            n_bad = sum(v is None for v in values)
            if n_bad and bad_column is None:
                bad_column = name
            bad_count += n_bad
            columns[name] = np.array([math.nan if v is None else v for v in values])
        else:
            columns[name] = _typed_column(cells[i])
    roles = _suggest_roles(header, spectral, columns)
    sample_id = roles["sample_id"]
    if isinstance(sample_id, str):
        ids = [c.strip() for c in cells[header.index(sample_id)]]
        columns[sample_id] = np.array(ids, dtype=np.str_)
        warnings.extend(_duplicate_id_warnings(ids))
    if bad_count:
        warnings.append(_warning(IMPORT_NON_NUMERIC_VALUES, count=bad_count, column=bad_column))
    for array in columns.values():
        array.flags.writeable = False
    return TableImport(
        detected_format=fmt,
        columns=MappingProxyType(columns),
        suggested_roles=roles,
        warnings=tuple(warnings),
    )


def _is_headerless(rows: Sequence[Sequence[str]]) -> bool:
    """All-numeric first row and first column, a monotonic first column, more rows than columns."""
    if any(_finite_number(cell) is None for cell in rows[0]):
        return False
    if len(rows) == 1:
        return len(rows[0]) == 1  # a lone number: headerless, then "no_spectra"
    if len(rows) <= len(rows[0]):
        return False  # wide: a numeric header row over spectra
    axis = [_finite_number(row[0]) for row in rows]
    values = [v for v in axis if v is not None]
    if len(values) != len(axis):
        return False
    steps = {math.copysign(1.0, b - a) if b != a else 0.0 for a, b in pairwise(values)}
    return steps in ({1.0}, {-1.0})


def _warning(code: str, **params: ErrorParam) -> ImportWarning:
    return {"code": code, "params": params}


def _duplicate_id_warnings(ids: Iterable[str]) -> list[ImportWarning]:
    repeated = sum(n > 1 for i, n in Counter(ids).items() if i)  # "" = missing
    return [_warning(IMPORT_DUPLICATE_SAMPLE_IDS, count=repeated)] if repeated else []


def _typed_column(cells: Iterable[str]) -> NDArray[np.float64] | NDArray[np.str_]:
    texts = [c.strip() for c in cells]
    numbers = [_to_number(c) for c in texts]
    if any(v is None for v in numbers) or all(not c for c in texts):
        return np.array(texts, dtype=np.str_)
    return np.array(numbers, dtype=np.float64)


def _spectral_run(header: Sequence[str]) -> range:
    """Indices of the longest run (≥ 2) of monotonic numeric headers; empty if none."""
    best = range(0)
    start = 0
    while start < len(header):
        if _finite_number(header[start]) is None:
            start += 1
            continue
        stop, direction, turned = start + 1, 0.0, False
        while stop < len(header):
            value = _finite_number(header[stop])
            previous = _finite_number(header[stop - 1])
            if value is None or previous is None or value == previous:
                break
            step = math.copysign(1.0, value - previous)
            if direction and step != direction:
                turned = True
                break
            direction = step
            stop += 1
        if stop - start >= 2 and stop - start > len(best):
            best = range(start, stop)
        # A run that ended by turning round shares its last column with the next run.
        start = stop - 1 if turned else stop
    return best


def _normalised(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "").replace("-", "")


def _suggest_roles(
    header: Sequence[str],
    spectral: range,
    columns: Mapping[str, np.ndarray],
) -> SuggestedRoles:
    other = [name for i, name in enumerate(header) if i not in spectral]
    texts = [name for name in other if columns[name].dtype.kind == "U"]

    # Step 3c: names first; else the first text column with unique, non-empty values.
    sample_id = next((n for n in other if _normalised(n) in _SAMPLE_ID_NAMES), None) or next(
        (n for n in texts if all(columns[n]) and len(set(columns[n])) == len(columns[n])), None
    )
    group_id = next((n for n in other if n != sample_id and _normalised(n) in _GROUP_NAMES), None)
    class_label = next(
        (n for n in texts if n != sample_id and _normalised(n) in _CLASS_NAMES), None
    )
    taken = {sample_id, group_id, class_label}
    y = [n for n in other if n not in taken and columns[n].dtype.kind == "f"]
    metadata = [n for n in other if n not in taken and columns[n].dtype.kind == "U"]

    spectral_columns: SpectralColumns | None = None
    if spectral:
        names = [header[i] for i in spectral]
        values = [float(n) for n in names]
        decreasing = values[1] < values[0]
        unit = "cm-1" if decreasing or max(values) > _MAX_NM else "nm"
        spectral_columns = {
            "from": names[0],
            "to": names[-1],
            "count": len(names),
            "axis_unit": unit,
        }
    return {
        "sample_id": sample_id,
        "group_id": group_id,
        "y": y,
        "class_label": class_label,
        "metadata": metadata,
        "spectral_columns": spectral_columns,
    }


def spectra_import(
    fmt: TableFormat,
    spectra: Sequence[tuple[ArrayLike, ArrayLike]],
    axis_unit: str | None,
    text_columns: Mapping[str, Sequence[str]] | None = None,
) -> TableImport:
    """Spectra read from a spectral file (JCAMP-DX, SPC) as a ``TableImport``.

    One row per spectrum ``(x, y)``: the text columns first, then one float64
    column per axis value, named ``repr(float(value))``. Spectra on different
    axes are put on the union axis (in the direction of the first spectrum),
    missing points NaN, with an ``IMPORT_AXIS_MISMATCH`` warning and
    ``needs_interpolation``. Non-finite intensities become NaN
    (``IMPORT_NON_NUMERIC_VALUES``). ``axis_unit`` None → guessed as for CSV.

    Raises
    ------
    VibeChemError
        ``IMPORT_FILE_INVALID``: ``empty`` (no spectrum, or one with fewer than
        2 points), ``corrupt`` (x and y lengths differ), ``axis`` (x not finite
        and strictly monotonic).
    """
    # Step 1: check every spectrum; non-finite intensities become NaN.
    if not spectra:
        raise _invalid("empty")
    axes: list[NDArray[np.float64]] = []
    values: list[NDArray[np.float64]] = []
    bad_x: list[float] = []
    for x_in, y_in in spectra:
        x = np.asarray(x_in, dtype=np.float64)
        y = np.asarray(y_in, dtype=np.float64)
        if x.ndim != 1 or x.shape != y.shape:
            raise _invalid("corrupt")
        if len(x) < 2:
            raise _invalid("empty")
        if not _strictly_monotonic(x):
            raise _invalid("axis")
        finite = np.isfinite(y)
        bad_x.extend(x[np.logical_not(finite)].tolist())
        axes.append(x)
        values.append(np.where(finite, y, np.nan))
    # Step 2: common axis, one row per spectrum.
    axis, n_axes = _union_axis(axes)
    names = [repr(v) for v in axis.tolist()]
    rows = [_on_axis(axis, x, y) for x, y in zip(axes, values, strict=True)]
    matrix = np.stack(rows)
    warnings: list[ImportWarning] = []
    if bad_x:
        position = {v: i for i, v in enumerate(axis.tolist())}
        column = names[min(position[v] for v in bad_x)]
        warnings.append(_warning(IMPORT_NON_NUMERIC_VALUES, count=len(bad_x), column=column))
    # Step 3: columns, roles and warnings.
    columns: dict[str, NDArray[np.float64] | NDArray[np.str_]] = {
        name: np.array(cells, dtype=np.str_) for name, cells in (text_columns or {}).items()
    }
    n_text = len(columns)
    for i, name in enumerate(names):
        columns[name] = matrix[:, i].copy()
    header = list(columns)
    roles = _suggest_roles(header, range(n_text, len(header)), columns)
    if axis_unit is not None and roles["spectral_columns"] is not None:
        roles["spectral_columns"]["axis_unit"] = axis_unit
    sample_id = roles["sample_id"]
    if isinstance(sample_id, str):
        warnings.extend(_duplicate_id_warnings(columns[sample_id].tolist()))
    if n_axes > 1:
        warnings.append(_warning(IMPORT_AXIS_MISMATCH, axes=n_axes))
    for array in columns.values():
        array.flags.writeable = False
    return TableImport(
        detected_format=fmt,
        columns=MappingProxyType(columns),
        suggested_roles=roles,
        warnings=tuple(warnings),
        needs_interpolation=n_axes > 1,
    )


def _strictly_monotonic(x: NDArray[np.float64]) -> bool:
    steps = np.diff(x)
    return bool(np.isfinite(x).all() and ((steps > 0).all() or (steps < 0).all()))


def _union_axis(axes: Sequence[NDArray[np.float64]]) -> tuple[NDArray[np.float64], int]:
    """Union of strictly monotonic axes, ordered like the first; and the number of distinct axes.

    Empty axes (a file without spectral columns) are left out; an axis and its
    reverse are the same axis.
    """
    distinct: list[NDArray[np.float64]] = []
    for axis in axes:
        if len(axis) and not any(
            np.array_equal(axis, seen) or np.array_equal(axis[::-1], seen) for seen in distinct
        ):
            distinct.append(axis)
    if not distinct:
        return np.empty(0), 1
    if len(distinct) == 1:
        return distinct[0], 1
    union = np.unique(np.concatenate(distinct))
    first = next((a for a in axes if len(a) >= 2), union)
    return (union[::-1] if first[0] > first[-1] else union), len(distinct)


def _on_axis(
    axis: NDArray[np.float64], x: NDArray[np.float64], y: NDArray[np.float64]
) -> NDArray[np.float64]:
    """``y`` placed on ``axis``, which contains every value of ``x``; other points NaN."""
    if np.array_equal(axis, x):
        return y.copy()
    descending = len(axis) >= 2 and axis[0] > axis[-1]
    index = np.searchsorted(axis[::-1] if descending else axis, x)
    row = np.full(len(axis), np.nan)
    row[len(axis) - 1 - index if descending else index] = y
    return row
