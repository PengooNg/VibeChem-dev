# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/preprocess/test_scaling.py
"""Tests for ``preprocess.mean_centre``, ``preprocess.autoscale`` and ``preprocess.pareto``
(docs/METHODS.md §3, incl. Y scaling)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from vibechem_core.block import (
    BLOCK_INPUT_AXIS_MISMATCH,
    BLOCK_INPUT_REQUIREMENT_MISSING,
    load_state,
    parse_params,
    save_state,
)
from vibechem_core.blocks.preprocess import BLOCK_CONSTANT_COLUMNS
from vibechem_core.blocks.preprocess.scaling import (
    Autoscale,
    MeanCentre,
    Pareto,
    ScalingParams,
    inverse_y,
)
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError, VibeChemWarning
from vibechem_core.testing import assert_close, assert_reference

# Hand calculation: training columns [1, 3, 5] and [1, 5, 9] have means 3 and 5 and
# SDs (ddof 1) sqrt(8/2) = 2 and sqrt(32/2) = 4. New row [7, 1] must use these.
TRAIN = [[1.0, 1.0], [3.0, 5.0], [5.0, 9.0]]
NEW = [[7.0, 1.0]]
R2 = math.sqrt(2.0)
EXPECTED = {
    MeanCentre: ([[-2.0, -4.0], [0.0, 0.0], [2.0, 4.0]], [[4.0, -4.0]]),
    Autoscale: ([[-1.0, -1.0], [0.0, 0.0], [1.0, 1.0]], [[2.0, -1.0]]),
    Pareto: ([[-R2, -2.0], [0.0, 0.0], [R2, 2.0]], [[2.0 * R2, -2.0]]),
}
BLOCKS = (MeanCentre, Autoscale, Pareto)
X_PARAMS = ScalingParams()
Y_PARAMS = parse_params(ScalingParams, {"target": "y"})


def assert_exact(actual: np.typing.ArrayLike, expected: np.typing.ArrayLike, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-exact (METHODS §1)


def make_dataset(X: np.typing.ArrayLike, y: np.typing.ArrayLike | None = None) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = int(x.shape[0]), int(x.shape[1])
    k = 0 if y is None else np.asarray(y).shape[1]
    return SpectralDataset(
        x,
        Axis(np.linspace(4000.0, 400.0, p), "cm-1"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
        y=y,
        y_columns=[f"c{j}" for j in range(k)],
        y_units=["%"] * k,
    )


@pytest.mark.parametrize("block", BLOCKS)
def test_hand_calculation_uses_training_statistics_only(block: type[MeanCentre]) -> None:
    # Done-when test (METHODS.md §3): new rows are scaled with the training mean and SD.
    expected_train, expected_new = EXPECTED[block]
    state = block().fit(make_dataset(TRAIN), X_PARAMS)
    train_out = block().apply(make_dataset(TRAIN), X_PARAMS, state)
    new_out = block().apply(make_dataset(NEW), X_PARAMS, state)
    assert_exact(train_out.X, expected_train, block.block_id)
    assert_exact(new_out.X, expected_new, f"{block.block_id} on new rows")
    assert_reference(
        method=f"{block.__name__} (new row [7, 1], training statistics)",
        dataset="hand calculation 3x2",
        actual=float(new_out.X[0, 0]),
        expected=expected_new[0][0],
        rtol=1e-10,
        atol=1e-12,
        source=f"hand calculation (METHODS.md#{block.block_id.split('.')[1].replace('_', '-')})",
    )
    assert new_out.history == (f"{block.__name__}(target=X)",)
    assert block.metadata().fitted is True


def test_constant_column_is_centred_unscaled_with_warning() -> None:
    with pytest.warns(VibeChemWarning) as record:
        state = Autoscale().fit(make_dataset([[1.0, 2.0], [3.0, 2.0]]), X_PARAMS)
    assert [(w.message.code, dict(w.message.params)) for w in record] == [  # type: ignore[union-attr]
        (BLOCK_CONSTANT_COLUMNS, {"columns": [1]})
    ]
    out = Autoscale().apply(make_dataset([[3.0, 5.0]]), X_PARAMS, state)
    assert_exact(out.X, [[0.5**0.5, 3.0]], "autoscale with a flat column")  # (3 - 2) / sqrt 2


@pytest.mark.parametrize("block", BLOCKS)
def test_y_scaling_and_inverse(block: type[MeanCentre]) -> None:
    # TRAIN as y (two responses): same numbers as the X hand calculation; X untouched.
    expected_train, expected_new = EXPECTED[block]
    state = block().fit(make_dataset(TRAIN, y=TRAIN), Y_PARAMS)
    out = block().apply(make_dataset(NEW, y=NEW), Y_PARAMS, state)
    assert out.y is not None
    assert_exact(out.y, expected_new, f"{block.block_id} on y")
    assert_exact(out.X, NEW, "X unchanged")
    assert_exact(inverse_y(state, np.asarray(expected_train)), TRAIN, "inverse_y round trip")
    assert out.history == (f"{block.__name__}(target=y)",)


def test_y_target_needs_the_fitted_y_columns() -> None:
    state = Autoscale().fit(make_dataset(TRAIN, y=TRAIN), Y_PARAMS)
    for data in (make_dataset(NEW), make_dataset(NEW, y=[[1.0]])):
        with pytest.raises(BlockInputError) as info:
            Autoscale().apply(data, Y_PARAMS, state)
        assert info.value.code == BLOCK_INPUT_REQUIREMENT_MISSING
        assert info.value.params == {"port_id": "spectra", "requirement": "y", "expected": "c0, c1"}
    with pytest.raises(BlockInputError):
        Autoscale().fit(make_dataset(TRAIN), Y_PARAMS)


def test_x_target_rejects_another_axis() -> None:
    state = MeanCentre().fit(make_dataset(TRAIN), X_PARAMS)
    with pytest.raises(BlockInputError) as info:
        MeanCentre().apply(make_dataset([[1.0, 2.0, 3.0]]), X_PARAMS, state)
    assert info.value.code == BLOCK_INPUT_AXIS_MISMATCH


def test_state_save_load_round_trip(tmp_path: Path) -> None:
    state = Pareto().fit(make_dataset(TRAIN), X_PARAMS)
    save_state(state, tmp_path / "pareto")
    out = Pareto().apply(make_dataset(NEW), X_PARAMS, load_state(tmp_path / "pareto"))
    assert_exact(out.X, EXPECTED[Pareto][1], "Pareto after load")
