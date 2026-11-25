# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/io/test_table.py
"""Tests for ``vibechem_core.io.table`` (DATA_MODEL.md §2.5 import step 1)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vibechem_core.errors import VibeChemError
from vibechem_core.io import (
    IMPORT_DUPLICATE_SAMPLE_IDS,
    IMPORT_FILE_INVALID,
    IMPORT_FORMAT_UNKNOWN,
    IMPORT_NON_NUMERIC_VALUES,
    SpectralColumns,
    TableImport,
    read_table,
)
from vibechem_core.reference_datasets import load_reference_dataset

DATA = Path(__file__).parent / "data"
TESTDATA = Path(__file__).parents[4] / "testdata" / "datasets"


def write(tmp_path: Path, name: str, text: str, newline: str = "\n") -> Path:
    path = tmp_path / name
    path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    return path


def codes(table: TableImport) -> list[str]:
    return [w["code"] for w in table.warnings]


def spectral_of(table: TableImport) -> SpectralColumns:
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral is not None
    return spectral


# --- reference data -----------------------------------------------------------------


def test_gasoline_csv_roles_and_values_match_reference_loader() -> None:
    table = read_table(TESTDATA / "gasoline_nir.csv")
    expected = load_reference_dataset("gasoline_nir")
    assert table.detected_format == "csv"
    assert (table.n_rows, table.n_columns) == (60, 403)
    roles = table.suggested_roles
    assert roles["sample_id"] == "sample"
    assert roles["y"] == ["octane"]
    assert roles["group_id"] is None
    assert roles["class_label"] is None
    assert roles["metadata"] == []
    assert roles["spectral_columns"] == {
        "from": "900",
        "to": "1700",
        "count": 401,
        "axis_unit": "nm",
    }
    assert table.warnings == ()
    X = np.column_stack([table.columns[str(w)] for w in range(900, 1701, 2)])
    np.testing.assert_array_equal(X, expected.spectra)
    np.testing.assert_array_equal(table.columns["octane"], expected.target)
    assert table.columns["sample"].tolist() == [str(i) for i in range(1, 61)]


def test_olive_oil_csv_text_metadata_and_wavenumber_axis() -> None:
    table = read_table(TESTDATA / "olive_oil_ftir.csv")
    roles = table.suggested_roles
    assert table.n_rows == 120
    assert roles["sample_id"] == "sample"
    assert roles["metadata"] == ["country"]
    assert roles["y"] == ["oil"]  # a numeric column; the user re-assigns it as groups
    spectral = spectral_of(table)
    assert (spectral["from"], spectral["to"], spectral["count"]) == ("798.892", "1896.8085", 570)
    assert spectral["axis_unit"] == "nm"  # increasing and below 2600: ambiguous, user confirms
    assert table.columns["country"].dtype.kind == "U"
    assert set(table.columns["country"].tolist()) == {"Greece", "Italy", "Portugal", "Spain"}


def test_bruker_dpt_headerless_two_columns_with_comment_lines() -> None:
    # osp datasets/peach_juice.dpt: tab separated, '#' and ';' comment lines at the end.
    table = read_table(DATA / "peach_juice.dpt")
    assert table.detected_format == "tsv"
    assert table.n_rows == 1
    assert table.n_columns == 1816
    spectral = table.suggested_roles["spectral_columns"]
    assert spectral == {"from": "4000.11610", "to": "499.53234", "count": 1816, "axis_unit": "cm-1"}
    assert table.suggested_roles["sample_id"] is None
    # First and last lines of the file, read by eye.
    assert table.columns["4000.11610"].tolist() == [0.90603]
    assert table.columns["499.53234"].tolist() == [0.75763]


# --- parsing rules ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "text", "fmt"),
    [
        ("a.csv", "id,y,1000,1002\ns1,1.5,0.1,0.2\n", "csv"),
        ("a.csv", "id;y;1000;1002\ns1;1.5;0.1;0.2\n", "csv"),
        ("a.tsv", "id\ty\t1000\t1002\ns1\t1.5\t0.1\t0.2\n", "tsv"),
        ("a.txt", "id\ty\t1000\t1002\ns1\t1.5\t0.1\t0.2\n", "tsv"),
        ("a.txt", "id  y   1000 1002\ns1  1.5 0.1  0.2\n", "csv"),
    ],
)
def test_delimiters(tmp_path: Path, name: str, text: str, fmt: str) -> None:
    table = read_table(write(tmp_path, name, text))
    assert table.detected_format == fmt
    assert list(table.columns) == ["id", "y", "1000", "1002"]
    assert table.columns["1002"].tolist() == [0.2]


def test_crlf_bom_comments_quotes_and_blank_lines(tmp_path: Path) -> None:
    text = '﻿; exported by X\n# another comment\nid,note,1,2\n\n"s,1","a ""b""",3,4\n'
    table = read_table(write(tmp_path, "a.csv", text, newline="\r\n"))
    assert list(table.columns) == ["id", "note", "1", "2"]
    assert table.columns["id"].tolist() == ["s,1"]
    assert table.columns["note"].tolist() == ['a "b"']


