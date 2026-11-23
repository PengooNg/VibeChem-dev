# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_testing.py
"""Tests for the shared test helpers in ``vibechem_core.testing``."""

import json
import re
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vibechem_core import testing


def test_assert_close_passes_within_tolerance() -> None:
    testing.assert_close([1.0, 2.0], [1.0 + 1e-13, 2.0], rtol=0.0, atol=1e-12)
    testing.assert_close([[1.0, np.nan]], [[1.0, np.nan]], rtol=1e-9, atol=0.0)
    testing.assert_close(100.0, 101.0, rtol=0.01, atol=0.0)  # 1 <= 0.01 * 101


def test_assert_close_names_the_worst_element() -> None:
    actual = np.array([[1.0, 2.0], [3.0, 4.5]])
    expected = np.array([[1.0, 2.1], [3.0, 4.0]])
    message = (
        "SNV row 2: 2 of 4 elements outside tolerance (rtol=0, atol=0.01); "
        "worst at index (1, 1): actual 4.5, expected 4.0, |diff| 0.5 > allowed 0.01"
    )
    with pytest.raises(AssertionError, match=re.escape(message)):
        testing.assert_close(actual, expected, rtol=0.0, atol=0.01, name="SNV row 2")


def test_assert_close_reports_nan_and_inf_mismatches_first() -> None:
    with pytest.raises(AssertionError, match=r"1 of 3 .* index \(2,\): actual nan"):
        testing.assert_close([1.0, 5.0, np.nan], [1.0, 5.0, 3.0], rtol=0.0, atol=1e-9)
    with pytest.raises(AssertionError, match=r"2 of 3 .* index \(1,\): actual inf"):
        testing.assert_close([1.0, np.inf, 9.0], [1.0, 2.0, 3.0], rtol=0.0, atol=1e-9)


def test_assert_close_rejects_shape_mismatch_without_broadcasting() -> None:
    with pytest.raises(AssertionError, match=r"shape \(3,\) differs from expected \(1,\)"):
        testing.assert_close([1.0, 1.0, 1.0], [1.0], rtol=0.0, atol=1.0)


@pytest.mark.parametrize(("rtol", "atol"), [(-1e-9, 0.0), (0.0, -1.0), (float("nan"), 0.0)])
def test_assert_close_rejects_bad_tolerance(rtol: float, atol: float) -> None:
    with pytest.raises(ValueError, match="tolerances must be >= 0"):
        testing.assert_close(1.0, 1.0, rtol=rtol, atol=atol)


@settings(max_examples=50)
@given(
    st.lists(st.floats(-1e6, 1e6), min_size=1, max_size=20),
    st.floats(1e-12, 1e-3),
)
def test_assert_close_agrees_with_numpy_isclose(values: list[float], rtol: float) -> None:
    expected = np.array(values)
    shifted = expected * (1 + 2 * rtol) + 1.0
    testing.assert_close(expected, expected, rtol=rtol, atol=0.0)
    if np.isclose(shifted, expected, rtol=rtol, atol=0.0).all():
        testing.assert_close(shifted, expected, rtol=rtol, atol=0.0)
    else:
        with pytest.raises(AssertionError):
            testing.assert_close(shifted, expected, rtol=rtol, atol=0.0)


def _reference(actual: float) -> None:
    testing.assert_reference(
        method="row mean",
        dataset="hand calculation",
        actual=actual,
        expected=2.0,
        rtol=0.0,
        atol=1e-12,
        source="(1 + 2 + 3) / 3",
    )


def test_assert_reference_records_pass_and_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "reference.jsonl"
    monkeypatch.setenv(testing.REFERENCE_LOG_ENV, str(log))
    _reference(2.0)
    with pytest.raises(AssertionError, match="row mean on hand calculation: 1 of 1 elements"):
        _reference(2.5)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["passed"] for r in rows] == [True, False]
    assert rows[1] == {
        "method": "row mean",
        "dataset": "hand calculation",
        "expected": 2.0,
        "actual": 2.5,
        "difference": 0.5,
        "rtol": 0.0,
        "atol": 1e-12,
        "source": "(1 + 2 + 3) / 3",
        "passed": False,
    }


def test_assert_reference_writes_nothing_without_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(testing.REFERENCE_LOG_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    _reference(2.0)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("ci", "override", "expected"),
    [("", "", "dev"), ("true", "", "ci"), ("true", "dev", "dev"), ("", "ci", "ci")],
)
def test_load_hypothesis_profile(
    monkeypatch: pytest.MonkeyPatch, ci: str, override: str, expected: str
) -> None:
    monkeypatch.setenv("CI", ci)
    monkeypatch.setenv(testing.HYPOTHESIS_PROFILE_ENV, override)
    assert testing.load_hypothesis_profile() == expected
    assert settings().deadline is None
    assert settings().derandomize is (expected == "ci")
    monkeypatch.undo()
    testing.load_hypothesis_profile()  # restore the session's profile
