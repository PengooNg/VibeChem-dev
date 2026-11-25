# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/preprocess/test_msc.py
"""Tests for ``preprocess.msc`` (docs/METHODS.md#msc)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vibechem_core.block import NoParams, State, load_state, save_state
from vibechem_core.blocks.preprocess import BLOCK_CONSTANT_SPECTRA, BLOCK_MSC_SLOPE_INVALID
from vibechem_core.blocks.preprocess.msc import MSC
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError
from vibechem_core.testing import assert_close, assert_reference

# Hand calculation (3 x 5). Column mean m = [0, 1, 2, 3, 4]; centred m is
# [-2, -1, 0, 1, 2] with sum of squares 10, so b = sum(mc * x) / 10 and
# a = mean(x) - 2 b.
#   row 0 [1, 1, 2, 3, 3]: b = 6/10 = 0.6, a = 2 - 1.2 = 0.8
#   row 1 [0, 2, 4, 6, 8]: b = 2, a = 0
#   row 2 [-1, 0, 0, 0, 1]: b = 4/10 = 0.4, a = 0 - 0.8 = -0.8
HAND_X = [[1.0, 1.0, 2.0, 3.0, 3.0], [0.0, 2.0, 4.0, 6.0, 8.0], [-1.0, 0.0, 0.0, 0.0, 1.0]]
HAND_M = [0.0, 1.0, 2.0, 3.0, 4.0]
HAND_EXPECTED = [
    [1 / 3, 1 / 3, 2.0, 11 / 3, 11 / 3],  # (x - 0.8) / 0.6
    [0.0, 1.0, 2.0, 3.0, 4.0],  # (x - 0) / 2
    [-0.5, 2.0, 2.0, 2.0, 4.5],  # (x + 0.8) / 0.4
]


def assert_exact(actual: np.typing.ArrayLike, expected: np.typing.ArrayLike, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-exact (METHODS §1)


def make_dataset(X: np.typing.ArrayLike) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = int(x.shape[0]), int(x.shape[1])
    return SpectralDataset(
        x,
        Axis(np.linspace(4000.0, 400.0, p), "cm-1"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
    )


def fit_apply(
    train: np.typing.ArrayLike,
    data: np.typing.ArrayLike | None = None,
    reference: np.typing.ArrayLike | None = None,
) -> SpectralDataset:
    ref = None if reference is None else make_dataset(reference)
    state = MSC().fit(make_dataset(train), NoParams(), reference=ref)
    target = make_dataset(train if data is None else data)
    return MSC().apply(target, NoParams(), state, reference=ref)


def test_metadata() -> None:
    meta = MSC.metadata()
    assert meta.fitted is True
    inputs = [p.to_dict("input") for p in meta.inputs]
    assert inputs[1] == {
        "port_id": "reference",
        "port_type": "Spectra",
        "required": False,
        "multiple": False,
        "axis_match": "spectra",
    }
    assert [p.port_type for p in meta.outputs] == ["Spectra", "Transform"]


def test_hand_calculation_with_training_mean() -> None:
    out = fit_apply(HAND_X)
    assert_exact(out.X, HAND_EXPECTED, "MSC")
    for i, j in ((0, 0), (2, 0), (2, 4)):
        assert_reference(
            method=f"MSC (reference mean, element [{i}, {j}])",
            dataset="hand calculation 3x5",
            actual=float(out.X[i, j]),
            expected=HAND_EXPECTED[i][j],
            rtol=1e-10,
            atol=1e-12,
            source="hand calculation (METHODS.md#msc)",
        )
    assert out.history == ("MSC(reference=mean, rows=3)",)


def test_reference_learned_in_fit_is_the_training_mean() -> None:
    state = MSC().fit(make_dataset(HAND_X), NoParams())
    assert_exact(state.arrays["m"], HAND_M, "m")
    assert state.values == {"reference": "mean", "n_reference_rows": 3}


@pytest.mark.parametrize(
    "reference",
    [[HAND_M], [[-1.0, 0.0, 1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0, 5.0]]],
    ids=["one row", "two rows (mean used)"],
)
def test_user_reference(reference: list[list[float]]) -> None:
    # Training rows whose mean is not HAND_M, so only the user reference can give
    # HAND_EXPECTED.
    train = [[5.0, 1.0, 0.0, 2.0, 9.0], [1.0, 3.0, 2.0, 7.0, 4.0]]
    out = fit_apply(train, HAND_X, reference)
    assert_exact(out.X, HAND_EXPECTED, "MSC with user reference")
    assert out.history == (f"MSC(reference=input, rows={len(reference)})",)


def test_exact_affine_spectrum_gives_the_reference() -> None:
    # D1 regression test: x = a + b m must give back m exactly.
    rng = np.random.default_rng(7)
    train = rng.normal(size=(8, 50)) + np.linspace(0.0, 3.0, 50)
    m = train.mean(axis=0)
    new = np.vstack([0.3 + 1.7 * m, -2.0 + 0.25 * m, 5.0 * m])
    out = fit_apply(train, new)
    assert_exact(out.X, np.vstack([m, m, m]), "MSC(a + b m)")
    assert_reference(
        method="MSC (x = a + b m, max abs difference to m)",
        dataset="synthetic 50 points",
        actual=float(np.abs(out.X - m).max()),
        expected=0.0,
        rtol=0.0,
        atol=1e-12,
        source="algebraic identity (METHODS.md#msc, D1)",
    )


def test_apply_uses_training_reference_only() -> None:
    # Fitting on the training rows and applying to other rows must equal using the
    # training mean, never a mean that includes the new rows (D2).
    rng = np.random.default_rng(3)
    base = np.linspace(1.0, 2.0, 20)
    train = base + 0.1 * rng.normal(size=(6, 20))
    test = 2.0 * base + 0.5 + 0.1 * rng.normal(size=(4, 20))
    out = fit_apply(train, test)
    m = train.mean(axis=0)
    design = np.column_stack([np.ones(20), m])
    (a, b), *_ = np.linalg.lstsq(design, test.T)  # [1, m] directly, uncentred
    assert_exact(out.X, (test - a[:, np.newaxis]) / b[:, np.newaxis], "MSC on test rows")


def test_non_positive_slope_is_rejected() -> None:
    with pytest.raises(BlockInputError) as info:
        fit_apply(HAND_X, [HAND_X[0], [-x for x in HAND_M], [2.0] * 5])
    assert info.value.code == BLOCK_MSC_SLOPE_INVALID
    assert info.value.params["rows"] == [1, 2]  # b = -1 and b = 0 (constant spectrum)


@pytest.mark.parametrize(
    ("train", "reference", "kind"),
    [([[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]], None, "mean"), (HAND_X, [[4.0] * 5], "input")],
)
def test_constant_reference_is_rejected(
    train: list[list[float]], reference: list[list[float]] | None, kind: str
) -> None:
    ref = None if reference is None else make_dataset(reference)
    with pytest.raises(BlockInputError) as info:
        MSC().fit(make_dataset(train), NoParams(), reference=ref)
    assert info.value.code == BLOCK_CONSTANT_SPECTRA
    assert info.value.params["reference"] == kind


def test_state_save_load_round_trip(tmp_path: Path) -> None:
    state = MSC().fit(make_dataset(HAND_X), NoParams())
    save_state(state, tmp_path / "msc")
    loaded: State = load_state(tmp_path / "msc")
    out = MSC().apply(make_dataset(HAND_X), NoParams(), loaded)
    assert_exact(out.X, HAND_EXPECTED, "MSC after load")
    assert loaded.values == state.values