def test_explicit_delimiter_and_format_hint(tmp_path: Path) -> None:
    path = write(tmp_path, "data.dat", "id|1|2\ns1|3|4\n")
    table = read_table(path, "csv", delimiter="|")
    assert table.columns["2"].tolist() == [4.0]
    with pytest.raises(VibeChemError) as err:
        read_table(path)
    assert err.value.code == IMPORT_FORMAT_UNKNOWN
    assert err.value.params == {"format": ".dat"}


@pytest.mark.parametrize("hint", ["jcamp", "spc", "parquet"])
def test_unsupported_format_hint(tmp_path: Path, hint: str) -> None:
    with pytest.raises(VibeChemError) as err:
        read_table(write(tmp_path, "a.csv", "a,b\n1,2\n"), hint)
    assert err.value.code == IMPORT_FORMAT_UNKNOWN


def test_headerless_multi_column_file_gives_one_row_per_spectrum(tmp_path: Path) -> None:
    table = read_table(write(tmp_path, "a.csv", "1000,1,10\n1002,2,20\n1004,3,30\n"))
    assert list(table.columns) == ["1000", "1002", "1004"]
    assert table.n_rows == 2
    assert table.columns["1004"].tolist() == [3.0, 30.0]


def test_empty_header_cells_named_and_trailing_empty_column_dropped(tmp_path: Path) -> None:
    table = read_table(write(tmp_path, "a.csv", ",y,1,2,\nA,1,2,3,\nB,4,5,6,\n"))
    assert list(table.columns) == ["column_1", "y", "1", "2"]
    assert table.suggested_roles["sample_id"] == "column_1"


def test_columns_are_read_only(tmp_path: Path) -> None:
    table = read_table(write(tmp_path, "a.csv", "id,1,2\ns1,3,4\n"))
    with pytest.raises(ValueError, match="read-only"):
        table.columns["1"][0] = 0.0
    with pytest.raises(TypeError):
        table.columns["x"] = np.zeros(1)  # type: ignore[index]


# --- roles and warnings -------------------------------------------------------------


def test_roles_by_name_and_type(tmp_path: Path) -> None:
    text = (
        "Sample ID,Batch,Class,Origin,Fat %,Water,1100,1102,1104\n"
        "007,b1,A,JP,1.5,10,0.1,0.2,0.3\n"
        "008,b1,B,VN,2.5,11,0.4,0.5,0.6\n"
    )
    table = read_table(write(tmp_path, "a.csv", text))
    roles = table.suggested_roles
    assert roles["sample_id"] == "Sample ID"
    assert roles["group_id"] == "Batch"
    assert roles["class_label"] == "Class"
    assert roles["metadata"] == ["Origin"]
    assert roles["y"] == ["Fat %", "Water"]
    assert spectral_of(table)["count"] == 3
    assert table.columns["Sample ID"].tolist() == ["007", "008"]  # text, zeros kept
    assert table.columns["Fat %"].dtype == np.float64


