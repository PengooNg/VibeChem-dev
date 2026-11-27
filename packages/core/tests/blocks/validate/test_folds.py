# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/validate/test_folds.py
"""Tests for the CV fold generators (docs/METHODS.md §5)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from vibechem_core.block import (
    BLOCK_INPUT_REQUIREMENT_MISSING,
    BLOCK_PARAM_INVALID,
    NoParams,
    parse_params,
)
from vibechem_core.blocks.validate.folds import (
    ContiguousBlocks,
    FoldParams,
    GroupKFold,
    KFold,
    LeaveOneOut,
    RepeatedKFold,
    RepeatedKFoldParams,
    ShuffledFoldParams,
    VenetianBlinds,
)
from vibechem_core.data import Axis, FoldSet, SpectralDataset
from vibechem_core.errors import BlockInputError, ParamError
from vibechem_core.testing import assert_reference

OFFSET = 50  # row_index = position + OFFSET, so positions and row_index values differ

BLOCKS: dict[str, tuple[Any, type[Any]]] = {
    "kfold": (KFold, ShuffledFoldParams),
    "venetian": (VenetianBlinds, FoldParams),
    "contiguous": (ContiguousBlocks, FoldParams),
    "loo": (LeaveOneOut, NoParams),
    "repeated_kfold": (RepeatedKFold, RepeatedKFoldParams),
    "group_kfold": (GroupKFold, ShuffledFoldParams),
}


def make_dataset(n: int, groups: list[str] | None = None) -> SpectralDataset:
    return SpectralDataset(
        np.zeros((n, 2)),
        Axis(np.array([1.0, 2.0]), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n) + OFFSET,
        source_id="ds_test",
        group_ids=groups,
    )


def run(scheme: str, data: SpectralDataset, rng: Any = None, **values: object) -> FoldSet:
    block, params_type = BLOCKS[scheme]
    params = parse_params(params_type, values)
    if rng is None:
        return block().apply(data, params)
    return block().apply(data, params, rng=rng)


def validation_positions(folds: FoldSet) -> list[list[int]]:
    return [(f.validation - OFFSET).tolist() for f in folds.folds]


GROUPS = ["g3", "g0", "g1", "g0", "g2", "g4", "g1", "g3", "g2", "g0", "g5", "g6", "g5"]


@pytest.mark.parametrize(
    ("scheme", "values", "groups"),
    [
        ("kfold", {"k": 4, "seed": 3}, None),
        ("kfold", {"k": 3, "shuffle": False}, None),
        ("venetian", {"k": 4}, None),
        ("contiguous", {"k": 4}, None),
        ("loo", {}, None),
        ("loo", {}, GROUPS),
        ("repeated_kfold", {"k": 3, "repeats": 3, "seed": 1}, None),
        ("group_kfold", {"k": 3, "seed": 2}, GROUPS),
    ],
)
def test_folds_partition_rows_and_keep_groups_whole(
    scheme: str, values: dict[str, object], groups: list[str] | None
) -> None:
    data = make_dataset(len(GROUPS), groups)
    folds = run(scheme, data, **values)
    labels = np.array(GROUPS) if groups else np.arange(len(GROUPS)).astype(str)

    def unit_of(rows: NDArray[np.int64]) -> NDArray[np.str_]:
        return labels[rows - OFFSET]

    assert folds.scheme == scheme
    assert folds.n_samples == data.n_samples
    for repeat in range(folds.n_repeats):
        in_repeat = [f for f in folds.folds if f.repeat == repeat]
        validated = np.concatenate([f.validation for f in in_repeat])
        assert sorted(validated.tolist()) == data.row_index.tolist()  # each row exactly once
        sizes = [np.unique(unit_of(f.validation)).size for f in in_repeat]
        assert max(sizes) - min(sizes) <= 1  # in units
        for f in in_repeat:
            assert (
                sorted(np.concatenate([f.train, f.validation]).tolist()) == data.row_index.tolist()
            )
            if groups:
                assert not set(unit_of(f.train)) & set(unit_of(f.validation))
    assert folds.groups_respected


@pytest.mark.parametrize(
    ("scheme", "values"),
    [("kfold", {"k": 3}), ("repeated_kfold", {"k": 3, "repeats": 2}), ("group_kfold", {"k": 3})],
)
def test_same_seed_same_folds(scheme: str, values: dict[str, object]) -> None:
    data = make_dataset(len(GROUPS), GROUPS)
    first = validation_positions(run(scheme, data, seed=4, **values))
    assert validation_positions(run(scheme, data, seed=4, **values)) == first
    assert validation_positions(run(scheme, data, seed=5, **values)) != first
    explicit = run(scheme, data, rng=np.random.default_rng(9), **values)
    assert explicit.seed == int(np.random.default_rng(9).integers(2**32))
    again = run(scheme, data, rng=np.random.default_rng(9), **values)
    assert validation_positions(again) == validation_positions(explicit)
    assert run(scheme, data, seed=4, **values).seed == 4


def test_hand_listed_folds() -> None:
    seven = make_dataset(7)
    groups = make_dataset(7, ["a", "a", "a", "b", "b", "c", "d"])
    cases = {
        "k-fold unshuffled (7 rows, k = 3)": (
            run("kfold", seven, k=3, shuffle=False),
            [[0, 1, 2], [3, 4], [5, 6]],
        ),
        "venetian blinds (7 rows, k = 3)": (
            run("venetian", seven, k=3),
            [[0, 3, 6], [1, 4], [2, 5]],
        ),
        "contiguous blocks (7 rows, k = 3)": (
            run("contiguous", seven, k=3),
            [[0, 1, 2], [3, 4], [5, 6]],
        ),
        "leave-one-out (3 rows)": (run("loo", make_dataset(3)), [[0], [1], [2]]),
        "leave-one-group-out (groups b a b c)": (
            run("loo", make_dataset(4, ["b", "a", "b", "c"])),
            [[1], [0, 2], [3]],
        ),
        # largest group first to the lightest fold (equal sizes: later label first,
        # lowest fold on ties): a(3) -> 0, b(2) -> 1, d(1) -> 1, c(1) -> 0
        "group k-fold unshuffled (group sizes 3 2 1 1, k = 2)": (
            run("group_kfold", groups, k=2, shuffle=False),
            [[0, 1, 2, 5], [3, 4, 6]],
        ),
    }
    for method, (folds, expected) in cases.items():
        actual = validation_positions(folds)
        assert_reference(
            method=f"CV folds: {method}, folds differing from the hand list",
            dataset="hand calculation",
            actual=sum(a != e for a, e in zip(actual, expected, strict=False))
            + abs(len(actual) - len(expected)),
            expected=0,
            rtol=0,
            atol=0,
            source="METHODS.md §5 definitions, listed by hand",
        )
        assert folds.seed is None
    assert [(f.fold, f.repeat) for f in run("repeated_kfold", seven, k=3, repeats=2).folds] == [
        (0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1),
    ]  # fmt: skip


def test_contiguous_blocks_equal_unshuffled_kfold() -> None:
    data = make_dataset(11)
    assert validation_positions(run("contiguous", data, k=4)) == validation_positions(
        run("kfold", data, k=4, shuffle=False)
    )


@pytest.mark.parametrize("scheme", ["kfold", "venetian", "contiguous", "repeated_kfold"])
def test_schemes_that_ignore_groups_report_it(scheme: str) -> None:
    assert not run(scheme, make_dataset(6, ["a", "a", "b", "b", "c", "c"]), k=2).groups_respected
    assert run(scheme, make_dataset(6), k=2).groups_respected


@pytest.mark.parametrize(
    ("scheme", "n", "groups", "high"),
    [
        ("kfold", 4, None, 4),
        ("venetian", 4, None, 4),
        ("contiguous", 4, None, 4),
        ("repeated_kfold", 4, None, 4),
        ("group_kfold", 6, ["a", "a", "b", "b", "c", "c"], 3),
    ],
)
def test_k_above_units_is_rejected(
    scheme: str, n: int, groups: list[str] | None, high: int
) -> None:
    data = make_dataset(n, groups)
    assert run(scheme, data, k=high).n_folds == high  # k = n_units is allowed (Q8)
    with pytest.raises(ParamError) as err:
        run(scheme, data, k=high + 1)
    assert err.value.code == BLOCK_PARAM_INVALID
    assert err.value.params["constraint"] == f"2 <= k <= {high}"


@pytest.mark.parametrize("groups", [None, ["a", "", "b", "b"]])
def test_grouped_schemes_need_every_group_label(groups: list[str] | None) -> None:
    data = make_dataset(4, groups)
    with pytest.raises(BlockInputError) as err:
        run("group_kfold", data, k=2)
    assert err.value.code == BLOCK_INPUT_REQUIREMENT_MISSING
    if groups is not None:
        with pytest.raises(BlockInputError):
            run("loo", data)
