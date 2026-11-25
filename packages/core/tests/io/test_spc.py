# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_spc.py
"""Tests for ``vibechem_core.io.spc`` (DATA_MODEL.md §2.5, Galactic SPC import).

Expected values for the sample files come from spc-io 0.2.1 (MIT, an independent
SPC reader; run outside the project, it is not a dependency) and from small files
written here byte by byte from the Galactic SPC header layout (hand calculation).
Values of the ported upstream reader are not used (TECH_STACK.md §11.1 rule 3).
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import IMPORT_AXIS_MISMATCH, IMPORT_FILE_INVALID, TableImport
from vibechem_core.io.spc import read_spc
from vibechem_core.testing import assert_reference

DATA = Path(__file__).parent / "data"
SPC_IO = "spc-io 0.2.1 (independent SPC reader), to_dataframe_flattened()"


def matrix(table: TableImport) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in table.columns if n != "title"]
    return np.array([float(n) for n in names]), np.stack([table.columns[n] for n in names], 1)


def header(
    flags: int,
    npts: int,
    first: float,
    last: float,
    nsub: int,
    exponent: int = -128,
    xtype: int = 1,
    comment: bytes = b"hand made",
    version: int = 0x4B,
) -> bytes:
    head = struct.pack("<BBBbiddiB", flags, version, 0, exponent, npts, first, last, nsub, xtype)
    head = head.ljust(88, b"\x00") + comment.ljust(130, b"\x00")
    return head.ljust(512, b"\x00")


def subheader(exponent: int = -128, npts: int = 0) -> bytes:
    return struct.pack("<Bbhfffiif4s", 0, exponent, 0, 0.0, 0.0, 0.0, npts, 0, 0.0, b"")


def write(tmp_path: Path, content: bytes) -> Path:
    path = tmp_path / "s.spc"
    path.write_bytes(content)
    return path


def reason(exc: pytest.ExceptionInfo[VibeChemError]) -> object:
    assert exc.value.code == IMPORT_FILE_INVALID
    return exc.value.params["reason"]


# --- sample files from two instrument vendors ---


@pytest.mark.parametrize(
    ("name", "n", "x0", "x_end", "y0", "y_mid", "y_end", "unit"),
    [
        # PerkinElmer Spectrum 2000 FT-IR (polystyrene), transmittance
        (
            "Ft-ir.spc",
            1776,
            4000.0,
            450.0,
            95.13749694824219,
            96.27213287353516,
            94.88349151611328,
            "cm-1",
        ),
        # Thermo Nicolet FT-Raman (Raman shift)
        (
            "raman.spc",
            3632,
            3996.8232421875,
            -3005.9560546875005,
            0.01710212230682373,
            1.237623691558838,
            0.03207695484161377,
            "cm-1",
        ),
    ],
)
def test_vendor_files_match_independent_reader(
    name: str, n: int, x0: float, x_end: float, y0: float, y_mid: float, y_end: float, unit: str
) -> None:
    table = read_spc(DATA / name)
    x, y = matrix(table)
    assert table.detected_format == "spc"
    assert y.shape == (1, n)
    for label, actual, expected in [
        ("first x", x[0], x0),
        ("last x", x[-1], x_end),
        ("y[0]", y[0, 0], y0),
        (f"y[{n // 2}]", y[0, n // 2], y_mid),
        ("y[-1]", y[0, -1], y_end),
    ]:
        assert_reference(
            method=f"SPC reader ({label})",
            dataset=name,
            actual=actual,
            expected=expected,
            rtol=1e-12,
            atol=0.0,
            source=SPC_IO,
        )
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == unit
    assert table.warnings == ()
    assert not table.needs_interpolation


def test_polystyrene_band_near_1601() -> None:
    # Sanity check from the literature: polystyrene's aromatic band at 1601 cm-1 is a
    # local transmittance minimum.
    x, y = matrix(read_spc(DATA / "Ft-ir.spc"))
    window = (x > 1580) & (x < 1620)
    assert abs(x[window][np.argmin(y[0, window])] - 1601) <= 4


def test_multifile_even_x_one_row_per_subfile() -> None:
    table = read_spc(DATA / "nir.spc")
    x, y = matrix(table)
    assert y.shape == (20, 700)
    np.testing.assert_array_equal(x[[0, 1, -1]], [1100.0, 1102.0, 2498.0])
    for label, actual, expected in [
        ("subfile 0 y[0]", y[0, 0], 0.00020048394799232483),
        ("subfile 0 y[350]", y[0, 350], 0.015757396817207336),
        ("subfile 19 y[0]", y[19, 0], 0.0004443895595613867),
        ("subfile 19 y[-1]", y[19, -1], 2.5556952095939778e-05),
    ]:
        assert_reference(
            method=f"SPC reader ({label})",
            dataset="nir.spc",
            actual=actual,
            expected=expected,
            rtol=1e-12,
            atol=0.0,
            source=SPC_IO,
        )
    assert table.columns["title"].tolist() == ["NIR Spectra Example"] * 20
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "nm"


def test_xyxy_subfiles_on_union_axis() -> None:
    # Each subfile has its own float32 x array (TXYXYS). Upstream decodes them as
    # scaled integers (first x 16943.6); the header's ffirst and spc-io give 43.9.
    table = read_spc(DATA / "m_xyxy.spc")
    x, y = matrix(table)
    assert y.shape == (512, 261)  # spc-io: 512 subfiles, 261 distinct x values
    assert table.needs_interpolation
    assert table.warnings[0]["code"] == IMPORT_AXIS_MISMATCH
    sub0 = dict(zip(x.tolist(), y[0].tolist(), strict=True))
    assert_reference(
        method="SPC reader (XYXY subfile 0 at x 43.9)",
        dataset="m_xyxy.spc",
        actual=sub0[float(np.float32(43.9))],
        expected=6823.0,
        rtol=0.0,
        atol=0.0,
        source=SPC_IO,
    )
    assert sub0[float(np.float32(25.85))] == 3144.0
    assert np.count_nonzero(~np.isnan(y[0])) == 8  # spc-io: subfile 0 has 8 points
    assert x[0] > x[-1]  # direction of the first subfile (decreasing)


# --- hand-made files (values known by construction) ---


def test_even_x_32_bit_integers_scaled_by_exponent(tmp_path: Path) -> None:
    # exponent 30: y = int * 2**(30 - 32) = int / 4
    data = struct.pack("<3i", 4, -8, 10)
    table = read_spc(write(tmp_path, header(0, 3, 10.0, 30.0, 1, exponent=30) + subheader() + data))
    x, y = matrix(table)
    np.testing.assert_array_equal(x, [10.0, 20.0, 30.0])
    np.testing.assert_array_equal(y[0], [1.0, -2.0, 2.5])
    assert table.columns["title"].tolist() == ["hand made"]


def test_16_bit_integers_and_global_x_array(tmp_path: Path) -> None:
    # TSPREC | TXVALS; exponent 16: y = int * 2**0; x stored after the header
    xs = struct.pack("<3f", 900.0, 950.0, 1000.0)
    data = struct.pack("<3h", 7, -3, 300)
    content = header(0x01 | 0x80, 3, 0.0, 0.0, 1, exponent=16, xtype=3) + xs + subheader() + data
    table = read_spc(write(tmp_path, content))
    x, y = matrix(table)
    np.testing.assert_array_equal(x, [900.0, 950.0, 1000.0])
    np.testing.assert_array_equal(y[0], [7.0, -3.0, 300.0])
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "nm"


def test_multifile_uses_each_subfile_exponent(tmp_path: Path) -> None:
    # TMULTI, header exponent 0 is ignored; subfile 1 is float, subfile 2 has exponent 33
    sub1 = subheader(-128) + struct.pack("<2f", 1.5, 2.5)
    sub2 = subheader(33) + struct.pack("<2i", 3, 4)
    table = read_spc(write(tmp_path, header(0x04, 2, 1.0, 2.0, 2, exponent=0) + sub1 + sub2))
    np.testing.assert_array_equal(matrix(table)[1], [[1.5, 2.5], [6.0, 8.0]])


def test_empty_comment_uses_file_name(tmp_path: Path) -> None:
    content = header(0, 2, 1.0, 2.0, 1, comment=b"") + subheader() + struct.pack("<2f", 1, 2)
    assert read_spc(write(tmp_path, content)).columns["title"].tolist() == ["s"]


@pytest.mark.parametrize("version", [0x4D, 0x4C, 0xCF, 0x00])
def test_other_versions_are_unsupported(tmp_path: Path, version: int) -> None:
    content = header(0, 2, 1.0, 2.0, 1, version=version) + subheader() + struct.pack("<2f", 1, 2)
    with pytest.raises(VibeChemError) as exc:
        read_spc(write(tmp_path, content))
    assert reason(exc) == "unsupported"
    assert exc.value.params == {
        "reason": "unsupported",
        "feature": "spc_version",
        "version": f"0x{version:02X}",
    }


@pytest.mark.parametrize(
    "content",
    [
        b"",
        header(0, 2, 1.0, 2.0, 1)[:100],
        header(0, 2, 1.0, 2.0, 1) + subheader() + struct.pack("<f", 1),  # one point short
        header(0, 0, 1.0, 2.0, 1) + subheader(),  # no points
        header(0x04, 2, 1.0, 2.0, 0) + subheader(),  # multifile without subfiles
        header(0x04, 2, 1.0, 2.0, 1_000_000_000) + subheader() + struct.pack("<2f", 1, 2),
        header(0x40, 0, 1.0, 2.0, 1) + subheader(npts=-5),  # XYXY with a negative count
        header(0x40, 0, 1.0, 2.0, 1) + subheader(npts=2**30),  # count larger than the file
    ],
)
def test_truncated_or_inconsistent_files_are_corrupt(tmp_path: Path, content: bytes) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_spc(write(tmp_path, content))
    assert reason(exc) == "corrupt"


def test_non_monotonic_global_x_is_rejected(tmp_path: Path) -> None:
    xs = struct.pack("<3f", 1.0, 3.0, 2.0)
    content = header(0x80, 3, 0.0, 0.0, 1) + xs + subheader() + struct.pack("<3f", 1, 2, 3)
    with pytest.raises(VibeChemError) as exc:
        read_spc(write(tmp_path, content))
    assert reason(exc) == "axis"