def test_sample_id_falls_back_to_first_unique_text_column(tmp_path: Path) -> None:
    text = "origin,code,1,2\nJP,a,1,2\nJP,b,3,4\n"
    roles = read_table(write(tmp_path, "a.csv", text)).suggested_roles
    assert roles["sample_id"] == "code"
    assert roles["metadata"] == ["origin"]


def test_no_spectral_run_without_two_monotonic_numeric_headers(tmp_path: Path) -> None:
    text = "id,5,y,3,4,2\na,1,2,3,4,5\n"
    table = read_table(write(tmp_path, "a.csv", text))
    roles = table.suggested_roles
    # "3","4" is the only run; "4","2" breaks it (direction change).
    assert spectral_of(table)["from"] == "3"
    assert spectral_of(table)["count"] == 2
    assert roles["y"] == ["5", "y", "2"]


def test_longest_numeric_run_is_spectral(tmp_path: Path) -> None:
    text = "id,1,2,x,10,20,30\na,1,2,3,4,5,6\n"
    table = read_table(write(tmp_path, "a.csv", text))
    roles = table.suggested_roles
    assert spectral_of(table)["from"] == "10"
    assert roles["y"] == ["1", "2", "x"]  # header "x" over numbers: numeric column
    assert roles["metadata"] == []


def test_duplicate_sample_ids_warning(tmp_path: Path) -> None:
    text = "sample,1,2\na,1,2\na,1,2\nb,1,2\nb,1,2\nb,1,2\nc,1,2\n"
    table = read_table(write(tmp_path, "a.csv", text))
    assert table.warnings == ({"code": IMPORT_DUPLICATE_SAMPLE_IDS, "params": {"count": 2}},)


def test_non_numeric_and_empty_spectral_cells_warning(tmp_path: Path) -> None:
    text = "id,1,2,3\na,0.1,x,0.3\nb,,0.2,inf\n"
    table = read_table(write(tmp_path, "a.csv", text))
    assert codes(table) == [IMPORT_NON_NUMERIC_VALUES]
    assert table.warnings[0]["params"] == {"count": 3, "column": "1"}
    np.testing.assert_array_equal(table.columns["2"], [np.nan, 0.2])
    np.testing.assert_array_equal(table.columns["3"], [0.3, np.nan])


def test_mixed_column_is_text(tmp_path: Path) -> None:
    table = read_table(write(tmp_path, "a.csv", "id,y,1,2\na,1.5,1,2\nb,n/a,1,2\nc,,1,2\n"))
    assert table.columns["y"].tolist() == ["1.5", "n/a", ""]
    assert table.suggested_roles["metadata"] == ["y"]


def test_numeric_column_with_empty_cells_is_float_with_nan(tmp_path: Path) -> None:
    table = read_table(write(tmp_path, "a.csv", "id,y,1,2\na,1.5,1,2\nb,,1,2\n"))
    np.testing.assert_array_equal(table.columns["y"], [1.5, np.nan])


# --- malformed files ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "empty"),
        ("; only a comment\n\n", "empty"),
        ("id,1,2\n", "empty"),
        ("1000\n1002\n", "no_spectra"),
        ("id,1,2\na,1\n", "row_length"),
        ("id,1,1\na,2,3\n", "duplicate_column"),
    ],
)
def test_malformed_text_files(tmp_path: Path, text: str, reason: str) -> None:
    with pytest.raises(VibeChemError) as err:
        read_table(write(tmp_path, "a.csv", text))
    assert err.value.code == IMPORT_FILE_INVALID
    assert err.value.params["reason"] == reason


def test_row_length_error_names_the_row(tmp_path: Path) -> None:
    with pytest.raises(VibeChemError) as err:
        read_table(write(tmp_path, "a.csv", "id,1,2\na,1,2\nb,1,2,3\n"))
    assert dict(err.value.params) == {"reason": "row_length", "row": 3, "expected": 3, "found": 4}


def test_non_utf8_file(tmp_path: Path) -> None:
    path = tmp_path / "a.csv"
    path.write_bytes("id,1,2\nmüller,1,2\n".encode("latin-1"))
    with pytest.raises(VibeChemError) as err:
        read_table(path)
    assert dict(err.value.params) == {"reason": "encoding"}


def test_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_table(tmp_path / "missing.csv")
