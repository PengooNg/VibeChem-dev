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
from pytest_regressions.data_regression import DataRegressionFixture

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
    with pytest.raises(AssertionError, match=r"1 of 2 .* index \(1,\): actual 1.0"):
        testing.assert_close([np.inf, 1.0], [np.inf, 2.0], rtol=1e-9, atol=0.0)  # inf - inf
    with pytest.raises(
        AssertionError, match=r"elements outside tolerance \(rtol=0, atol=0\); value:"
    ):
        testing.assert_close(1.0, 2.0, rtol=0.0, atol=0.0)


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


def test_node_hash_ignores_last_bits_signed_zero_and_nan_payload() -> None:
    x = np.array([[1.0, -0.0, np.nan], [1e300, 3.5e-12, -7.25]])
    wobble = x * (1 + 2.0**-50)
    payload_nan = np.frombuffer(np.uint64(0x7FF8000000000001).tobytes(), dtype=np.float64)
    wobble[0, 1], wobble[0, 2] = 0.0, payload_nan[0]
    assert testing.node_hash(x) == testing.node_hash(wobble)
    assert len(testing.node_hash(x)) == 16
    assert testing.node_hash([1, 2, 3]) == testing.node_hash([1.0, 2.0, 3.0])


def test_node_hash_sees_real_changes_and_shape() -> None:
    x = np.linspace(0.0, 1.0, 12)
    changed = x.copy()
    changed[5] *= 1 + 1e-9
    assert testing.node_hash(x) != testing.node_hash(changed)
    assert testing.node_hash(x) != testing.node_hash(x.reshape(3, 4))
    coarse = {"significant_bits": 10}
    assert testing.node_hash(x, **coarse) == testing.node_hash(changed, **coarse)


@pytest.mark.parametrize("bits", [0, 53])
def test_node_hash_rejects_bad_bits(bits: int) -> None:
    with pytest.raises(ValueError, match="significant_bits"):
        testing.node_hash([1.0], significant_bits=bits)


def test_check_golden_names_first_changed_node(
    data_regression: DataRegressionFixture, tmp_path: Path
) -> None:
    golden = tmp_path / "expected" / "golden_nodes.yml"
    hashes = {"dataset": "aaaa", "snv": "bbbb", "pls": "cccc"}
    with pytest.raises(pytest.fail.Exception, match="File not found"):
        testing.check_golden(data_regression, hashes, golden)  # first run creates the file
    text = golden.read_text(encoding="utf-8")
    assert text.index("dataset") < text.index("snv") < text.index("pls")  # pipeline order kept
    testing.check_golden(data_regression, hashes, golden)

    changed = {"dataset": "aaaa", "snv": "dddd", "pls": "eeee"}
    first = r"first node whose output changed: snv \(expected bbbb, got dddd\)"
    with pytest.raises(AssertionError, match=first):
        testing.check_golden(data_regression, changed, golden)
    with pytest.raises(AssertionError, match=r"changed: pls \(missing from this run\)"):
        testing.check_golden(data_regression, {"dataset": "aaaa", "snv": "bbbb"}, golden)
    with pytest.raises(AssertionError, match=r"changed: msc \(expected no entry, got ffff\)"):
        testing.check_golden(data_regression, {**hashes, "msc": "ffff"}, golden)
