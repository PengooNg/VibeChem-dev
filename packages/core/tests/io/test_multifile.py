# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_multifile.py
"""Tests for ``vibechem_core.io.multifile`` (DATA_MODEL.md §2.5, several paths)."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import (
    IMPORT_AXIS_MISMATCH,
    IMPORT_DUPLICATE_SAMPLE_IDS,
    IMPORT_FILE_INVALID,
    IMPORT_FORMAT_UNKNOWN,
    SOURCE_FILE,
    ImportWarning,
    read_file,
    read_files,
    read_jcamp,
    read_spc,
    read_table,
)

DATA = Path(__file__).parent / "data"


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def codes(warnings: tuple[ImportWarning, ...]) -> list[str]:
    return [w["code"] for w in warnings]


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("ethanol2.jdx", "jcamp"),
        ("Ft-ir.spc", "spc"),
        ("peach_juice.dpt", "tsv"),
        ("sample1.spa", "spa"),
        ("single_PE_spectrum.sp", "perkinelmer"),
        ("sp.wdf", "wdf"),
    ],
)
def test_read_file_dispatches_by_extension(name: str, fmt: str) -> None:
    assert read_file(DATA / name).detected_format == fmt


def test_read_file_hint_overrides_extension(tmp_path: Path) -> None:
    path = tmp_path / "spectrum.txt"
    shutil.copy(DATA / "ethanol2.jdx", path)
    assert read_file(path, "jcamp").detected_format == "jcamp"
    with pytest.raises(VibeChemError) as exc:
        read_file(tmp_path / "x.abc")
    assert exc.value.code == IMPORT_FORMAT_UNKNOWN


def test_one_path_is_the_reader_result() -> None:
    table = read_files([DATA / "nir.spc"])
    assert SOURCE_FILE not in table.columns
    assert table.n_rows == 20


def test_same_axis_files_are_stacked_with_file_names() -> None:
    table = read_files([DATA / "Ft-ir.spc", DATA / "Ft-ir.spc"])
    single = read_spc(DATA / "Ft-ir.spc")
    assert table.columns[SOURCE_FILE].tolist() == ["Ft-ir.spc", "Ft-ir.spc"]
    assert list(table.columns)[1:] == list(single.columns)
    np.testing.assert_array_equal(table.columns["4000.0"], [single.columns["4000.0"][0]] * 2)
    assert not table.needs_interpolation
    assert table.warnings == ()
    assert table.suggested_roles["spectral_columns"] == single.suggested_roles["spectral_columns"]


def test_different_axes_give_union_and_warning() -> None:
    table = read_files([DATA / "ethanol2.jdx", DATA / "Ft-ir.spc"])
    jdx, spc = read_jcamp(DATA / "ethanol2.jdx"), read_spc(DATA / "Ft-ir.spc")
    n_jdx = len(jdx.columns) - 1
    n_spc = len(spc.columns) - 1
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    assert spectral["count"] == n_jdx + n_spc  # no x value in common
    assert (spectral["from"], spectral["to"]) == ("450.0", "4000.36425781")  # increasing, as file 1
    assert table.needs_interpolation
    assert table.warnings == ({"code": IMPORT_AXIS_MISMATCH, "params": {"axes": 2}},)
    np.testing.assert_array_equal(table.columns["4000.0"], [np.nan, spc.columns["4000.0"][0]])
    np.testing.assert_array_equal(
        table.columns["599.86169434"], [jdx.columns["599.86169434"][0], np.nan]
    )
    assert table.columns[SOURCE_FILE].tolist() == ["ethanol2.jdx", "Ft-ir.spc"]
    assert table.columns["title"].tolist() == ["ethanol2", "FT-IR Spectrum Example"]
    assert table.suggested_roles["sample_id"] == SOURCE_FILE


def test_csv_files_match_axis_by_value_and_merge_columns(tmp_path: Path) -> None:
    a = write(
        tmp_path, "a.csv", "Sample,Batch,Origin,1100,1102\nS1,1,EU,0.1,0.2\nS2,2,EU,0.3,0.4\n"
    )
    b = write(tmp_path, "b.csv", "Sample,Batch,Fat,1100.0,1102.0\nS2,X,5,0.5,0.6\n")
    table = read_files([a, b])
    assert list(table.columns) == [SOURCE_FILE, "Sample", "Batch", "Origin", "Fat", "1100", "1102"]
    np.testing.assert_array_equal(table.columns["1102"], [0.2, 0.4, 0.6])
    assert table.columns["Batch"].tolist() == ["1.0", "2.0", "X"]  # text in b → text
    assert table.columns["Origin"].tolist() == ["EU", "EU", ""]
    np.testing.assert_array_equal(table.columns["Fat"], [np.nan, np.nan, 5.0])
    assert not table.needs_interpolation
    assert table.suggested_roles["sample_id"] == "Sample"
    # "S2" occurs in both files: counted again over the merged table.
    assert table.warnings == ({"code": IMPORT_DUPLICATE_SAMPLE_IDS, "params": {"count": 1}},)


def test_file_without_spectra_is_not_an_axis_mismatch(tmp_path: Path) -> None:
    a = write(tmp_path, "a.csv", "Sample,1100,1102\nS1,0.1,0.2\n")
    b = write(tmp_path, "b.csv", "Sample,Fat\nS2,5\n")
    table = read_files([a, b])
    np.testing.assert_array_equal(table.columns["1100"], [0.1, np.nan])
    assert IMPORT_AXIS_MISMATCH not in codes(table.warnings)
    assert not table.needs_interpolation


def test_reversed_axis_is_the_same_axis(tmp_path: Path) -> None:
    a = write(tmp_path, "a.csv", "Sample,1100,1102\nS1,0.1,0.2\n")
    b = write(tmp_path, "b.csv", "Sample,1102,1100\nS2,0.6,0.5\n")
    table = read_files([a, b])
    np.testing.assert_array_equal(table.columns["1100"], [0.1, 0.5])
    assert table.warnings == ()
    assert not table.needs_interpolation


def test_per_file_axis_mismatch_is_kept() -> None:
    table = read_files([DATA / "m_xyxy.spc", DATA / "m_xyxy.spc"])
    assert table.n_rows == 1024
    assert codes(table.warnings) == [IMPORT_AXIS_MISMATCH, IMPORT_AXIS_MISMATCH]
    assert table.needs_interpolation


def test_name_clash_is_duplicate_column(tmp_path: Path) -> None:
    a = write(tmp_path, "a.csv", "source_file,1100,1102\nx,0.1,0.2\n")
    with pytest.raises(VibeChemError) as exc:
        read_files([a, a])
    assert exc.value.code == IMPORT_FILE_INVALID
    assert exc.value.params == {"reason": "duplicate_column", "column": SOURCE_FILE}


def test_columns_are_read_only() -> None:
    table = read_files([DATA / "Ft-ir.spc", DATA / "Ft-ir.spc"])
    for array in table.columns.values():
        assert not array.flags.writeable


def test_empty_paths_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        read_files([])


def test_read_table_unchanged_for_tables() -> None:
    assert read_file(DATA / "peach_juice.dpt").columns.keys() == (
        read_table(DATA / "peach_juice.dpt").columns.keys()
    )
