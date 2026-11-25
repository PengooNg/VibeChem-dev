# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/wdf.py
# Ported from alchem0x2A/py-wdf-reader (renishawWiRE 0.1.16) renishawWiRE/wdfReader.py and
# renishawWiRE/types.py at commit e22fa62add9a080d9eb80863a8b9fa426eb573dd (MIT); that code is
# inspired by Alex Henderson's WDF reader (doi:10.5281/zenodo.495477), and its constants credit
# the Gwyddion project's renishaw.c.
# Original copyright: Copyright (c) 2022 T.Tian (MIT License, notice below).
# Changes: byte parsing of the WDF1, XLST and DATA blocks only (no ORGN, WMAP, white-light
# image, PIL or printing); bounds checks; maps rejected; Orange-style reader replaced by
# `spectra_import`.
#
# MIT License
#
# Copyright (c) 2022 T.Tian
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Renishaw WiRE WDF reader (DATA_MODEL.md §2.5, ``format_hint`` ``wdf``).

Rules
-----
- The file is a chain of blocks: 4-byte name, int32 id, int64 size (header
  included), data from byte 16. The first block must be ``WDF1`` of size 512.
  A block that runs past the end of the file is corrupt only when its data
  is read (WiRE files may end inside an unused last block).
- ``WDF1`` gives the points per spectrum (byte 0x3C), the number of spectra
  measured (``count``, byte 0x48; may be below the capacity of an unfinished
  measurement), the x-list length (byte 0x58), the measurement type (byte 0x84)
  and the title (bytes 0xF0–0x1FF, UTF-8).
- Single spectra, series and unspecified measurements give one row per
  spectrum on the ``XLST`` axis (float32; its length must equal the points per
  spectrum) with the ``DATA`` intensities (float32, ``count`` times points).
  Positions from ``ORGN`` (stage x/y/z, time) are not read. Maps (measurement
  type 3 or a ``WMAP`` block) give ``IMPORT_FILE_INVALID`` reason
  ``unsupported`` (``feature`` ``wdf_map``; imaging is P2).
- Text column ``title``: the WDF1 title, or the file name without extension
  when it is empty.
- Axis unit from the ``XLST`` unit code: 1 (Raman shift) → ``cm-1``,
  3 → ``nm``, 5 → ``um``; others → guessed as for CSV.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from vibechem_core.errors import ErrorParam, VibeChemError
from vibechem_core.io.table import IMPORT_FILE_INVALID, TableImport, spectra_import

_BLOCK = struct.Struct("<4siq")
_HEADER_SIZE = 512
_DATA_OFFSET = 16
_MAPPING = 3
_UNITS = {1: "cm-1", 3: "nm", 5: "um"}


def read_wdf(path: str | Path) -> TableImport:
    """Read a Renishaw WiRE file (``.wdf``): one row per spectrum.

    Raises
    ------
    VibeChemError
        ``IMPORT_FILE_INVALID`` with reason ``corrupt``, ``unsupported``
        (``feature`` ``wdf_map``), ``empty`` or ``axis``.
    OSError
        The file cannot be opened.
    """
    path = Path(path)
    content = path.read_bytes()
    # Step 1: block chain (first block of each name wins).
    blocks: dict[bytes, tuple[int, int]] = {}
    position = 0
    while position + _BLOCK.size <= len(content):
        name, _, size = _BLOCK.unpack_from(content, position)
        if size < _BLOCK.size:
            raise _invalid("corrupt")
        blocks.setdefault(name, (position, size))
        position += size
    if blocks.get(b"WDF1") != (0, _HEADER_SIZE) or b"XLST" not in blocks or b"DATA" not in blocks:
        raise _invalid("corrupt")
    # Step 2: WDF1 header.
    n_points, _, count = struct.unpack_from("<iqq", content, 0x3C)
    (x_length,) = struct.unpack_from("<i", content, 0x58)
    (measurement,) = struct.unpack_from("<i", content, 0x84)
    if measurement == _MAPPING or b"WMAP" in blocks:
        raise _invalid("unsupported", feature="wdf_map")
    if count < 1:
        raise _invalid("empty")
    if n_points < 1 or x_length != n_points:
        raise _invalid("corrupt")
    # Step 3: axis (XLST) and intensities (DATA), each inside its block.
    x_start, x_size = blocks[b"XLST"]
    (x_unit,) = struct.unpack_from("<i", _within(content, x_start, x_size, 4, 4))
    x = _floats(content, x_start, x_size, 8, n_points)
    data_start, data_size = blocks[b"DATA"]
    y = _floats(content, data_start, data_size, 0, count * n_points).reshape(count, n_points)
    # Step 4: one row per spectrum.
    title = content[0xF0:_HEADER_SIZE].split(b"\x00", 1)[0].decode("utf-8", "replace").strip()
    spectra = [(x, row) for row in y]
    return spectra_import(
        "wdf", spectra, _UNITS.get(x_unit), {"title": [title or path.stem] * count}
    )


def _floats(content: bytes, start: int, size: int, offset: int, n: int) -> NDArray[np.float64]:
    """``n`` float32 values ``offset`` bytes into a block's data."""
    raw = _within(content, start, size, offset, 4 * n)
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def _within(content: bytes, start: int, size: int, offset: int, length: int) -> bytes:
    """``length`` bytes at ``offset`` into the data of the block at ``start``."""
    begin = start + _DATA_OFFSET + offset
    if begin + length > min(start + size, len(content)):
        raise _invalid("corrupt")
    return content[begin : begin + length]


def _invalid(reason: str, **params: ErrorParam) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason, **params})
