# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/split/test_kennard_stone.py
"""Tests for ``split.kennard_stone`` (docs/METHODS.md#kennard-stone, #group-aware-split)."""

from __future__ import annotations

import numpy as np
import pytest

from vibechem_core.block import BLOCK_PARAM_INVALID, parse_params
from vibechem_core.blocks.split.kennard_stone import (
    KennardStone,
    KennardStoneParams,
    distance_space,
    ks_order,
)
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.testing import assert_reference

# Hand-worked example (squared distances written out in the test below).
POINTS = [[0, 0], [10, 0], [5, 1], [2, 8], [9, 9], [6, 5]]


def make_dataset(
    X: np.typing.ArrayLike, groups: list[str] | None = None, y: np.typing.ArrayLike | None = None
) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = int(x.shape[0]), int(x.shape[1])
    k = 0 if y is None else np.asarray(y).shape[1]
    return SpectralDataset(
        x,
        Axis(np.arange(1.0, p + 1.0), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n) + 100,
        source_id="ds_test",
        group_ids=groups,
        y=y,
        y_columns=[f"c{j}" for j in range(k)],
        y_units=["%"] * k,
    )


def order_of(params: dict[str, object]) -> list[int]:
    p = parse_params(KennardStoneParams, params)
    z = np.asarray(POINTS, dtype=float)
    D = np.sqrt(((z[:, None] - z[None]) ** 2).sum(axis=2))
    return ks_order(D, np.linalg.norm(z - z.mean(axis=0), axis=1), p.start).tolist()


def test_hand_worked_order_most_distant() -> None:
    # Squared distances: 0-4 = 162 is the largest pair. Min squared distance to {0, 4}:
    # 1: 82, 2: 26, 3: 50, 5: 25 -> 1. Then to {0, 4, 1}: 2: 26, 3: 50, 5: 25 -> 3.
    # Then 2: 26 (vs 2-3 = 58), 5: 25 -> 2, last 5.
    assert order_of({}) == [0, 4, 1, 3, 2, 5]


def test_hand_worked_order_nearest_mean_and_tie_rule() -> None:
    # Mean (32/6, 23/6); squared distances to it: 43.1, 36.5, 8.14, 28.5, 40.1, 1.81 -> 5.
    # To {5}: 0: 61, 1: 41, 2: 17, 3: 25, 4: 25 -> 0. To {5, 0}: 1: 41 -> 1.
    # To {5, 0, 1}: 2: 17, 3: 25, 4: 25 -> tie, lowest index 3. Then 4 (25 vs 17), last 2.
    assert order_of({"start": "nearest_mean"}) == [5, 0, 1, 3, 4, 2]


def test_block_splits_hand_example_and_records_reference() -> None:
    # 6 rows, test_fraction 0.25 -> ceil(1.5) = 2 test rows: the last two of the order.
    out = KennardStone().apply(make_dataset(POINTS), KennardStoneParams())
    folds = out["folds"]
    (fold,) = folds.folds
    assert sorted(fold.validation.tolist()) == [102, 105]  # row_index values, not positions
    assert sorted(fold.train.tolist()) == [100, 101, 103, 104]
    assert folds.scheme == "holdout"
    assert folds.groups_respected
    assert folds.seed is None
    assert out["test"].sample_ids == ("s2", "s5")
    assert_reference(
        method="Kennard-Stone order (most_distant, position of 6th pick)",
        dataset="hand calculation 6 points in 2-D",
        actual=order_of({})[-1],
        expected=5,
        rtol=0,
        atol=0,
        source="hand calculation (squared distances in the test)",
    )


def test_groups_stay_whole_and_one_row_per_group_equals_plain() -> None:
    rng = np.random.default_rng(1)
    X = rng.normal(size=(12, 4))
    groups = [f"g{i // 3}" for i in range(12)]  # 4 groups of 3 replicates
    out = KennardStone().apply(make_dataset(X, groups), KennardStoneParams())
    (fold,) = out["folds"].folds
    group_of = {100 + i: g for i, g in enumerate(groups)}
    train_groups = {group_of[int(r)] for r in fold.train}
    test_groups = {group_of[int(r)] for r in fold.validation}
    assert not train_groups & test_groups
    assert len(test_groups) == 1  # ceil(0.25 * 4 groups)

    plain = KennardStone().apply(make_dataset(X), KennardStoneParams())
    one_per_group = KennardStone().apply(
        make_dataset(X, [f"g{i}" for i in range(12)]), KennardStoneParams()
    )
    for a, b in zip(plain["folds"].folds, one_per_group["folds"].folds, strict=True):
        np.testing.assert_array_equal(a.validation, b.validation)


def test_groups_ignored_is_recorded() -> None:
    X = np.random.default_rng(2).normal(size=(8, 3))
    params = parse_params(KennardStoneParams, {"group_aware": False})
    out = KennardStone().apply(make_dataset(X, ["a", "a", "b", "b"] * 2), params)
    assert out["folds"].groups_respected is False


def test_pca_space_with_all_components_equals_raw_x() -> None:
    # Distances are invariant under the PCA rotation when every component is kept.
    X = np.random.default_rng(3).normal(size=(10, 4))
    raw = KennardStone().apply(make_dataset(X), KennardStoneParams())
    pca = KennardStone().apply(
        make_dataset(X), parse_params(KennardStoneParams, {"space": "pca", "variance": 1.0})
    )
    np.testing.assert_array_equal(
        raw["folds"].folds[0].validation, pca["folds"].folds[0].validation
    )


@pytest.mark.parametrize(
    ("values", "param_id"),
    [({"test_fraction": 0.0}, "test_fraction"), ({"size_by": "count", "n_test": 6}, "n_test")],
)
def test_test_size_must_leave_both_sets_non_empty(values: dict[str, object], param_id: str) -> None:
    with pytest.raises(ParamError) as info:
        KennardStone().apply(make_dataset(POINTS), parse_params(KennardStoneParams, values))
    assert info.value.code == BLOCK_PARAM_INVALID
    assert info.value.params["param_id"] == param_id
    assert info.value.params["reason"] == "constraint"


def test_metadata_is_valid() -> None:
    meta = KennardStone.metadata()
    assert [p.port_id for p in meta.outputs] == ["folds", "train", "test"]


def test_pca_variance_keeps_fewest_components_above_the_fraction() -> None:
    # Hand-made: centred column variances 100 : 1 : 0 -> explained 0.990099, 1, 1.
    X = np.array([[10.0, 1.0, 0.0], [-10.0, -1.0, 0.0], [10.0, -1.0, 0.0], [-10.0, 1.0, 0.0]])
    for variance, k in ((0.99, 1), (0.995, 2)):
        params = parse_params(KennardStoneParams, {"space": "pca", "variance": variance})
        assert distance_space(X, params).shape == (4, k)
