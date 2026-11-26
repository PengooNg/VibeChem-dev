# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/model/test_plsda.py
"""Tests for ``model.plsda`` (docs/METHODS.md#plsda)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, parse_params
from vibechem_core.blocks.model.plsda import PLSDA, PLSDAParams
from vibechem_core.blocks.split import BLOCK_CONSTANT_RESPONSE
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import BlockInputError
from vibechem_core.reference_datasets import load_expected, load_reference_dataset
from vibechem_core.testing import assert_close, assert_reference


def make_dataset(X: Any, classes: Any | None) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = int(x.shape[0]), int(x.shape[1])
    return SpectralDataset(
        x,
        Axis(np.arange(1.0, p + 1.0), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
        classes=None if classes is None else [str(c) for c in classes],
        class_column=None if classes is None else "class",
    )


def params(**values: Any) -> PLSDAParams:
    return parse_params(PLSDAParams, values)


def scores(table: dict[str, Any]) -> np.ndarray[Any, Any]:
    return np.column_stack([v for name, v in table.items() if name.startswith("score_")])


def clustered(n_per_class: int, labels: list[str], seed: int) -> tuple[Any, list[str]]:
    rng = np.random.default_rng(seed)
    centres = rng.normal(scale=5.0, size=(len(labels), 8))
    X = np.vstack([c + rng.normal(size=(n_per_class, 8)) for c in centres])
    return X, [label for label in labels for _ in range(n_per_class)]


def test_binary_matches_hand_calculation() -> None:
    # X0 = X - (1.5, 1.5); w = (2, 1)/sqrt(5), t't = 8.2, p'w = 1, B_a = -(10, 5)/41, B_b = -B_a,
    # so score_a = 1/2 - (10 x0_1 + 5 x0_2)/41 and score_b = 1 - score_a (A = 1, by hand).
    X = [[0.0, 0.0], [1.0, 2.0], [2.0, 1.0], [3.0, 3.0]]
    state = PLSDA().fit(make_dataset(X, "aabb"), params(n_components=1))
    new = np.array([[0.0, 0.0], [1.0, 2.0], [2.0, 1.0], [3.0, 3.0], [1.5, 3.0]])
    table = PLSDA().apply(make_dataset(new, None), params(), state)
    x0 = new - 1.5
    score_a = 0.5 - (10 * x0[:, 0] + 5 * x0[:, 1]) / 41
    for i, (actual, expected) in enumerate(zip(table["score_a"], score_a, strict=True)):
        assert_reference(method="PLS-DA predicted indicator", dataset=f"hand calculation, row {i}",
                         actual=float(actual), expected=float(expected), rtol=1e-12, atol=1e-12,
                         source="hand-worked binary example, METHODS.md#plsda")  # fmt: skip
    assert_close(table["score_b"], 1 - score_a, rtol=1e-12, atol=1e-12, name="score_b")
    assert list(table["class_pred"]) == ["a", "a", "b", "b", "b"]
    assert list(table) == ["row_index", "sample_id", "class_pred", "score_a", "score_b"]


def test_tie_goes_to_the_lowest_class_index() -> None:
    X = [[0.0, 0.0], [1.0, 2.0], [2.0, 1.0], [3.0, 3.0]]
    state = PLSDA().fit(make_dataset(X, "bbaa"), params(n_components=1))
    table = PLSDA().apply(make_dataset([[1.5, 1.5]], None), params(), state)  # at the mean
    assert table["score_a"][0] == table["score_b"][0] == 0.5
    assert table["class_pred"][0] == "a"


@pytest.mark.parametrize("labels", [["no", "yes"], ["c", "a", "b"], ["d", "b", "c", "a"]])
def test_rows_sum_to_one_and_max_rule(labels: list[str]) -> None:
    X, y = clustered(10, labels, seed=len(labels))
    rng = np.random.default_rng(0)
    new = X + rng.normal(scale=3.0, size=X.shape)  # noisy rows, some misclassified
    state = PLSDA().fit(make_dataset(X, y), params(n_components=3, n_components_mode="fixed"))
    table = PLSDA().apply(make_dataset(new, None), params(), state)
    s = scores(table)
    ordered = sorted(labels)
    assert [name for name in table if name.startswith("score_")] == [f"score_{c}" for c in ordered]
    assert_close(s.sum(axis=1), np.ones(len(X)), rtol=1e-12, atol=1e-12, name="row sums")  # T-exact
    assert list(table["class_pred"]) == [ordered[g] for g in s.argmax(axis=1)]
    if len(labels) == 2:
        assert list(table["class_pred"] == "yes") == list(table["score_yes"] > 0.5)
    train = PLSDA().apply(make_dataset(X, None), params(), state)
    assert list(train["class_pred"]) == y  # well-separated clusters


def test_errors() -> None:
    X, _ = clustered(4, ["a", "b"], seed=1)
    with pytest.raises(BlockInputError) as missing:
        PLSDA().fit(make_dataset(X, None), params(n_components=2))
    assert missing.value.code == BLOCK_INPUT_REQUIREMENT_MISSING
    assert missing.value.params["requirement"] == "classes"

    with pytest.raises(BlockInputError) as one_class:
        PLSDA().fit(make_dataset(X, ["a"] * len(X)), params(n_components=2))
    assert one_class.value.code == BLOCK_CONSTANT_RESPONSE
    PLSDA.metadata()  # the block definition is valid


def test_olive_oil_cv_accuracy_meets_the_loose_published_floor() -> None:
    data = load_reference_dataset("olive_oil_ftir")
    assert data.groups is not None
    expected = load_expected("olive_oil_ftir_classification")["values"]
    full = SpectralDataset(
        data.spectra,
        Axis(data.axis, "cm-1"),
        signal_unit="absorbance",
        sample_ids=[str(s) for s in data.sample_ids],
        row_index=np.arange(120),
        source_id="olive_oil_ftir",
        group_ids=[str(g) for g in data.groups],
        classes=[str(c) for c in data.target],
        class_column="country",
    )
    oils = np.asarray(full.group_ids)
    correct = 0
    # Leave one oil out: both duplicate spectra of an oil leave training together.
    # shortcut: 16 LV fixed (leave-one-oil-out accuracy 0.87-0.93 for 4-20 LV), until T2 nested CV
    for oil in np.unique(oils):
        train = full.subset(np.flatnonzero(oils != oil))
        test = full.subset(np.flatnonzero(oils == oil))
        state = PLSDA().fit(train, params(n_components=16, n_components_mode="fixed"))
        table = PLSDA().apply(test, params(), state)
        correct += int((table["class_pred"] == np.asarray(test.classes)).sum())
    accuracy = correct / full.n_samples
    assert accuracy >= expected["cv_accuracy_min"], accuracy  # loose floor, protocol unverified
