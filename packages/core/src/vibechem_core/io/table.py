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
- Lines whose first non-blank character is ``;`` or ``#`` are comments; blank
  lines and empty rows are skipped.
- Delimiter: tab for ``.tsv``/``.tab``; otherwise the one of tab, ``,``, ``;`` that
  splits the first data line into most fields, else runs of whitespace.
- If every cell of the first row is a finite number, the file has no header
  (e.g. Bruker ``.dpt``): the first column is the axis and every further column
  is one spectrum. The result then has one row per spectrum.
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
from pathlib import Path
from types import MappingProxyType
from typing import Literal, TypedDict

import numpy as np
from numpy.typing import NDArray

from vibechem_core.errors import ErrorParam, VibeChemError

IMPORT_FORMAT_UNKNOWN = "IMPORT_FORMAT_UNKNOWN"
"""The file type is not recognised (DATA_MODEL.md §7); params ``format``."""
IMPORT_FILE_INVALID = "IMPORT_FILE_INVALID"
"""The file cannot be read as a table (DATA_MODEL.md §7); params ``reason`` (+ details)."""
IMPORT_DUPLICATE_SAMPLE_IDS = "IMPORT_DUPLICATE_SAMPLE_IDS"
"""Warning: sample IDs occur more than once; params ``count`` = number of such IDs."""
IMPORT_NON_NUMERIC_VALUES = "IMPORT_NON_NUMERIC_VALUES"
"""Warning: spectral cells that are empty or not finite numbers (read as NaN); params ``count``, ``column``."""

TableFormat = Literal["csv", "tsv", "xlsx"]

_TEXT_EXTENSIONS = {".csv": None, ".txt": None, ".dpt": None, ".tsv": "\t", ".tab": "\t"}
_EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
_COMMENT_PREFIXES = (";", "#")

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
    detected_format : {"csv", "tsv", "xlsx"}
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
    """

    detected_format: TableFormat
    columns: Mapping[str, NDArray[np.float64] | NDArray[np.str_]]
    suggested_roles: SuggestedRoles
    warnings: tuple[ImportWarning, ...]

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
    lines = [
        line
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith(_COMMENT_PREFIXES)
    ]
    if delimiter is None and lines:
        delimiter = _sniff_delimiter(lines[0])
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
                return [[_cell_text(v) for v in row] for row in sheet.iter_rows(values_only=True)]
            finally:
                workbook.close()
    except OSError:
        raise
    except Exception as exc:  # untrusted file: any parser failure is "invalid"
        raise _invalid("corrupt") from exc


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
    if all(_finite_number(cell) is not None for cell in rows[0]):
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
        ids = np.array([c.strip() for c in cells[header.index(sample_id)]])
        columns[sample_id] = ids
        repeated = sum(n > 1 for n in Counter(ids.tolist()).values())
        if repeated:
            warnings.append(_warning(IMPORT_DUPLICATE_SAMPLE_IDS, count=repeated))
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


def _warning(code: str, **params: ErrorParam) -> ImportWarning:
    return {"code": code, "params": params}


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
        stop = start + 1
        direction = 0.0
        while stop < len(header):
            value = _finite_number(header[stop])
            previous = _finite_number(header[stop - 1])
            if value is None or previous is None or value == previous:
                break
            step = math.copysign(1.0, value - previous)
            if direction and step != direction:
                break
            direction = step
            stop += 1
        if stop - start >= 2 and stop - start > len(best):
            best = range(start, stop)
        start = stop
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
