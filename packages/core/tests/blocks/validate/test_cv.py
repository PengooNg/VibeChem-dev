# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/validate/test_cv.py
"""``validate.cv`` (docs/METHODS.md#cv) on fold models fitted by hand; the engine runner
that fits them per fold is tested in ``packages/engine/tests/runners/``."""

from __future__ import annotations

import warnings
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, parse_params
from vibechem_core.blocks.model.pls import PLS, PLSParams
from vibechem_core.blocks.validate.cv import (
    VALIDATION_FOLDS_INVALID,
    VALIDATION_GROUPS_IGNORED,
    CrossValidation,
    CVParams,
    FoldRun,
)
from vibechem_core.blocks.validate.folds import (
    KFold,
    RepeatedKFold,
    RepeatedKFoldParams,
    ShuffledFoldParams,
)
from vibechem_core.data import Axis, Fold, FoldSet, Results, SpectralDataset
from vibechem_core.errors import BlockInputError, VibeChemWarning
from vibechem_core.metrics import cv_metrics

N_LV = 4


def dataset(n: int = 24, k: int = 1, groups: list[str] | None = None) -> SpectralDataset:
    rng = np.random.default_rng(3)
    X = rng.normal(size=(n, 6))
    y = X[:, :2] @ rng.normal(size=(2, k)) + 0.3 * rng.normal(size=(n, k))
    return SpectralDataset(
        X,
        Axis(np.arange(6.0), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n)[::-1] + 40,  # offset and reversed
        source_id="ds",
        group_ids=groups,
        y=y,
        y_columns=[f"y{j}" for j in range(k)],
        y_units=["%"] * k,
    )


def runs(data: SpectralDataset, folds: FoldSet) -> list[FoldRun]:
    params = parse_params(PLSParams, {"n_components": N_LV})
    return [
        FoldRun(f, PLS().fit(data.rows(f.train), params), data.rows(f.validation))
        for f in folds.folds
    ]


def cv(data: SpectralDataset, folds: FoldSet, **values: Any) -> Results:
    state = PLS().fit(data, parse_params(PLSParams, {"n_components": N_LV}))
    return CrossValidation().apply(state, folds, parse_params(CVParams, values), runs(data, folds))


def kfold(data: SpectralDataset) -> FoldSet:
    return KFold().apply(data, parse_params(ShuffledFoldParams, {"k": 3, "shuffle": False}))


def sklearn_curve(data: SpectralDataset, folds: FoldSet) -> NDArray[np.float64]:
    """Pooled RMSECV for a = 1 ... N_LV with scikit-learn PLS on positions (independent)."""
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    y = cast(NDArray[np.float64], data.y)[:, 0]
    curve: list[float] = []
    for a in range(1, N_LV + 1):
        sse = 0.0
        for f in folds.folds:
            tr = [position[r] for r in f.train.tolist()]
            va = [position[r] for r in f.validation.tolist()]
            pls: Any = PLSRegression(n_components=a, scale=False)
            pls.fit(data.X[tr], y[tr])
            pred: NDArray[np.float64] = pls.predict(data.X[va]).ravel()
            sse += float(((pred - y[va]) ** 2).sum())
        curve.append(np.sqrt(sse / y.size))
    return np.array(curve)


def test_curve_matches_scikit_learn_and_metrics_are_at_the_chosen_lv() -> None:
    data = dataset()
    folds = kfold(data)
    result = cv(data, folds)
    np.testing.assert_allclose(
        result.details["rmsecv"][1:], sklearn_curve(data, folds), rtol=1e-10, atol=1e-12
    )  # T-lib
    n_lv = int(result.metrics["n_lv"])
    assert n_lv == 1 + int(np.argmin(result.details["rmsecv"][1:]))
    assert result.metrics["rmsecv"] == pytest.approx(result.details["rmsecv"][n_lv], rel=1e-12)
    assert result.predictions is not None
    assert sorted(result.predictions["row_index"].tolist()) == sorted(data.row_index.tolist())
    assert result.y_unit == "%"
    assert np.isnan(result.details["rmsecv_repeat_sd"])


def test_repeated_cv_averages_the_repeats() -> None:
    data = dataset()
    folds = RepeatedKFold().apply(
        data, parse_params(RepeatedKFoldParams, {"k": 3, "repeats": 2, "seed": 1})
    )
    result = cv(data, folds, lv_rule="one_se")
    n_lv = int(result.metrics["n_lv"])
    p = result.predictions
    assert p is not None
    per_repeat = [
        cv_metrics(
            p["y_true_y0"][p["repeat"] == r],
            p["y_pred_y0"][p["repeat"] == r],
            p["fold"][p["repeat"] == r],
        )
        for r in (0, 1)
    ]
    assert result.metrics["rmsecv"] == pytest.approx(
        np.mean([m["rmsecv"] for m in per_repeat]), rel=1e-12
    )
    assert result.details["rmsecv_repeat_sd"] == pytest.approx(
        np.std([m["rmsecv"] for m in per_repeat], ddof=1), rel=1e-12
    )
    assert len(result.details["rmsecv_fold_se"]) == N_LV + 1
    assert result.details["lv_rule"] == "one_se"
    assert 1 <= n_lv <= N_LV


def test_rows_predicted_twice_or_never_are_rejected() -> None:
    data = dataset()
    good = kfold(data).folds
    twice = FoldSet(
        "custom", "ds", 24, (*good, Fold(3, 0, good[0].train, good[0].validation)), True
    )
    with pytest.raises(BlockInputError) as err:
        cv(data, twice)
    assert err.value.code == VALIDATION_FOLDS_INVALID
    assert err.value.params == {"reason": "duplicate_prediction", "repeat": 0}
    never = FoldSet("custom", "ds", 24, good[:2], True)
    with pytest.raises(BlockInputError) as err:
        cv(data, never)
    assert err.value.params == {"reason": "missing_prediction", "repeat": 0}


def test_folds_that_ignore_groups_warn() -> None:
    data = dataset(groups=[f"g{i // 3}" for i in range(24)])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        cv(data, kfold(data))
    coded = [w.message for w in caught if isinstance(w.message, VibeChemWarning)]
    assert any(w.code == VALIDATION_GROUPS_IGNORED and w.params == {"n_groups": 8} for w in coded)


def test_pls2_is_not_supported_yet() -> None:
    data = dataset(k=2)
    with pytest.raises(BlockInputError) as err:
        cv(data, kfold(data))
    assert err.value.code == BLOCK_INPUT_REQUIREMENT_MISSING
