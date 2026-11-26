# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/split/test_random_split.py
"""Tests for ``split.random`` (docs/METHODS.md#random-split, #group-aware-split)."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pytest

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, BLOCK_PARAM_INVALID, parse_params
from vibechem_core.blocks.split import BLOCK_SPLIT_STRATUM_TOO_SMALL
from vibechem_core.blocks.split.random_split import RandomSplit, RandomSplitParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError, ParamError, VibeChemWarning
from vibechem_core.testing import assert_reference


def make_dataset(
    n: int,
    classes: list[str] | None = None,
    groups: list[str] | None = None,
    y: Any = None,
) -> SpectralDataset:
    return SpectralDataset(
        np.random.default_rng(0).normal(size=(n, 3)),
        Axis(np.array([1.0, 2.0, 3.0]), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n) + 50,
        source_id="ds_test",
        group_ids=groups,
        classes=classes,
        class_column=None if classes is None else "kind",
        y=y,
        y_columns=() if y is None else ("c",),
        y_units=() if y is None else ("%",),
    )


def split(data: SpectralDataset, **values: object) -> tuple[list[str], list[str], Any]:
    out = RandomSplit().apply(data, parse_params(RandomSplitParams, values))
    return list(out["train"].sample_ids), list(out["test"].sample_ids), out["folds"]


def test_partition_sizes_and_seed() -> None:
    data = make_dataset(20)
    train, test, folds = split(data, seed=7)
    assert len(test) == 5  # ceil(0.25 * 20)
    assert sorted(train + test) == sorted(data.sample_ids)
    assert folds.seed == 7
    assert split(data, seed=7)[1] == test
    assert split(data, seed=8)[1] != test
    rng_out = RandomSplit().apply(data, RandomSplitParams(), rng=np.random.default_rng(7))
    assert rng_out["folds"].seed is None  # explicit Generator: no seed parameter to record


def test_stratified_by_class_keeps_shares_exactly() -> None:
    # 4 classes x 8 rows, test_fraction 0.25 -> 8 test rows, 2 per class (hand count).
    classes = [c for c in "ABCD" for _ in range(8)]
    _, test, _ = split(make_dataset(32, classes=classes), stratify="classes")
    per_class = Counter(classes[int(s[1:])] for s in test)
    assert_reference(
        method="Stratified random split (test rows of class A, 2 of 8)",
        dataset="hand calculation 4 classes x 8 rows",
        actual=per_class["A"],
        expected=2,
        rtol=0,
        atol=0,
        source="hand count: 0.25 x 8 rows",
    )
    assert per_class == {"A": 2, "B": 2, "C": 2, "D": 2}


def test_stratified_by_y_bins_covers_every_bin() -> None:
    y = np.arange(20.0).reshape(-1, 1)  # 5 quantile bins of 4 rows
    _, test, _ = split(make_dataset(20, y=y), stratify="y", test_fraction=0.25)
    assert sorted(int(s[1:]) // 4 for s in test) == [0, 1, 2, 3, 4]


def test_small_stratum_goes_to_training_with_a_warning() -> None:
    classes = ["A"] * 6 + ["B"] * 6 + ["C"]
    with pytest.warns(VibeChemWarning) as record:
        train, _, _ = split(make_dataset(13, classes=classes), stratify="classes")
    assert record[0].message.code == BLOCK_SPLIT_STRATUM_TOO_SMALL  # type: ignore[union-attr]
    assert record[0].message.params["strata"] == ["C"]  # type: ignore[union-attr]
    assert "s12" in train


def test_groups_stay_whole_with_majority_class_strata() -> None:
    groups = [f"g{i // 2}" for i in range(16)]  # 8 units of 2 rows
    classes = ["A"] * 8 + ["B"] * 8
    train, test, folds = split(
        make_dataset(16, classes=classes, groups=groups), stratify="classes", seed=3
    )
    train_groups = {groups[int(s[1:])] for s in train}
    test_groups = {groups[int(s[1:])] for s in test}
    assert not train_groups & test_groups
    assert len(test_groups) == 2  # ceil(0.25 * 8 units), one per class
    assert folds.groups_respected


@pytest.mark.parametrize(
    ("data", "values", "code"),
    [
        (make_dataset(10), {"stratify": "classes"}, BLOCK_INPUT_REQUIREMENT_MISSING),
        (make_dataset(10), {"stratify": "y"}, BLOCK_INPUT_REQUIREMENT_MISSING),
        (make_dataset(4, classes=list("AABB")), {"stratify": "classes"}, BLOCK_PARAM_INVALID),
    ],
)
def test_errors(data: SpectralDataset, values: dict[str, object], code: str) -> None:
    # The last case: 1 test row (ceil(0.25 * 4)) cannot hold 2 strata.
    with pytest.raises((BlockInputError, ParamError)) as info:
        RandomSplit().apply(data, parse_params(RandomSplitParams, values))
    assert info.value.code == code
