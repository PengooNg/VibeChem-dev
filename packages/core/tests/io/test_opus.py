# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_opus.py
"""Tests for ``vibechem_core.io.opus`` (DATA_MODEL.md §2.5, Bruker OPUS import).

Independent expected values for ``peach_juice.0``: ``peach_juice.dpt``, the same
measurement exported as text (axis and intensities rounded to 5 decimals), and
the value that opusFC (a different OPUS reader, used by orange-spectroscopy)
gives at index 3 in Quasar's ``tests/test_readers.py``. The wrapped library is
brukeropus, so neither source shares its code.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import IMPORT_FILE_INVALID, TableImport, read_table
from vibechem_core.io.opus import is_opus_extension, read_opus
from vibechem_core.testing import assert_reference

DATA = Path(__file__).parent / "data"
SAMPLE = DATA / "peach_juice.0"


def matrix(table: TableImport) -> tuple[np.ndarray, np.ndarray]:
    names = [n for n in table.columns if n != "title"]
    return np.array([float(n) for n in names]), np.stack([table.columns[n] for n in names], 1)


def reason(exc: pytest.ExceptionInfo[VibeChemError]) -> object:
    assert exc.value.code == IMPORT_FILE_INVALID
    return exc.value.params["reason"]


# --- sample file ---


def test_default_block_matches_the_dpt_export() -> None:
    table = read_opus(SAMPLE)
    x, y = matrix(table)
    dpt_x, dpt_y = matrix(read_table(DATA / "peach_juice.dpt"))
    assert table.detected_format == "opus"
    assert y.shape == (1, 1816)
    assert_reference(
        method="OPUS reader (axis vs DPT export, max abs difference)",
        dataset="peach_juice.0",
        actual=float(np.max(np.abs(x - dpt_x))),
        expected=0.0,
        rtol=0.0,
        atol=5.001e-6,  # the DPT file is rounded to 5 decimals (+ float rounding)
        source="peach_juice.dpt (same measurement exported as text)",
    )
    assert_reference(
        method="OPUS reader (intensities vs DPT export, max abs difference)",
        dataset="peach_juice.0",
        actual=float(np.max(np.abs(y[0] - dpt_y[0]))),
        expected=0.0,
        rtol=0.0,
        atol=5.001e-6,
        source="peach_juice.dpt (same measurement exported as text)",
    )
    assert_reference(
        method="OPUS reader (y[3])",
        dataset="peach_juice.0",
        actual=y[0, 3],
        expected=0.90655535,
        rtol=0.0,
        atol=5e-9,  # value printed with 8 decimals
        source="opusFC via orange-spectroscopy tests/test_readers.py (independent OPUS reader)",
    )
    assert table.columns["title"].tolist() == ["Peach juice colorful spot"]
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["axis_unit"] == "cm-1"
    assert table.warnings == ()


def test_sample_and_reference_blocks() -> None:
    _, sample = matrix(read_opus(SAMPLE, "sample"))
    _, reference = matrix(read_opus(SAMPLE, "reference"))
    _, default = matrix(read_opus(SAMPLE))
    assert sample.shape == reference.shape == (1, 1816)
    assert not np.allclose(sample, reference)
    # The default block is the reflectance R = sample / reference (OPUS ratio); they
    # agree except near the CO2 band (largest difference 0.017 at 2357 cm-1).
    assert np.median(np.abs(sample / reference - default)) < 1e-4


def test_missing_block_is_unsupported() -> None:
    with pytest.raises(VibeChemError) as exc:
        read_opus(SAMPLE, "absorbance")  # the file holds reflectance, not absorbance
    assert reason(exc) == "unsupported"
    assert exc.value.params == {
        "reason": "unsupported",
        "feature": "opus_block",
        "block": "absorbance",
    }


def test_unknown_block_name_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="unknown OPUS block"):
        read_opus(SAMPLE, "transmittance")  # pyright: ignore[reportArgumentType]


# --- files the library rejects ---


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"not an OPUS file",
        b"\n\n\xfe\xfe" + b"\x00" * 20,  # OPUS magic, then nothing usable
        SAMPLE.read_bytes()[:5000],  # truncated
    ],
)
def test_corrupt_files(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "s.0"
    path.write_bytes(content)
    with pytest.raises(VibeChemError) as exc:
        read_opus(path)
    assert reason(exc) == "corrupt"


def test_missing_file_is_os_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_opus(tmp_path / "missing.0")


def test_series_only_file_is_unsupported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Series:
        data_keys: list[str] = []  # noqa: RUF012
        series_keys = ["sm"]  # noqa: RUF012

        def __bool__(self) -> bool:
            return True

    def fake_read(_path: str) -> Series:
        return Series()

    monkeypatch.setattr("brukeropus.file.read_opus", fake_read)
    path = tmp_path / "s.0"
    path.write_bytes(b"")
    with pytest.raises(VibeChemError) as exc:
        read_opus(path)
    assert exc.value.params == {"reason": "unsupported", "feature": "opus_series"}


def test_auto_skips_interferograms_and_phases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spectrum = SimpleNamespace(x=[1.0, 2.0], y=[3.0, 4.0], params=SimpleNamespace(dxu="WN"))

    class File:
        data_keys = ["igsm", "phsm", "sm"]  # noqa: RUF012
        series_keys: list[str] = []  # noqa: RUF012
        params = SimpleNamespace(snm="")
        sm = spectrum

        def __bool__(self) -> bool:
            return True

    def fake_read(_path: str) -> File:
        return File()

    monkeypatch.setattr("brukeropus.file.read_opus", fake_read)
    path = tmp_path / "s.0"
    path.write_bytes(b"")
    _, y = matrix(read_opus(path))
    np.testing.assert_array_equal(y, [[3.0, 4.0]])


@pytest.mark.parametrize(
    ("ext", "expected"),
    [
        (".0", True),
        (".12", True),
        (".9", True),
        (".", False),
        (".0a", False),
        (".spa", False),
        (".²", False),  # superscript two: a Unicode digit, not ASCII
    ],
)
def test_opus_extensions(ext: str, expected: bool) -> None:
    assert is_opus_extension(ext) is expected
