# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/testing.py
"""Test helpers shared by every VibeChem package (QA.md §3, §5).

Like ``numpy.testing``, this module ships with the package but is meant for tests:

- :func:`assert_close` compares arrays with an explicit tolerance and says which
  element failed and by how much.
- :func:`assert_reference` does the same for one reference value and records the
  result for ``reports/reference_report.md`` (written by ``scripts/check.py``).
- :func:`node_hash` and :func:`check_golden` keep one hash per pipeline node in a
  golden file and name the first node whose output changed (QA.md §5); storage and
  ``--force-regen`` come from pytest-regressions' ``data_regression`` fixture.
- :func:`load_hypothesis_profile` selects the hypothesis settings profile (``ci`` on CI).
- :class:`DummyOffset` (stateless) and :class:`DummyCenter` (fitted) are the smallest
  blocks that follow the block contract (``vibechem_core.block``), for contract,
  registry and engine tests; :class:`DummySchema` declares one parameter of every
  implemented schema type (DATA_MODEL.md §5) for schema tests.

Only numpy is imported at module level; hypothesis and PyYAML are imported inside the
functions that need them, so the shipped package has no test-tool dependencies.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import ArrayLike

from vibechem_core.block import Block, NoParams, Param, State, port
from vibechem_core.data import SpectralDataset

if TYPE_CHECKING:
    from pytest_regressions.data_regression import DataRegressionFixture

__all__ = [
    "HYPOTHESIS_PROFILE_ENV",
    "REFERENCE_LOG_ENV",
    "DummyCenter",
    "DummyOffset",
    "DummyOffsetParams",
    "DummySchema",
    "DummySchemaParams",
    "assert_close",
    "assert_reference",
    "check_golden",
    "load_hypothesis_profile",
    "node_hash",
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
    where = f"worst at index {tuple(int(i) for i in worst)}" if a.ndim else "value"
    raise AssertionError(
        f"{name}: {int((~ok).sum())} of {a.size} elements outside tolerance "
        f"(rtol={rtol:g}, atol={atol:g}); {where}: "
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
    actual, expected = float(actual), float(expected)  # numpy scalars are not JSON-serialisable
    # Same criterion as assert_close (NaN equals NaN).
    passed = bool(np.isclose(actual, expected, rtol=rtol, atol=atol, equal_nan=True))
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
    on_ci = os.environ.get("CI", "").lower() in {"1", "true", "yes"}
    name = os.environ.get(HYPOTHESIS_PROFILE_ENV) or ("ci" if on_ci else "dev")
    settings.load_profile(name)
    return name


def node_hash(values: ArrayLike, *, significant_bits: int = 40) -> str:
    """Short, platform-independent hash of one node output for golden files.

    Values are converted to float64 and each mantissa is rounded to
    ``significant_bits`` bits (40 bits ~ 12 significant digits) with exact
    power-of-two arithmetic (``frexp``/``ldexp``), so last-bit differences between
    BLAS builds or operating systems usually give the same hash. ``-0.0`` and every
    NaN are canonicalised. A value lying on a rounding boundary can still flip the
    hash; the golden test then names that node and the metric checks decide.

    Parameters
    ----------
    values : array_like
        Node output (real or integer); its shape is part of the hash.
    significant_bits : int, default 40
        Mantissa bits kept, 1 to 52.

    Returns
    -------
    str
        First 16 hex digits of a SHA-256 over shape and rounded values.

    Raises
    ------
    ValueError
        If ``significant_bits`` is outside 1..52.
    """
    if not 1 <= significant_bits <= 52:
        raise ValueError(f"significant_bits must be in 1..52, got {significant_bits}")
    a = np.asarray(values, dtype=np.float64)
    mantissa, exponent = np.frexp(a)  # a == mantissa * 2**exponent exactly
    scaled = np.rint(np.ldexp(mantissa, significant_bits))
    rounded = np.ldexp(scaled, exponent - significant_bits)
    canonical = np.where(np.isnan(rounded), np.nan, rounded + 0.0)  # + 0.0 turns -0.0 into 0.0
    digest = hashlib.sha256(repr(a.shape).encode())
    digest.update(np.ascontiguousarray(canonical, dtype="<f8").tobytes())
    return digest.hexdigest()[:16]


def check_golden(
    data_regression: DataRegressionFixture, node_hashes: Mapping[str, str], path: Path
) -> None:
    """Compare node hashes (in pipeline order) with the golden file at ``path``.

    The YAML file (under ``testdata/expected/``) stores ``nodes: [{node, hash}, ...]``
    in the given order. A missing file is created and the test fails once, as usual
    for pytest-regressions; ``pytest --force-regen`` rewrites it (regenerating golden
    files is a red flag in a PR, QA.md §4).

    Parameters
    ----------
    data_regression : DataRegressionFixture
        The pytest-regressions fixture of the calling test.
    node_hashes : Mapping[str, str]
        ``node_id -> node_hash(...)`` in pipeline (topological) order.
    path : Path
        Golden file.

    Raises
    ------
    AssertionError
        If any hash differs; the message starts with the first changed node.
    """
    nodes = [{"node": node, "hash": h} for node, h in node_hashes.items()]
    try:
        data_regression.check({"nodes": nodes}, fullpath=path)
    except AssertionError as exc:
        first = _first_changed_node(path, node_hashes)
        if first is None:  # the file matches now (e.g. it was just regenerated)
            raise
        raise AssertionError(f"golden: first node whose output changed: {first}\n{exc}") from None


def _first_changed_node(path: Path, node_hashes: Mapping[str, str]) -> str | None:
    """First node, in the current order, whose hash differs from the golden file."""
    import yaml  # noqa: PLC0415  (test-only dependency, comes with pytest-regressions)

    stored: dict[str, list[dict[str, str]]] = yaml.safe_load(path.read_text(encoding="utf-8"))
    expected = {n["node"]: n["hash"] for n in stored["nodes"]}
    for node, h in node_hashes.items():
        if expected.get(node) != h:
            return f"{node} (expected {expected.get(node, 'no entry')}, got {h})"
    removed = [n for n in expected if n not in node_hashes]
    return f"{removed[0]} (missing from this run)" if removed else None


# ---- Dummy blocks (T1.02a) ----------------------------------------------------------
# The smallest stateless and fitted blocks, used to test the block contract, the
# registry, state serialisation (T1.02b), the parameter schema (T1.03) and the engine.


@dataclass(frozen=True)
class DummyOffsetParams:
    offset: float = Param(
        0.0, min=-1e6, max=1e6, tooltip_key="blocks.testing.offset.params.offset.tip"
    )


class DummyOffset(Block):
    """Stateless dummy block: adds ``offset`` to every value."""

    block_id = "testing.offset"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = DummyOffsetParams

    def apply(self, spectra: SpectralDataset, params: DummyOffsetParams) -> SpectralDataset:
        return spectra.with_X(spectra.X + params.offset, step=f"Offset({params.offset})")


class DummyCenter(Block):
    """Fitted dummy block: subtracts the column means of the training rows."""

    block_id = "testing.center"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = True
    tier = "P1"
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"), port("transform", "Transform"))

    def fit(self, spectra: SpectralDataset, params: NoParams) -> State:  # noqa: ARG002
        return State({"n_fitted": spectra.X.shape[0]}, {"mean": spectra.X.mean(axis=0)})

    def apply(
        self,
        spectra: SpectralDataset,
        params: NoParams,  # noqa: ARG002
        state: State,
    ) -> SpectralDataset:
        return spectra.with_X(spectra.X - state.arrays["mean"], step="Center")


@dataclass(frozen=True)
class DummySchemaParams:
    window: int = Param(15, min=5, max=101, odd_only=True, unit="points")
    polyorder: int = Param(2, min=0, max=6, constraint="polyorder < window")
    scale: float = Param(1.0, min=0.0, unit="%", advanced=True)
    mode: str = Param("mean", choices=("mean", "median"))
    deriv: int = Param(0, choices=(0, 1, 2))
    clip: bool = Param(False)
    label: str = Param("", visible_if=("mode", ("median",)))
    ranges: tuple[tuple[float, float], ...] = Param(((1700.0, 900.0),))  # stored as (900.0, 1700.0)


class DummySchema(Block):
    """Stateless dummy block with one parameter per schema type; returns its input."""

    block_id = "testing.schema"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = DummySchemaParams

    def apply(self, spectra: SpectralDataset, params: DummySchemaParams) -> SpectralDataset:  # noqa: ARG002
        return spectra
