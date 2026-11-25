# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_spa.py
"""Tests for ``vibechem_core.io.spa`` (DATA_MODEL.md §2.5, Thermo OMNIC SPA import).

Expected values for ``sample1.spa`` come from spectrochempy 1.4.0 ``read_omnic``
(CeCILL-B, an independent OMNIC reader; run outside the project, it is not a
dependency). Hand-made files are written here byte by byte from the section
layout. Values of the ported upstream reader are only regression checks
(TECH_STACK.md §11.1 rule 3).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import IMPORT_FILE_INVALID, TableImport
from vibechem_core.io.spa import read_spa
from vibechem_core.testing import assert_reference

DATA = Path(__file__).parent / "data"
SCP = "spectrochempy 1.4.0 read_omnic (independent OMNIC reader)"


def matrix(table: TableImport) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in table.columns if n != "title"]
    return np.array([float(n) for n in names]), np.stack([table.columns[n] for n in names], 1)


def spa_file(
    y: list[float],
    first: float = 4000.0,
    last: float = 400.0,
    *,
    x_unit: int = 1,
    title: bytes = b"hand made",
    extended: bool = False,
    data_length: int | None = None,
    sections: tuple[int, ...] = (2, 3),
) -> bytes:
    """A minimal SPA file: signature, title, section directory, header, data."""
    signature = b"Spectral Exte File" if extended else b"Spectral Data File"
    head = (signature.ljust(30, b"\x00") + title.ljust(256, b"\x00")).ljust(294, b"\x00")
    head += struct.pack("<h", len(sections))
    head = head.ljust(304, b"\x00")
    entry, layout = (22, "<hqi") if extended else (16, "<hii")
    start = 304 + entry * len(sections)
    spec_header = struct.pack("<iiiifff", 3, len(y), x_unit, 17, first, last, 0.0)
    data = struct.pack(f"<{len(y)}f", *y)
    payloads = {2: spec_header, 3: data}
    directory = b""
    body = b""
    for kind in sections:
        payload = payloads[kind]
        length = data_length if kind == 3 and data_length is not None else len(payload)
        directory += struct.pack(layout, kind, start + len(body), length).ljust(entry, b"\x00")
        body += payload
    return head + directory + body


def write(tmp_path: Path, content: bytes, name: str = "s.spa") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def reason(exc: pytest.ExceptionInfo[VibeChemError]) -> object:
    assert exc.value.code == IMPORT_FILE_INVALID
    return exc.value.params["reason"]


# --- sample file ---


def test_sample_file_matches_independent_reader() -> None:
    table = read_spa(DATA / "sample1.spa")
    x, y = matrix(table)
    assert table.detected_format == "spa"
    assert y.shape == (1, 1738)
    for label, actual, expected in [
        ("first x", x[0], 3999.703125),
        ("last x", x[-1], 649.903564453125),
        ("x[100]", x[100], 3806.853),
        ("y[0]", y[0, 0], 0.043998364359140396),
        ("y[100]", y[0, 100], 0.023094354197382927),
        ("y[-5]", y[0, -5], 0.8969618082046509),
    ]:
        assert_reference(
            method=f"SPA reader ({label})",
            dataset="sample1.spa",
            actual=actual,
            expected=expected,
            rtol=1e-6 if label.startswith("x") else 1e-12,  # spectrochempy rounds x to float32
            atol=0.0,
            source=SCP,
        )
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "cm-1"
    title = table.columns["title"][0]
    assert title.startswith("Z:\\COM-SMIS\\")
    assert "12x12µm²" in title
    assert table.warnings == ()


def test_sample_file_quasar_regression() -> None:
    # osp tests/test_readers.py TestSpa: 1738 points (regression check only).
    _, y = matrix(read_spa(DATA / "sample1.spa"))
    assert y.shape[1] == 1738


# --- hand-made files (values known by construction) ---


def test_hand_made_file(tmp_path: Path) -> None:
    table = read_spa(write(tmp_path, spa_file([1.0, 2.5, -3.0], 1000.0, 1200.0)))
    x, y = matrix(table)
    np.testing.assert_array_equal(x, [1000.0, 1100.0, 1200.0])
    np.testing.assert_array_equal(y[0], [1.0, 2.5, -3.0])
    assert table.columns["title"].tolist() == ["hand made"]


def test_extended_directory(tmp_path: Path) -> None:
    content = spa_file([1.0, 2.0], 10.0, 20.0, extended=True, sections=(3, 2))
    _, y = matrix(read_spa(write(tmp_path, content)))
    np.testing.assert_array_equal(y[0], [1.0, 2.0])


@pytest.mark.parametrize(("code", "unit"), [(1, "cm-1"), (32, "cm-1"), (3, "nm"), (4, "um")])
def test_unit_codes(tmp_path: Path, code: int, unit: str) -> None:
    # Raman shift (32) on an increasing axis below 2600 would be guessed as nm.
    table = read_spa(write(tmp_path, spa_file([1.0, 2.0], 200.0, 2000.0, x_unit=code)))
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == unit


def test_empty_title_uses_file_name_and_other_unit_is_guessed(tmp_path: Path) -> None:
    content = spa_file([1.0, 2.0], 1100.0, 1200.0, title=b"", x_unit=7)
    table = read_spa(write(tmp_path, content, "my_spectrum.spa"))
    assert table.columns["title"].tolist() == ["my_spectrum"]
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "nm"  # guessed from the axis (increasing, < 2600)


@pytest.mark.parametrize(
    "content",
    [
        spa_file([1.0, 2.0], sections=(2,)),  # no data section
        spa_file([1.0, 2.0], sections=(3,)),  # no header section
        spa_file([1.0, 2.0], data_length=12),  # data length differs from the point count
        spa_file([1.0, 2.0])[:-4],  # truncated data
        spa_file([1.0, 2.0])[:300],  # truncated directory
        b"",
    ],
)
def test_corrupt_files(tmp_path: Path, content: bytes) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_spa(write(tmp_path, content))
    assert reason(exc) == "corrupt"


def test_offset_outside_the_file_is_corrupt(tmp_path: Path) -> None:
    content = bytearray(spa_file([1.0, 2.0]))
    struct.pack_into("<i", content, 304 + 16 + 2, 10**9)  # data section offset
    with pytest.raises(VibeChemError) as exc:
        read_spa(write(tmp_path, bytes(content)))
    assert reason(exc) == "corrupt"


def test_single_point_is_empty(tmp_path: Path) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_spa(write(tmp_path, spa_file([1.0])))
    assert reason(exc) == "empty"
