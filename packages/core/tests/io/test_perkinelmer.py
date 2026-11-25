# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_perkinelmer.py
"""Tests for ``vibechem_core.io.perkinelmer`` (DATA_MODEL.md §2.5, PerkinElmer ``.sp``).

Independent expected values for ``single_PE_spectrum.sp``: the minimum and
maximum intensity that the instrument software wrote into the file's own block
35699 (not read by our reader), the point count and x step of blocks 35701 and
35700, and a hand decode of the intensity block located by its byte offset
(scratch script). Hand-made files are written here byte by byte. Values of the
ported upstream reader are only regression checks (TECH_STACK.md §11.1 rule 3).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import IMPORT_FILE_INVALID, TableImport
from vibechem_core.io.perkinelmer import read_perkinelmer
from vibechem_core.testing import assert_reference

DATA = Path(__file__).parent / "data"
SAMPLE = "single_PE_spectrum.sp"
FILE = "values written by the instrument software in the file (blocks 35699–35701)"
HAND = "hand decode of block 35708 at byte 1251 (scratch script)"


def matrix(table: TableImport) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in table.columns if n != "title"]
    return np.array([float(n) for n in names]), np.stack([table.columns[n] for n in names], 1)


def block(block_id: int, body: bytes) -> bytes:
    return struct.pack("<Hi", block_id, len(body)) + body


def sp_file(
    y: list[float],
    first: float = 4000.0,
    last: float = 750.0,
    *,
    unit: bytes | None = b"cm-1",
    n: int | None = None,
    drop: int | None = None,
    variable: int = 29981,
) -> bytes:
    """A minimal ``.sp`` file: signature, description and one data-set block."""
    members = [
        block(35711, b"\x00" * 10),  # a block the reader skips
        block(35698, struct.pack("<Hdd", variable, first, last)),
        block(35701, struct.pack("<HI", 29995, len(y) if n is None else n)),
        block(35708, struct.pack(f"<HI{len(y)}d", 29974, 8 * len(y), *y)),
    ]
    if unit is not None:
        members.append(block(35703, struct.pack("<HH", 29987, len(unit)) + unit))
    if drop is not None:
        members = [m for m in members if struct.unpack_from("<H", m)[0] != drop]
    head = b"PEPE" + b"2D constant interval DataSet file".ljust(40, b"\x00")
    return head + block(120, b"".join(members))


def write(tmp_path: Path, content: bytes, name: str = "s.sp") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def reason(exc: pytest.ExceptionInfo[VibeChemError]) -> object:
    assert exc.value.code == IMPORT_FILE_INVALID
    return exc.value.params["reason"]


# --- sample file ---


def test_sample_file_matches_values_in_the_file() -> None:
    table = read_perkinelmer(DATA / SAMPLE)
    x, y = matrix(table)
    assert table.detected_format == "perkinelmer"
    assert y.shape == (1, 1626)
    for label, actual, expected, source in [
        ("first x", x[0], 4000.0, FILE),
        ("last x", x[-1], 750.0, FILE),
        ("x step", x[1] - x[0], -2.0, FILE),
        ("min y", y.min(), 81.4703369140625, FILE),
        ("max y", y.max(), 101.32456970214844, FILE),
        ("y[0]", y[0, 0], 100.71570587158203, HAND),
    ]:
        assert_reference(
            method=f"PerkinElmer .sp reader ({label})",
            dataset=SAMPLE,
            actual=actual,
            expected=expected,
            rtol=1e-12,
            atol=0.0,
            source=source,
        )
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "cm-1"
    assert table.columns["title"].tolist() == ["single_PE_spectrum"]
    assert table.warnings == ()


def test_sample_file_quasar_regression() -> None:
    # osp tests/test_readers.py TestPerkinElmerReader (regression check only).
    x, y = matrix(read_perkinelmer(DATA / SAMPLE))
    assert y[0, 4] == 100.65028381347656
    assert (x.min(), x.max()) == (750.0, 4000.0)


# --- hand-made files (values known by construction) ---


def test_hand_made_file(tmp_path: Path) -> None:
    table = read_perkinelmer(write(tmp_path, sp_file([1.0, -2.5, 3.0], 1000.0, 1100.0, unit=b"nm")))
    x, y = matrix(table)
    np.testing.assert_array_equal(x, [1000.0, 1050.0, 1100.0])
    np.testing.assert_array_equal(y[0], [1.0, -2.5, 3.0])
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "nm"


def test_unknown_or_missing_unit_is_guessed(tmp_path: Path) -> None:
    for unit in (b"%T", None):
        table = read_perkinelmer(write(tmp_path, sp_file([1.0, 2.0], 4000.0, 400.0, unit=unit)))
        spectral = table.suggested_roles["spectral_columns"]
        assert spectral is not None
        assert spectral["axis_unit"] == "cm-1"  # guessed: decreasing axis


@pytest.mark.parametrize(
    "content",
    [
        sp_file([1.0, 2.0], drop=35698),  # no x range
        sp_file([1.0, 2.0], drop=35701),  # no point count
        sp_file([1.0, 2.0], drop=35708),  # no intensities
        sp_file([1.0, 2.0], n=3),  # point count differs from the intensities
        sp_file([1.0, 2.0], variable=1),  # wrong variable ID
        sp_file([1.0, 2.0])[:-3],  # truncated
        b"XXXX" + sp_file([1.0, 2.0])[4:],  # wrong signature
        b"PEPE",
        b"",
    ],
)
def test_corrupt_files(tmp_path: Path, content: bytes) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_perkinelmer(write(tmp_path, content))
    assert reason(exc) == "corrupt"


def test_member_running_past_its_parent_is_corrupt(tmp_path: Path) -> None:
    content = bytearray(sp_file([1.0, 2.0]))
    struct.pack_into("<i", content, 44 + 6 + 2, 10**6)  # size of the first member
    with pytest.raises(VibeChemError) as exc:
        read_perkinelmer(write(tmp_path, bytes(content)))
    assert reason(exc) == "corrupt"


def test_single_point_is_empty(tmp_path: Path) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_perkinelmer(write(tmp_path, sp_file([1.0])))
    assert reason(exc) == "empty"
