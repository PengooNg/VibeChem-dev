# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_reference_datasets.py
"""Tests for the reference dataset loaders in ``vibechem_core.reference_datasets``.

Spot values come from the source files named in ``testdata/datasets/PROVENANCE.md``
(R ``pls`` 2.9-0 ``gasoline`` and the QIB ``FTIR_Spectra_olive_oils.csv``).
"""

import shutil
from pathlib import Path

import numpy as np
import pytest

from vibechem_core import reference_datasets as rd
from vibechem_core.testing import assert_close


def test_gasoline_shapes_axis_and_spot_values() -> None:
    ds = rd.load_reference_dataset("gasoline_nir")
    assert ds.spectra.shape == (60, 401)
    assert ds.spectra.dtype == np.float64
    assert ds.axis_unit == "nm"
    assert_close(ds.axis, np.arange(900.0, 1701.0, 2.0), rtol=0.0, atol=0.0, name="axis")
    assert ds.target_name == "octane"
    assert ds.target.dtype == np.float64
    assert ds.target.shape == (60,)
    assert ds.groups is None
    assert ds.sample_ids.tolist() == list(range(1, 61))
    # source values (R print of gasoline$octane / gasoline$NIR)
    assert_close(ds.target[[0, 1, 59]], [85.3, 85.25, 87.1], rtol=0.0, atol=0.0)
    assert_close(ds.spectra[0, :3], [-0.050193, -0.045903, -0.042187], rtol=0.0, atol=0.0)
    assert_close(ds.spectra[59, -1], 1.163959, rtol=0.0, atol=0.0)
    assert np.isfinite(ds.spectra).all()


def test_olive_oil_shapes_classes_and_groups() -> None:
    ds = rd.load_reference_dataset("olive_oil_ftir")
    assert ds.spectra.shape == (120, 570)
    assert ds.axis_unit == "cm-1"
    assert ds.axis[0] == 798.892
    assert ds.axis[-1] == 1896.8085
    assert np.all(np.diff(ds.axis) > 0)
    assert ds.target_name == "country"
    classes, counts = np.unique(ds.target, return_counts=True)
    assert classes.tolist() == ["Greece", "Italy", "Portugal", "Spain"]
    assert counts.tolist() == [20, 34, 16, 50]
    assert ds.groups is not None
    oils, per_oil = np.unique(ds.groups, return_counts=True)
    assert oils.tolist() == list(range(1, 61))
    assert set(per_oil.tolist()) == {2}
    # both spectra of one oil have the same country
    for oil in oils:
        assert len(set(ds.target[ds.groups == oil].tolist())) == 1
    assert ds.sample_ids.tolist() == list(range(1, 121))
    assert ds.spectra[0, 0] == 0.127523009  # source row "798.892", column 1
    assert ds.spectra[1, 0] == 0.126498181


def test_expected_files_match_the_datasets() -> None:
    gas = rd.load_expected("gasoline_nir_pls")
    assert gas["dataset"] == "gasoline_nir"
    values = gas["values"]
    for key in ("rmsep_cv", "rmsep_adjcv", "rmsep_test"):
        assert len(values[key]) == 11  # 0..10 components
    for key in ("x_variance_explained_cumulative_pct", "y_variance_explained_cumulative_pct"):
        assert len(values[key]) == 10
        assert np.all(np.diff(values[key]) > 0)
    assert values["test_predictions_2_components"]["samples"] == list(range(51, 61))
    assert gas["tolerance"]["rtol"] == 1e-3

    olive = rd.load_expected("olive_oil_ftir_classification")
    assert olive["dataset"] == "olive_oil_ftir"
    assert olive["values"]["cv_accuracy_min"] <= olive["values"]["cv_accuracy_published"]
    for name in (gas["dataset"], olive["dataset"]):
        assert name in rd.REFERENCE_DATASETS


def test_unknown_name_lists_available_datasets() -> None:
    with pytest.raises(KeyError, match="available: gasoline_nir, olive_oil_ftir"):
        rd.load_reference_dataset("tecator")


def test_unknown_expected_name_lists_available_files() -> None:
    with pytest.raises(
        KeyError,
        match="available: gasoline_nir_pls, gasoline_nir_splits, olive_oil_ftir_classification",
    ):
        rd.load_expected("gasoline_pls")


def test_find_testdata_dir_fails_outside_the_repository(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Pass testdata_dir"):
        rd.find_testdata_dir(tmp_path)


@pytest.fixture
def testdata_copy(tmp_path: Path) -> Path:
    """A writable copy of ``testdata/`` (datasets only)."""
    shutil.copytree(rd.find_testdata_dir() / "datasets", tmp_path / "datasets")
    return tmp_path


def _rewrite(path: Path, edit: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if edit == "header":
        lines[0] = lines[0].replace("octane", "ron", 1)
    elif edit == "short_row":
        lines[5] = lines[5].rsplit(",", 1)[0]
    elif edit == "missing_row":
        del lines[-1]
    elif edit == "trailing_blank_lines":
        lines += ["", ""]
    elif edit == "empty":
        lines = []
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


@pytest.mark.parametrize(
    ("edit", "message"),
    [
        ("header", "metadata columns"),
        ("short_row", "line 6 has a different number of fields"),
        ("missing_row", r"shape \(59, 401\) != documented \(60, 401\)"),
        ("empty", "file is empty"),
    ],
)
def test_corrupted_file_is_rejected(testdata_copy: Path, edit: str, message: str) -> None:
    _rewrite(testdata_copy / "datasets" / "gasoline_nir.csv", edit)
    with pytest.raises(ValueError, match=message):
        rd.load_reference_dataset("gasoline_nir", testdata_dir=testdata_copy)


def test_trailing_blank_lines_are_ignored(testdata_copy: Path) -> None:
    _rewrite(testdata_copy / "datasets" / "gasoline_nir.csv", "trailing_blank_lines")
    ds = rd.load_reference_dataset("gasoline_nir", testdata_dir=testdata_copy)
    assert ds.spectra.shape == (60, 401)
