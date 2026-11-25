# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_jcamp.py
"""Tests for ``vibechem_core.io.jcamp`` (DATA_MODEL.md §2.5, JCAMP-DX import)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import IMPORT_FILE_INVALID, TableImport
from vibechem_core.io.jcamp import read_jcamp
from vibechem_core.testing import assert_reference

DATA = Path(__file__).parent / "data"

HEADER = """##TITLE=hand written
##JCAMP-DX=4.24
##DATA TYPE=INFRARED SPECTRUM
##XUNITS={xunits}
##YUNITS=ABSORBANCE
"""

AFFN = (
    HEADER
    + """##XFACTOR=1.0
##YFACTOR=0.001
##FIRSTX=1000
##LASTX=1006
##DELTAX=2
##NPOINTS=4
##XYDATA=(X++(Y..Y))
1000 100 -200
1004 300 400
##END=
"""
)

XY_PAIRS = (
    HEADER
    + """##XFACTOR=2.0
##YFACTOR=1.0
##NPOINTS=3
##XYPOINTS=(XY..XY)
500, 1.5; 501, 2.5; 502, 3.5
##END=
"""
)


def write(tmp_path: Path, text: str, name: str = "s.jdx") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def spectrum(table: TableImport) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in table.columns if n != "title"]
    return np.array([float(n) for n in names]), np.array([table.columns[n][0] for n in names])


def reason(exc: pytest.ExceptionInfo[VibeChemError]) -> object:
    assert exc.value.code == IMPORT_FILE_INVALID
    return exc.value.params["reason"]


def test_affn_hand_written_values(tmp_path: Path) -> None:
    table = read_jcamp(write(tmp_path, AFFN.format(xunits="1/CM")))
    x, y = spectrum(table)
    np.testing.assert_array_equal(x, [1000.0, 1002.0, 1004.0, 1006.0])
    np.testing.assert_allclose(y, [0.1, -0.2, 0.3, 0.4], rtol=1e-12)
    assert table.detected_format == "jcamp"
    assert table.n_rows == 1
    assert table.columns["title"].tolist() == ["hand written"]
    assert table.suggested_roles["sample_id"] == "title"
    assert table.suggested_roles["spectral_columns"] == {
        "from": "1000.0",
        "to": "1006.0",
        "count": 4,
        "axis_unit": "cm-1",
    }
    assert table.warnings == ()
    assert not table.needs_interpolation


def test_xy_pairs_apply_xfactor(tmp_path: Path) -> None:
    x, y = spectrum(read_jcamp(write(tmp_path, XY_PAIRS.format(xunits="NANOMETERS"))))
    np.testing.assert_array_equal(x, [1000.0, 1002.0, 1004.0])
    np.testing.assert_array_equal(y, [1.5, 2.5, 3.5])


@pytest.mark.parametrize(
    ("xunits", "unit"),
    [("1/CM", "cm-1"), ("nanometers", "nm"), ("MICROMETERS", "um"), ("ARBITRARY UNITS", "nm")],
)
def test_axis_unit_from_xunits_else_guess(tmp_path: Path, xunits: str, unit: str) -> None:
    table = read_jcamp(write(tmp_path, AFFN.format(xunits=xunits)))
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == unit  # 1000–1006 increasing → "nm" guess (T1.05 rule)


def test_title_comment_stripped_and_empty_title_uses_file_name(tmp_path: Path) -> None:
    text = AFFN.format(xunits="1/CM").replace("hand written", "$$ only a comment")
    table = read_jcamp(write(tmp_path, text, name="my sample.jdx"))
    assert table.columns["title"].tolist() == ["my sample"]


def test_columns_are_read_only(tmp_path: Path) -> None:
    table = read_jcamp(write(tmp_path, AFFN.format(xunits="1/CM")))
    with pytest.raises(ValueError, match="read-only"):
        table.columns["1000.0"][0] = 1.0


def test_missing_value_marker_is_rejected_not_guessed(tmp_path: Path) -> None:
    # JCAMP-DX writes "?" for a missing value; the library cannot decode it → corrupt.
    text = AFFN.format(xunits="1/CM").replace("1004 300 400", "1004 300 ?")
    with pytest.raises(VibeChemError) as exc:
        read_jcamp(write(tmp_path, text))
    assert reason(exc) == "corrupt"


def test_ethanol_dif_file_reference_values() -> None:
    """ACD/SpecManager file (DIF/SQZ); expected values from its header and a hand decode."""
    x, y = spectrum(read_jcamp(DATA / "ethanol2.jdx"))
    source = "header of ethanol2.jdx (##NPOINTS, ##FIRSTX, ##LASTX, ##MINY, ##MAXY)"
    assert len(x) == 1764
    for name, actual, expected in [
        ("first x", x[0], 599.86169434),
        ("last x", x[-1], 4000.36425781),
        ("min y", y.min(), 13.97983932),
        ("max y", y.max(), 94.72448730),
    ]:
        assert_reference(
            method=f"JCAMP-DX reader ({name})",
            dataset="ethanol2.jdx",
            actual=actual,
            expected=expected,
            rtol=1e-7,
            atol=0.0,
            source=source,
        )
    # Hand decode of the first data line "599.9D15824699M60816...": SQZ D = 4 → 415824699,
    # DIF M = +4 → +460816; times ##YFACTOR 1e-7.
    for i, expected in [(0, 415824699e-7), (1, (415824699 + 460816) * 1e-7)]:
        assert_reference(
            method=f"JCAMP-DX reader (y[{i}])",
            dataset="ethanol2.jdx",
            actual=y[i],
            expected=expected,
            rtol=1e-12,
            atol=0.0,
            source="hand decode of the first data line (JCAMP-DX 4.24 ASDF rules)",
        )


def test_isopropanol_asdf_file_reference_values() -> None:
    """ASDF file; first value hand-decoded, range from the header."""
    x, y = spectrum(read_jcamp(DATA / "isopropanol_ASDF.jdx"))
    assert len(x) == 9541
    np.testing.assert_allclose([x[0], x[-1]], [400.1963, 5000.042], rtol=1e-7)
    # "2561A058...": SQZ A = 1 → 1058, times ##YFACTOR.
    assert_reference(
        method="JCAMP-DX reader (y[0])",
        dataset="isopropanol_ASDF.jdx",
        actual=y[0],
        expected=1058 * 2.840445172462317941e-05,
        rtol=1e-12,
        atol=0.0,
        source="hand decode of the first data line (JCAMP-DX 4.24 ASDF rules)",
    )
    # ##MINY/##MAXY are given to 2 decimals.
    assert round(y.min(), 2) == -0.09
    assert round(y.max(), 2) == 0.37


def test_npoints_mismatch_is_corrupt(tmp_path: Path) -> None:
    text = AFFN.format(xunits="1/CM").replace("1004 300 400", "1004 300")
    with pytest.raises(VibeChemError) as exc:
        read_jcamp(write(tmp_path, text))
    assert reason(exc) == "corrupt"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not a jcamp file\n",
        "##TITLE=x\n##XYDATA=(X++(Y..Y))\n1 2 3\n##END=\n",  # no FIRSTX/LASTX/NPOINTS
        AFFN.format(xunits="1/CM").replace("1004 300 400", "1004 3#0 400"),
    ],
)
def test_unreadable_files_are_corrupt(tmp_path: Path, text: str) -> None:
    with pytest.raises(VibeChemError) as exc:
        read_jcamp(write(tmp_path, text))
    assert reason(exc) == "corrupt"


def test_compound_file_is_unsupported(tmp_path: Path) -> None:
    block = AFFN.format(xunits="1/CM")
    text = "##TITLE=link\n##JCAMP-DX=4.24\n##DATA TYPE=LINK\n##BLOCKS=1\n" + block + "##END=\n"
    with pytest.raises(VibeChemError) as exc:
        read_jcamp(write(tmp_path, text))
    assert reason(exc) == "unsupported"
    assert exc.value.params["feature"] == "compound"


def test_peak_table_is_unsupported(tmp_path: Path) -> None:
    text = HEADER.format(xunits="1/CM") + "##PEAK TABLE=(XY..XY)\n1000, 5; 1100, 7\n##END=\n"
    with pytest.raises(VibeChemError) as exc:
        read_jcamp(write(tmp_path, text))
    assert reason(exc) == "unsupported"
    assert exc.value.params["feature"] == "peak_table"


def test_axis_with_repeated_x_is_rejected(tmp_path: Path) -> None:
    text = XY_PAIRS.format(xunits="1/CM").replace("501, 2.5", "500, 2.5")
    with pytest.raises(VibeChemError) as exc:
        read_jcamp(write(tmp_path, text))
    assert reason(exc) == "axis"


def test_library_output_is_not_printed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # A wrong x check value makes the library print a message; it must not reach stdout.
    text = AFFN.format(xunits="1/CM").replace("1004 300 400", "1100 300 400")
    read_jcamp(write(tmp_path, text))
    assert capsys.readouterr().out == ""
