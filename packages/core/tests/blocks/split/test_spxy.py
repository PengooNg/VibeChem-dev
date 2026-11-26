# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/split/test_spxy.py
"""Tests for ``split.spxy`` (docs/METHODS.md#spxy) and the gasoline cross-check of
``split.kennard_stone`` and ``split.spxy`` (testdata/expected/gasoline_nir_splits.json)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from scipy.spatial.distance import pdist, squareform

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING
from vibechem_core.blocks.split import BLOCK_CONSTANT_RESPONSE
from vibechem_core.blocks.split.kennard_stone import KennardStone, KennardStoneParams, ks_order
from vibechem_core.blocks.split.spxy import SPXY
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError
from vibechem_core.reference_datasets import load_expected, load_reference_dataset
from vibechem_core.testing import assert_reference

# Hand-worked example: x = 0, 1, 2, 3, 10 (second column 0), y = 0, 10, 0, 0, 1.
X5 = [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [10.0, 0.0]]
Y5 = [[0.0], [10.0], [0.0], [0.0], [1.0]]


def make_dataset(X: Any, y: Any, sample_ids: list[str] | None = None) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = int(x.shape[0]), int(x.shape[1])
    return SpectralDataset(
        x,
        Axis(np.arange(1.0, p + 1.0), "nm"),
        signal_unit="absorbance",
        sample_ids=sample_ids or [f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
        y=y,
        y_columns=["c"],
        y_units=["%"],
    )


def test_hand_worked_spxy_order_differs_from_kennard_stone() -> None:
    # d_xy = |dx|/10 + |dy|/10. Largest pair 1-4 (0.9 + 0.9). Min to {1, 4}: 0: 1.1,
    # 2: 0.9, 3: 0.8 -> 0. Then 2: 0.2 (to 0), 3: 0.3 -> 3, last 2: SPXY order 1, 4, 0, 3, 2.
    # KS on x: pair 0-4, then 3 (min 3), then 1 and 2 tie at 1 -> 1: order 0, 4, 3, 1, 2.
    # With n_test = 2 (ceil(0.25 * 5)): SPXY test {3, 2}, KS test {1, 2}.
    data = make_dataset(X5, Y5)
    spxy = SPXY().apply(data, KennardStoneParams())["test"].sample_ids
    ks = KennardStone().apply(data, KennardStoneParams())["test"].sample_ids
    assert spxy == ("s2", "s3")
    assert ks == ("s1", "s2")


def test_constant_response_is_an_error_not_a_fallback() -> None:
    with pytest.raises(BlockInputError) as info:
        SPXY().apply(make_dataset(X5, [[1.0]] * 5), KennardStoneParams())
    assert info.value.code == BLOCK_CONSTANT_RESPONSE


def test_constant_y_with_uneven_groups_is_caught_before_averaging() -> None:
    # Means of 0.1 over groups of 3 and 2 rows differ by rounding noise (~1e-17).
    data = make_dataset(np.arange(14.0).reshape(7, 2), [[0.1]] * 7)
    data = SpectralDataset(
        data.X, data.axis, signal_unit="absorbance", sample_ids=data.sample_ids,
        row_index=data.row_index, source_id="ds_test", group_ids=list("aaabbcc"),
        y=data.y, y_columns=["c"], y_units=["%"],
    )  # fmt: skip
    with pytest.raises(BlockInputError) as info:
        SPXY().apply(data, KennardStoneParams())
    assert info.value.code == BLOCK_CONSTANT_RESPONSE


def test_group_aware_spxy_keeps_groups_whole() -> None:
    rng = np.random.default_rng(4)
    groups = [f"g{i // 2}" for i in range(12)]
    data = SpectralDataset(
        rng.normal(size=(12, 3)), Axis(np.array([1.0, 2.0, 3.0]), "nm"),
        signal_unit="absorbance", sample_ids=[f"s{i}" for i in range(12)],
        row_index=np.arange(12), source_id="ds_test", group_ids=groups,
        y=rng.normal(size=(12, 1)), y_columns=["c"], y_units=["%"],
    )  # fmt: skip
    out = SPXY().apply(data, KennardStoneParams())
    test_groups = {groups[int(s[1:])] for s in out["test"].sample_ids}
    train_groups = {groups[int(s[1:])] for s in out["train"].sample_ids}
    assert len(test_groups) == 2  # ceil(0.25 * 6 groups)
    assert not test_groups & train_groups


def test_missing_y_is_an_error() -> None:
    no_y = SpectralDataset(
        np.asarray(X5),
        Axis(np.array([1.0, 2.0]), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(5)],
        row_index=np.arange(5),
        source_id="ds_test",
    )
    with pytest.raises(BlockInputError) as info:
        SPXY().apply(no_y, KennardStoneParams())
    assert info.value.code == BLOCK_INPUT_REQUIREMENT_MISSING


@pytest.mark.parametrize(("block", "key"), [(KennardStone, "kennard_stone"), (SPXY, "spxy")])
def test_gasoline_selection_matches_kennard_stone_package(
    block: type[KennardStone], key: str
) -> None:
    ref = load_reference_dataset("gasoline_nir")
    doc = load_expected("gasoline_nir_splits")
    expected = doc["values"][key]
    ids = [str(s) for s in ref.sample_ids]
    data = make_dataset(ref.spectra, ref.target.reshape(-1, 1), ids)

    out = block().apply(data, KennardStoneParams())
    test = sorted(int(s) for s in out["test"].sample_ids)
    assert test == expected["test"]
    # the training set lists rows in input order; the selection order is checked on train_order
    assert sorted(int(s) for s in out["train"].sample_ids) == sorted(expected["train_order"])


@pytest.mark.parametrize("key", ["kennard_stone", "spxy"])
def test_gasoline_selection_order_matches(key: str) -> None:
    ref = load_reference_dataset("gasoline_nir")
    doc = load_expected("gasoline_nir_splits")
    X, y = ref.spectra, ref.target.reshape(-1, 1)
    d = squareform(pdist(X))
    if key == "spxy":
        dy = squareform(pdist(y))
        d = d / d.max() + dy / dy.max()
    order = ks_order(d, np.zeros(len(X)), "most_distant")
    picked = [int(ref.sample_ids[i]) for i in order[:45]]
    expected = doc["values"][key]["train_order"]
    leading = next((i for i, (a, b) in enumerate(zip(picked, expected, strict=True)) if a != b), 45)
    assert_reference(
        method=f"{key} selection order: leading training picks equal to reference (of 45)",
        dataset="gasoline_nir",
        actual=leading,
        expected=45,
        rtol=0,
        atol=0,
        source="kennard-stone 4.1.1 package, testdata/expected/gasoline_nir_splits.json",
    )
