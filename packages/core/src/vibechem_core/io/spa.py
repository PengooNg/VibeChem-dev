# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/spa.py
# Ported from quasars/orange-spectroscopy orangecontrib/spectroscopy/io/omnic.py (SPAReader)
# at commit df9246d7d6d7537b18ef5852e30c6ce212ebc92c (GPL-3.0-or-later), itself based on code
# by Zack Gainsforth.
# Original copyright: Canadian Light Source, Biolab UL, Soleil, Elettra and contributors.
# Changes: byte parsing only; Orange Table replaced by `spectra_import`; bounds checks; a data
# section whose length differs from the header's point count is corrupt (upstream: index axis);
# title and axis unit read from the file.
"""Thermo OMNIC SPA reader (DATA_MODEL.md §2.5, ``format_hint`` ``spa``).

Rules
-----
- One file is one spectrum (one row). The section count is at byte 294; the
  section directory starts at byte 304 (16-byte entries: type, 32-bit offset,
  length; 22-byte entries with a 64-bit offset when the file signature
  contains ``Exte``). Section type 2 is the spectrum header
  (point count, first and last x), type 3 the intensities (float32).
- The axis is ``n`` evenly spaced points from the first to the last x. A file
  without these sections, or whose intensity section does not hold exactly
  ``n`` values, is ``corrupt``.
- Text column ``title``: the spectrum title (bytes 30–285, Latin-1), or the
  file name without extension when it is empty.
- Axis unit from the header's x-unit code: 1 → ``cm-1``; others → guessed as
  for CSV.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from vibechem_core.errors import VibeChemError
from vibechem_core.io.table import IMPORT_FILE_INVALID, TableImport, spectra_import

_DIRECTORY = 304
_HEADER_SECTION, _DATA_SECTION = 2, 3
_UNITS = {1: "cm-1"}


def read_spa(path: str | Path) -> TableImport:
    """Read a Thermo OMNIC SPA file (``.spa``) as a one-row table.

    Raises
    ------
    VibeChemError
        ``IMPORT_FILE_INVALID`` with reason ``corrupt``, ``empty`` or ``axis``.
    OSError
        The file cannot be opened.
    """
    path = Path(path)
    content = path.read_bytes()
    # Step 1: section directory (type, offset, length per entry).
    extended = b"Exte" in _take(content, 0, 30)
    entry, layout = (22, "<hqi") if extended else (16, "<hii")
    (count,) = struct.unpack_from("<h", _take(content, 294, 2))
    sections: dict[int, tuple[int, int]] = {}
    for i in range(max(count, 0)):
        kind, offset, length = struct.unpack_from(
            layout, _take(content, _DIRECTORY + entry * i, struct.calcsize(layout))
        )
        sections.setdefault(kind, (offset, length))
    if _HEADER_SECTION not in sections or _DATA_SECTION not in sections:
        raise _invalid("corrupt")
    # Step 2: spectrum header: point count, x unit, first and last x.
    offset, _ = sections[_HEADER_SECTION]
    _, n, x_unit, _, first, last = struct.unpack_from("<iiiiff", _take(content, offset, 24))
    # Step 3: intensities, exactly n float32 values.
    offset, length = sections[_DATA_SECTION]
    if n < 1 or length != 4 * n:
        raise _invalid("corrupt")
    y = np.frombuffer(_take(content, offset, length), dtype="<f4").astype(np.float64)
    # Step 4: one row with the title.
    title = content[30:286].split(b"\x00", 1)[0].decode("latin-1").strip() or path.stem
    x = np.linspace(first, last, n)
    return spectra_import("spa", [(x, y)], _UNITS.get(x_unit), {"title": [title]})


def _take(content: bytes, position: int, size: int) -> bytes:
    """``size`` bytes at ``position``; a file that ends earlier is corrupt."""
    if position < 0 or position + size > len(content):
        raise _invalid("corrupt")
    return content[position : position + size]


def _invalid(reason: str) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason})
