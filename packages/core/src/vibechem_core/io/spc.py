# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/spc.py
# Ported from quasars/orange-spectroscopy orangecontrib/spectroscopy/utils/spc/{spc,sub,global_fun}.py
# and io/omnic.py (SPCReader) at commit df9246d7d6d7537b18ef5852e30c6ce212ebc92c (GPL-3.0-or-later);
# that code is Rohan Isaac's spc (https://github.com/rohanisaac/spc, commit f35b90f, GPL-3.0).
# Original copyright: Rohan Isaac; orange-spectroscopy: Canadian Light Source, Biolab UL, Soleil,
# Elettra and contributors.
# Changes: byte parsing only (new LSB format); per-subfile x read as float32 (upstream: scaled
# integers); signed exponents; bounds checks; Orange Table replaced by `spectra_import`; old,
# MSB and Shimadzu formats, log block, plotting and text export dropped.
"""Thermo Galactic SPC reader (DATA_MODEL.md §2.5, ``format_hint`` ``spc``).

Rules
-----
- Only the new little-endian format (version byte ``0x4B``) is read; other
  versions (old ``0x4D``, MSB ``0x4C``, Shimadzu ``0xCF``) give
  ``IMPORT_FILE_INVALID`` reason ``unsupported`` (``feature`` ``spc_version``).
- Each subfile is one spectrum (one row). The axis is, by header flag: a float32
  array per subfile (``TXYXYS``), one float32 array after the header
  (``TXVALS``), or ``fnpts`` evenly spaced points from ``ffirst`` to ``flast``.
  Subfiles with different axes are put on the union axis (``IMPORT_AXIS_MISMATCH``).
- Intensities: float32 when the exponent is ``0x80``, else 32-bit integers times
  ``2**(exp - 32)`` (16-bit times ``2**(exp - 16)`` with ``TSPREC``); the exponent
  is the subfile's in multifiles (``TMULTI``), else the header's.
- Text column ``title``: the header comment (``fcmnt``), or the file name without
  extension when it is empty.
- Axis unit from ``fxtype``: 1 (wavenumber) and 13 (Raman shift) → ``cm-1``,
  2 → ``um``, 3 → ``nm``; others → guessed as for CSV.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from vibechem_core.errors import ErrorParam, VibeChemError
from vibechem_core.io.table import IMPORT_FILE_INVALID, TableImport, spectra_import

_HEADER_SIZE = 512
_SUBHEADER_SIZE = 32
_NEW_LSB = 0x4B
_FLOAT_EXPONENT = -128  # 0x80 as a signed byte
# Header flag bits (ftflgs).
_TSPREC, _TMULTI, _TXYXYS, _TXVALS = 0x01, 0x04, 0x40, 0x80
_UNITS = {1: "cm-1", 2: "um", 3: "nm", 13: "cm-1"}


def read_spc(path: str | Path) -> TableImport:
    """Read a Galactic SPC file (``.spc``): one row per subfile.

    Raises
    ------
    VibeChemError
        ``IMPORT_FILE_INVALID`` with reason ``corrupt`` (truncated or
        inconsistent file), ``unsupported`` (other format version), ``empty``
        or ``axis``.
    OSError
        The file cannot be opened.
    """
    path = Path(path)
    content = path.read_bytes()
    # Step 1: main header (first 29 bytes) and the comment.
    flags, version, _, exponent, npts, first, last, nsub, xtype = struct.unpack_from(
        "<BBBbiddiB", _take(content, 0, _HEADER_SIZE)
    )
    if version != _NEW_LSB:
        raise _invalid("unsupported", feature="spc_version", version=f"0x{version:02X}")
    comment = content[88:218].split(b"\x00", 1)[0].decode("latin-1").strip()
    xyxy, multi, short = bool(flags & _TXYXYS), bool(flags & _TMULTI), bool(flags & _TSPREC)
    if not multi:
        nsub = 1
    if nsub < 1 or (not xyxy and npts < 1):
        raise _invalid("corrupt")
    # Step 2: common axis, read now only when stored after the header.
    position = _HEADER_SIZE
    shared_x: NDArray[np.float64] | None = None
    if not xyxy and flags & _TXVALS:
        shared_x = _floats(content, position, npts)
        position += 4 * npts
    # Step 3: subfiles, one after another (the directory of XYXY files is not needed).
    xs: list[NDArray[np.float64]] = []
    ys: list[NDArray[np.float64]] = []
    for _ in range(nsub):
        (sub_exponent,) = struct.unpack_from("<b", _take(content, position + 1, 1))
        (sub_npts,) = struct.unpack_from("<i", _take(content, position + 16, 4))
        position += _SUBHEADER_SIZE
        n = sub_npts if xyxy else npts
        if n < 1:
            raise _invalid("corrupt")
        if xyxy:
            xs.append(_floats(content, position, n))
            position += 4 * n
        y, size = _intensities(content, position, n, sub_exponent if multi else exponent, short)
        ys.append(y)
        position += size
    # Step 4: table with one row per subfile.
    if xyxy:
        spectra = list(zip(xs, ys, strict=True))
    else:
        axis = shared_x if shared_x is not None else np.linspace(first, last, npts)
        spectra = [(axis, y) for y in ys]
    title = comment or path.stem
    return spectra_import("spc", spectra, _UNITS.get(xtype), {"title": [title] * nsub})


def _intensities(
    content: bytes, position: int, n: int, exponent: int, short: bool
) -> tuple[NDArray[np.float64], int]:
    """``n`` intensities at ``position`` and their size in bytes."""
    if exponent == _FLOAT_EXPONENT:
        return _floats(content, position, n), 4 * n
    if short:
        raw = np.frombuffer(_take(content, position, 2 * n), dtype="<i2")
        return raw.astype(np.float64) * 2.0 ** (exponent - 16), 2 * n
    raw = np.frombuffer(_take(content, position, 4 * n), dtype="<i4")
    return raw.astype(np.float64) * 2.0 ** (exponent - 32), 4 * n


def _floats(content: bytes, position: int, n: int) -> NDArray[np.float64]:
    return np.frombuffer(_take(content, position, 4 * n), dtype="<f4").astype(np.float64)


def _take(content: bytes, position: int, size: int) -> bytes:
    """``size`` bytes at ``position``; a file that ends earlier is corrupt."""
    if position + size > len(content):
        raise _invalid("corrupt")
    return content[position : position + size]


def _invalid(reason: str, **params: ErrorParam) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason, **params})
