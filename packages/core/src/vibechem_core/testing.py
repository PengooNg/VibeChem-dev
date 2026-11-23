# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/testing.py
"""Test helpers shared by every VibeChem package (QA.md §3, §5).

Like ``numpy.testing``, this module ships with the package but is meant for tests:

- :func:`assert_close` compares arrays with an explicit tolerance and says which
  element failed and by how much.
- :func:`assert_reference` does the same for one reference value and records the
  result for ``reports/reference_report.md`` (written by ``scripts/check.py``).
- :func:`load_hypothesis_profile` selects the hypothesis settings profile (``ci`` on CI).

Only numpy is imported at module level; hypothesis is imported inside the function
that needs it, so the shipped package has no test-tool dependencies.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike

__all__ = [
    "HYPOTHESIS_PROFILE_ENV",
    "REFERENCE_LOG_ENV",
    "assert_close",
    "assert_reference",
    "load_hypothesis_profile",
]

REFERENCE_LOG_ENV = "VIBECHEM_REFERENCE_LOG"
"""Environment variable naming the JSON-lines file :func:`assert_reference` appends to."""

HYPOTHESIS_PROFILE_ENV = "VIBECHEM_HYPOTHESIS_PROFILE"
"""Environment variable that overrides the hypothesis profile (``dev`` or ``ci``)."""


def assert_close(
    actual: ArrayLike,
    expected: ArrayLike,
    *,
    rtol: float,
    atol: float,
    name: str = "value",
) -> None:
    """Assert ``|actual - expected| <= atol + rtol * |expected|`` element-wise.

    The criterion is the one of ``numpy.isclose``; NaN equals NaN at the same
    position. Shapes must match exactly (no broadcasting). Tolerances have no
    default on purpose: each test takes them from METHODS.md.

    Parameters
    ----------
    actual, expected : array_like
        Computed and expected values (real or integer).
    rtol, atol : float
        Relative and absolute tolerance, both >= 0.
    name : str, default "value"
        What is compared; starts the failure message.

    Raises
    ------
    AssertionError
        If shapes differ or any element is outside the tolerance. The message gives
        the number of failing elements, the worst one (index, both values, its
        difference and the allowed difference) and the tolerances.
    ValueError
        If a tolerance is negative or NaN.
    """
    if not (rtol >= 0 and atol >= 0):
        raise ValueError(f"tolerances must be >= 0, got rtol={rtol}, atol={atol}")
    a = np.asarray(actual, dtype=np.float64)
    e = np.asarray(expected, dtype=np.float64)
    if a.shape != e.shape:
        raise AssertionError(f"{name}: shape {a.shape} differs from expected {e.shape}")
    ok = np.isclose(a, e, rtol=rtol, atol=atol, equal_nan=True)
    if ok.all():
        return
    with np.errstate(invalid="ignore"):  # inf - inf
        diff = np.abs(a - e)
    allowed = atol + rtol * np.abs(e)
    # Worst element: largest excess over its allowed difference (NaN/inf mismatches first).
    excess = np.where(ok, -np.inf, np.nan_to_num(diff - allowed, nan=np.inf, posinf=np.inf))
    worst = np.unravel_index(int(np.argmax(excess)), a.shape)
    raise AssertionError(
        f"{name}: {int((~ok).sum())} of {a.size} elements outside tolerance "
        f"(rtol={rtol:g}, atol={atol:g}); worst at index {tuple(int(i) for i in worst)}: "
        f"actual {float(a[worst])!r}, expected {float(e[worst])!r}, "
        f"|diff| {diff[worst]:.3g} > allowed {allowed[worst]:.3g}"
    )


def assert_reference(
    *,
    method: str,
    dataset: str,
    actual: float,
    expected: float,
    rtol: float,
    atol: float,
    source: str,
) -> None:
    """Check one value against an independent reference and record it for the report.

    When the environment variable ``VIBECHEM_REFERENCE_LOG`` names a file (set by
    ``scripts/check.py``), one JSON line with every argument, the difference and the
    outcome is appended to it before the check, so failures are reported too.

    Parameters
    ----------
    method : str
        Method as named in METHODS.md, e.g. ``"PLS RMSECV"``.
    dataset : str
        Dataset name (``testdata/datasets/PROVENANCE.md``) or ``"hand calculation"``.
    actual, expected : float
        VibeChem value and the independent expected value.
    rtol, atol : float
        Tolerance from METHODS.md (see :func:`assert_close`).
    source : str
        Where ``expected`` comes from: a publication, a hand calculation or a second
        implementation, never the library under test (QA.md §3).

    Raises
    ------
    AssertionError
        If ``actual`` is outside the tolerance.
    """
    passed = math.isclose(actual, expected, rel_tol=0.0, abs_tol=atol + rtol * abs(expected))
    log = os.environ.get(REFERENCE_LOG_ENV)
    if log:
        row = {
            "method": method,
            "dataset": dataset,
            "expected": expected,
            "actual": actual,
            "difference": actual - expected,
            "rtol": rtol,
            "atol": atol,
            "source": source,
            "passed": passed,
        }
        with Path(log).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    assert_close(actual, expected, rtol=rtol, atol=atol, name=f"{method} on {dataset}")


def load_hypothesis_profile() -> str:
    """Register the VibeChem hypothesis profiles and load one; returns its name.

    ``dev`` (local default): 100 examples, no deadline (timing on Windows is noisy).
    ``ci`` (when ``CI`` is set, as on GitHub Actions): 200 examples, no deadline,
    derandomized so a red CI run reproduces exactly. ``VIBECHEM_HYPOTHESIS_PROFILE``
    overrides the choice. Call it from a package's ``tests/conftest.py``.
    """
    from hypothesis import settings  # noqa: PLC0415  (test-only dependency)

    base = settings.get_profile("default")  # not the loaded one: profiles must not stack
    settings.register_profile("dev", base, max_examples=100, deadline=None)
    settings.register_profile(
        "ci", base, max_examples=200, deadline=None, derandomize=True, print_blob=True
    )
    name = os.environ.get(HYPOTHESIS_PROFILE_ENV) or ("ci" if os.environ.get("CI") else "dev")
    settings.load_profile(name)
    return name
