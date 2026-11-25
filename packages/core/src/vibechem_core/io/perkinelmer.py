# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/io/perkinelmer.py
# Ported from quasars/orange-spectroscopy orangecontrib/spectroscopy/io/perkinelmer.py
# (PerkinElmerReader.read_sp) and utils/specio/specio.py (PerkinElmer.decode35698, decode35701,
# decode35708) at commit df9246d7d6d7537b18ef5852e30c6ce212ebc92c (GPL-3.0-or-later); the specio
# code is based on Specio (https://github.com/paris-saclay-cds/specio) and on software developed
# at the Diamond synchrotron.
# Original copyright: Canadian Light Source, Biolab UL, Soleil, Elettra and contributors;
# Specio: Copyright (c) 2017, Guillaume Lemaitre, BSD 3-Clause License (notice below).
# Changes: one flat walk over the members of the data-set block instead of the nested block
# search; metadata block (5104) not decoded; x unit from block 35703; bounds and variable-ID
# checks; Orange Table replaced by `spectra_import`; `.fsm` images dropped.
#
# BSD 3-Clause License (Specio)
#
# Copyright (c) 2017, Guillaume Lemaitre
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""PerkinElmer ``.sp`` reader (DATA_MODEL.md §2.5, ``format_hint`` ``perkinelmer``).

Rules
-----
- One file is one spectrum (one row). After the 4-byte signature ``PEPE`` and a
  40-byte description, the file is one data-set block; its members are blocks
  of ``(uint16 id, int32 size, body)``. Each body starts with a uint16
  variable ID that must match the block. Used blocks: 35698 (first and last x,
  float64), 35701 (point count, uint32), 35703 (x unit text), 35708
  (intensities, float64); other blocks are skipped.
- The axis is ``n`` evenly spaced points from the first to the last x. A file
  without the used blocks, with a wrong variable ID, a block running past its
  parent, or an intensity count other than ``n`` is ``corrupt``.
- Text column ``title``: the file name without extension.
- Axis unit from block 35703: ``cm-1`` → ``cm-1``, ``nm`` → ``nm``; others or
  missing → guessed as for CSV.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

from vibechem_core.errors import VibeChemError
from vibechem_core.io.table import IMPORT_FILE_INVALID, TableImport, spectra_import

_SIGNATURE = b"PEPE"
_START = 44  # signature (4) + description (40)
_BLOCK = struct.Struct("<Hi")
# Block id → expected variable id of its body.
_X_RANGE, _N_POINTS, _X_UNIT, _VALUES = 35698, 35701, 35703, 35708
_VARIABLES = {_X_RANGE: 29981, _N_POINTS: 29995, _X_UNIT: 29987, _VALUES: 29974}
_UNITS = {"cm-1": "cm-1", "nm": "nm"}


def read_perkinelmer(path: str | Path) -> TableImport:
    """Read a PerkinElmer spectrum file (``.sp``) as a one-row table.

    Raises
    ------
    VibeChemError
        ``IMPORT_FILE_INVALID`` with reason ``corrupt``, ``empty`` or ``axis``.
    OSError
        The file cannot be opened.
    """
    path = Path(path)
    content = path.read_bytes()
    if content[:4] != _SIGNATURE:
        raise _invalid("corrupt")
    # Step 1: members of the data-set block, by block id.
    _, size = _BLOCK.unpack(_take(content, _START, _BLOCK.size))
    end = _START + _BLOCK.size + size
    _take(content, _START, end - _START)
    bodies: dict[int, bytes] = {}
    position = _START + _BLOCK.size
    while position < end:
        block_id, size = _BLOCK.unpack(_take(content, position, _BLOCK.size))
        position += _BLOCK.size
        if size < 0 or position + size > end:
            raise _invalid("corrupt")
        if block_id in _VARIABLES:
            bodies.setdefault(block_id, content[position : position + size])
        position += size
    if any(block not in bodies for block in (_X_RANGE, _N_POINTS, _VALUES)):
        raise _invalid("corrupt")
    # Step 2: axis from the first and last x and the point count.
    first, last = struct.unpack("<dd", _body(bodies, _X_RANGE, 16))
    (n,) = struct.unpack("<I", _body(bodies, _N_POINTS, 4))
    # Step 3: intensities, exactly n float64 values.
    (n_bytes,) = struct.unpack("<I", _body(bodies, _VALUES, 4))
    values = _body(bodies, _VALUES, 4 + n_bytes)[4:]
    if n < 1 or n_bytes != 8 * n:
        raise _invalid("corrupt")
    y = np.frombuffer(values, dtype="<f8").astype(np.float64)
    # Step 4: one row; unit from the file when it is known.
    unit = None
    if _X_UNIT in bodies:
        (length,) = struct.unpack("<H", _body(bodies, _X_UNIT, 2))
        text = _body(bodies, _X_UNIT, 2 + length)[2:].decode("latin-1").strip()
        unit = _UNITS.get(text)
    x = np.linspace(first, last, n)
    return spectra_import("perkinelmer", [(x, y)], unit, {"title": [path.stem]})


def _body(bodies: dict[int, bytes], block_id: int, size: int) -> bytes:
    """``size`` bytes of a block body after its variable ID (which must match)."""
    body = bodies[block_id]
    if len(body) < 2 + size or struct.unpack_from("<H", body)[0] != _VARIABLES[block_id]:
        raise _invalid("corrupt")
    return body[2 : 2 + size]


def _take(content: bytes, position: int, size: int) -> bytes:
    """``size`` bytes at ``position``; a file that ends earlier is corrupt."""
    if size < 0 or position + size > len(content):
        raise _invalid("corrupt")
    return content[position : position + size]


def _invalid(reason: str) -> VibeChemError:
    return VibeChemError(IMPORT_FILE_INVALID, {"reason": reason})
