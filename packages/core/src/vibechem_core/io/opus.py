# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/opus.py
"""Bruker OPUS reader (DATA_MODEL.md §2.5, ``format_hint`` ``opus``).

Wraps the ``brukeropus`` package (MIT, TECH_STACK.md §1.2), imported lazily.
Block choice follows orange-spectroscopy's OPUS reader (behaviour only, no
code): by default the first data block of the file.

Rules
-----
- Extensions ``.0``, ``.1``, … (any number). One file gives one spectrum (one
  row) from one 1-D data block, chosen by ``block``: ``auto`` (the first data
  block the library lists, in file-directory order), ``absorbance``
  (``a``), ``sample`` (single-channel sample spectrum, ``sm``) or ``reference``
  (single-channel reference spectrum, ``rf``). A block missing from the file →
  ``IMPORT_FILE_INVALID`` reason ``unsupported`` (``feature`` ``opus_block``).
- Files with only data series (time-resolved, maps) are ``unsupported``
  (``feature`` ``opus_series``); a file the library does not recognise, or any
  library failure, is ``corrupt``.
- Intensities are the block's values times its scaling factor (``CSF``); the
  axis is ``NPT`` evenly spaced points from ``FXV`` to ``LXV`` (library rules).
- Text column ``title``: the sample name (``SNM``), or the file name without
  extension when it is empty.
- Axis unit from the block's ``DXU``: ``WN`` → ``cm-1``, ``MI`` → ``um``;
  others → guessed as for CSV.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Literal

from vibechem_core.errors import ErrorParam, VibeChemError
from vibechem_core.io.table import IMPORT_FILE_INVALID, TableImport, spectra_import

OpusBlock = Literal["auto", "absorbance", "sample", "reference"]
_KEYS = {"absorbance": "a", "sample": "sm", "reference": "rf"}
_UNITS = {"WN": "cm-1", "MI": "um"}


def is_opus_extension(ext: str) -> bool:
    """True for OPUS file extensions: a dot followed by digits (``.0``, ``.12``)."""
    return len(ext) > 1 and ext[0] == "." and ext[1:].isdigit()


def read_opus(path: str | Path, block: OpusBlock = "auto") -> TableImport:
    """Read a Bruker OPUS file as a one-row table (see module rules).

    Raises
    ------
    ValueError
        ``block`` is not one of the allowed values.
    VibeChemError
        ``IMPORT_FILE_INVALID`` with reason ``corrupt``, ``unsupported``
        (+ ``feature``: ``opus_block`` with ``block``, or ``opus_series``),
        ``empty`` or ``axis``.
    OSError
        The file cannot be opened.
    """
    if block != "auto" and block not in _KEYS:
        raise ValueError(f"unknown OPUS block {block!r}")
    path = Path(path)
    with path.open("rb"):  # OSError for a missing file, as the other readers
        pass
    # Step 1: parse with the library (any failure on untrusted bytes is "corrupt").
    try:
        with warnings.catch_warnings():
            # brukeropus 1.4.3: invalid escape in a docstring (SyntaxWarning on first import).
            warnings.simplefilter("ignore", SyntaxWarning)
            from brukeropus.file import read_opus as _read  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs]  (lazy import)
        opus: Any = _read(str(path))
    except Exception as exc:  # untrusted file: any parser failure is "invalid"
        raise _invalid("corrupt") from exc
    if not opus:
        raise _invalid("corrupt")
    # Step 2: choose the data block.
    keys: list[str] = list(opus.data_keys)
    if not keys:
        if opus.series_keys:
            raise _invalid("unsupported", feature="opus_series")
        raise _invalid("corrupt")
    key = keys[0] if block == "auto" else _KEYS[block]
    if key not in keys:
        raise _invalid("unsupported", feature="opus_block", block=block)
    data = getattr(opus, key)
    # Step 3: one row with the sample name.
    title = str(getattr(opus.params, "snm", "") or "").strip()
    unit = _UNITS.get(str(data.params.dxu))
    return spectra_import("opus", [(data.x, data.y)], unit, {"title": [title or path.stem]})


def _invalid(reason: str, **params: ErrorParam) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason, **params})
