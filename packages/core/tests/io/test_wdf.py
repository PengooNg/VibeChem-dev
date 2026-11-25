# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_wdf.py
"""Tests for ``vibechem_core.io.wdf`` (DATA_MODEL.md §2.5, Renishaw WiRE WDF import).

Expected values for ``sp.wdf`` come from rosettasciio 0.15.0
``rsciio.renishaw.file_reader`` (GPL-3.0, an independent WDF reader; run outside
the project, it is not a dependency). It returns the spectrum on an increasing
axis; the file stores it decreasing, which our reader keeps. rosettasciio
cannot read ``single-spectrum_undefined-type.wdf``; its values come from a hand
decode of the XLST and DATA blocks by byte offset (scratch script). Values of
renishawWiRE (the ported code, used by Quasar) are only regression checks
(TECH_STACK.md §11.1 rule 3). Hand-made files are written here byte by byte.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import IMPORT_FILE_INVALID, TableImport
from vibechem_core.io.wdf import read_wdf
from vibechem_core.testing import assert_reference

DATA = Path(__file__).parent / "data"
RSCIIO = "rosettasciio 0.15.0 rsciio.renishaw (independent WDF reader)"
HAND = "hand decode of the XLST and DATA blocks (scratch script)"


def matrix(table: TableImport) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in table.columns if n != "title"]
    return np.array([float(n) for n in names]), np.stack([table.columns[n] for n in names], 1)


def block(name: bytes, data: bytes) -> bytes:
    return struct.pack("<4siq", name, 0, 16 + len(data)) + data


def wdf_file(
    x: list[float],
    spectra: list[list[float]],
    *,
    measurement: int = 1,
    x_unit: int = 1,
    title: bytes = b"hand made",
    x_length: int | None = None,
    extra: bytes = b"",
    count: int | None = None,
) -> bytes:
    """A minimal WDF file: WDF1 header, DATA and XLST blocks."""
    header = bytearray(512 - 16)
    n = len(x)
    n_spectra = len(spectra) if count is None else count
    struct.pack_into("<iqq", header, 0x3C - 16, n, len(spectra), n_spectra)
    struct.pack_into("<i", header, 0x58 - 16, n if x_length is None else x_length)
    struct.pack_into("<ii", header, 0x80 - 16, 1, measurement)
    header[0xF0 - 16 : 0xF0 - 16 + len(title)] = title
    head = struct.pack("<4siq", b"WDF1", 1, 512) + bytes(header)
    values = [v for row in spectra for v in row]
    data = block(b"DATA", struct.pack(f"<{len(values)}f", *values))
    xlst = block(b"XLST", struct.pack(f"<ii{n}f", 1, x_unit, *x))
    return head + data + xlst + extra


def write(tmp_path: Path, content: bytes, name: str = "s.wdf") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def reason(exc: pytest.ExceptionInfo[VibeChemError]) -> object:
    assert exc.value.code == IMPORT_FILE_INVALID
    return exc.value.params["reason"]


# --- sample files ---


def test_single_spectrum_matches_independent_reader() -> None:
    table = read_wdf(DATA / "sp.wdf")
    x, y = matrix(table)
    assert table.detected_format == "wdf"
    assert y.shape == (1, 1015)
    for label, actual, expected in [
        ("first x", x[0], 2787.514404296875),
        ("last x", x[-1], 1226.2752685546875),
        ("y[0]", y[0, 0], 47.092708587646484),
        ("y[-1]", y[0, -1], 21.815458297729492),
        ("y[-5]", y[0, -5], 20.379457473754883),
    ]:
        assert_reference(
            method=f"WDF reader ({label})",
            dataset="sp.wdf",
            actual=actual,
            expected=expected,
            rtol=1e-12,
            atol=0.0,
            source=RSCIIO,
        )
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "cm-1"
    assert table.columns["title"].tolist() == ["Single scan measurement 1"]
    assert table.warnings == ()


def test_undefined_measurement_type_is_read() -> None:
    table = read_wdf(DATA / "single-spectrum_undefined-type.wdf")
    x, y = matrix(table)
    assert y.shape == (1, 1015)
    for label, actual, expected in [
        ("first x", x[0], 1338.296875),
        ("last x", x[-1], 78.728515625),
        ("y[0]", y[0, 0], 9.806330680847168),
        ("y[-1]", y[0, -1], 7.1900763511657715),
    ]:
        assert_reference(
            method=f"WDF reader ({label})",
            dataset="single-spectrum_undefined-type.wdf",
            actual=actual,
            expected=expected,
            rtol=1e-12,
            atol=0.0,
            source=HAND,
        )
    assert table.columns["title"].tolist() == ["Test file for WDF reader -------------"]


def test_sample_files_quasar_regression() -> None:
    # osp tests/test_readers.py TestWiREReaders (renishawWiRE; regression check only).
    for name, y4, low, high in [
        ("sp.wdf", 52.4945182800293, 1226.275269, 2787.514404),
        ("single-spectrum_undefined-type.wdf", -2.4491686820983887, 78.728516, 1338.296875),
    ]:
        x, y = matrix(read_wdf(DATA / name))
        assert y[0, 4] == y4
        assert x.min() == pytest.approx(low, abs=1e-6)
        assert x.max() == pytest.approx(high, abs=1e-6)


# --- hand-made files (values known by construction) ---


def test_series_gives_one_row_per_spectrum(tmp_path: Path) -> None:
    content = wdf_file([100.0, 200.0, 300.0], [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], measurement=2)
    table = read_wdf(write(tmp_path, content))
    x, y = matrix(table)
    np.testing.assert_array_equal(x, [100.0, 200.0, 300.0])
    np.testing.assert_array_equal(y, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    assert table.columns["title"].tolist() == ["hand made"] * 2


def test_unfinished_measurement_reads_count_spectra(tmp_path: Path) -> None:
    # capacity 2 (two rows of data space), but only one spectrum measured
    content = wdf_file([1.0, 2.0], [[7.0, 8.0], [0.0, 0.0]], count=1)
    _, y = matrix(read_wdf(write(tmp_path, content)))
    np.testing.assert_array_equal(y, [[7.0, 8.0]])


def test_empty_title_uses_file_name_and_unit_codes(tmp_path: Path) -> None:
    content = wdf_file([500.0, 600.0], [[1.0, 2.0]], title=b"", x_unit=3)
    table = read_wdf(write(tmp_path, content, "raman_01.wdf"))
    assert table.columns["title"].tolist() == ["raman_01"]
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "nm"


@pytest.mark.parametrize(
    "content",
    [
        wdf_file([1.0, 2.0], [[1.0, 2.0]], measurement=3),
        wdf_file([1.0, 2.0], [[1.0, 2.0]], extra=block(b"WMAP", b"\x00" * 8)),
    ],
)
def test_maps_are_unsupported(tmp_path: Path, content: bytes) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_wdf(write(tmp_path, content))
    assert reason(exc) == "unsupported"
    assert exc.value.params["feature"] == "wdf_map"


@pytest.mark.parametrize(
    "content",
    [
        wdf_file([1.0, 2.0], [[1.0, 2.0]], x_length=3),  # x list longer than the spectra
        wdf_file([1.0, 2.0], [[1.0, 2.0]], count=2),  # more spectra than DATA holds
        wdf_file([1.0, 2.0], [[1.0, 2.0]])[:-4],  # truncated last block
        b"WDF2" + wdf_file([1.0, 2.0], [[1.0, 2.0]])[4:],  # first block is not WDF1
        wdf_file([1.0, 2.0], [[1.0, 2.0]])[:512],  # no DATA or XLST
        b"",
    ],
)
def test_corrupt_files(tmp_path: Path, content: bytes) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_wdf(write(tmp_path, content))
    assert reason(exc) == "corrupt"


def test_block_size_below_header_is_corrupt(tmp_path: Path) -> None:
    content = bytearray(wdf_file([1.0, 2.0], [[1.0, 2.0]]))
    struct.pack_into("<q", content, 512 + 8, 4)  # DATA block size smaller than its header
    with pytest.raises(VibeChemError) as exc:
        read_wdf(write(tmp_path, bytes(content)))
    assert reason(exc) == "corrupt"


def test_no_spectrum_measured_is_empty(tmp_path: Path) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_wdf(write(tmp_path, wdf_file([1.0, 2.0], [[1.0, 2.0]], count=0)))
    assert reason(exc) == "empty"


def test_unused_last_block_may_be_truncated(tmp_path: Path) -> None:
    # single-spectrum_undefined-type.wdf ends 2 bytes inside its last block (WXDA).
    content = wdf_file([1.0, 2.0], [[1.0, 2.0]], extra=block(b"TEXT", b"note")[:-2])
    _, y = matrix(read_wdf(write(tmp_path, content)))
    np.testing.assert_array_equal(y, [[1.0, 2.0]])
