# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/jcamp.py
"""JCAMP-DX reader (DATA_MODEL.md §2.5, ``format_hint`` ``jcamp``).

Wraps the ``jcamp`` package (MIT, TECH_STACK.md §1.2), imported lazily. It
decodes AFFN and ASDF data (SQZ, DIF, DUP) in ``##XYDATA=(X++(Y..Y))`` and
``(XY..XY)`` tables and applies ``##XFACTOR``/``##YFACTOR``.

Rules
-----
- One file is one spectrum (one row). Compound files (``##DATA TYPE=LINK``) and
  peak tables are not supported (``IMPORT_FILE_INVALID``, reason
  ``unsupported``).
- The number of decoded points must equal ``##NPOINTS`` when the file gives it
  (the library only prints a message); otherwise ``corrupt``.
- Text column ``title``: ``##TITLE`` without a ``$$`` comment, or the file name
  without extension when that is empty.
- Axis unit from ``##XUNITS``: ``1/CM`` → ``cm-1``, ``NANOMETERS`` → ``nm``,
  ``MICROMETERS`` → ``um``; any other value → guessed as for CSV.
"""

from __future__ import annotations

import contextlib
import io
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from vibechem_core.errors import VibeChemError
from vibechem_core.io.table import IMPORT_FILE_INVALID, TableImport, spectra_import

_UNITS = {"1/CM": "cm-1", "NANOMETERS": "nm", "MICROMETERS": "um"}


def read_jcamp(path: str | Path) -> TableImport:
    """Read a JCAMP-DX file (``.jdx``, ``.dx``) as a one-row table.

    Raises
    ------
    VibeChemError
        ``IMPORT_FILE_INVALID`` with reason ``corrupt``, ``unsupported``
        (+ ``feature``: ``compound`` or ``peak_table``), ``empty`` or ``axis``.
    OSError
        The file cannot be opened.
    """
    import jcamp  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs]  (lazy import)

    path = Path(path)
    # Step 1: parse with the library; its diagnostics go to stdout, so capture them.
    with path.open("rb") as file, contextlib.redirect_stdout(io.StringIO()):
        try:
            header: dict[str, Any] = jcamp.read(file)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        except Exception as exc:  # untrusted file: any parser failure is "invalid"
            raise _invalid("corrupt") from exc
    # Step 2: reject what is not one spectrum.
    if "children" in header:
        raise _invalid("unsupported", feature="compound")
    if "xydata" not in header and "xypoints" not in header:
        if "peak table" in header:
            raise _invalid("unsupported", feature="peak_table")
        raise _invalid("corrupt")
    x: NDArray[np.float64] = header["x"]
    y: NDArray[np.float64] = header["y"]
    npoints: object = header.get("npoints")
    if len(x) != len(y) or (isinstance(npoints, int) and npoints != len(y)):
        raise _invalid("corrupt")
    # Step 3: one row, title column, unit from the file.
    title = _text(header, "title") or path.stem
    unit = _UNITS.get(_text(header, "xunits").upper())
    return spectra_import("jcamp", [(x, y)], unit, {"title": [title]})


def _text(header: dict[str, Any], key: str) -> str:
    """A header value as text without its ``$$`` comment (the library keeps comments)."""
    return str(header.get(key, "")).split("$$", 1)[0].strip()


def _invalid(reason: str, **params: str) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason, **params})
