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
from vibechem_core.lv_rules import select_lv
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
    out = CrossValidation().apply(state, folds, parse_params(CVParams, values), runs(data, folds))
    return cast(Results, out["results"])


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


def test_model_output_predicts_like_a_fit_at_the_chosen_lv() -> None:
    data = dataset()
    folds = kfold(data)
    state = PLS().fit(data, parse_params(PLSParams, {"n_components": N_LV}))
    out = CrossValidation().apply(state, folds, parse_params(CVParams, {}), runs(data, folds))
    n_lv = int(cast(Results, out["results"]).metrics["n_lv"])
    sk: Any = PLSRegression(n_components=n_lv, scale=False, max_iter=10_000, tol=1e-20)
    expected = np.asarray(sk.fit(data.X, data.y).predict(data.X)).ravel()
    actual = PLS().apply(data, PLSParams(), cast(Any, out["model"]))["y_pred_y0"]
    np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-12)  # T-lib


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


def test_press_fold_spread_and_fold_mean_from_the_predictions() -> None:
    """Steps 3-4 recomputed with plain NumPy from the out-of-fold predictions at n_lv."""
    data = dataset()
    folds = RepeatedKFold().apply(
        data, parse_params(RepeatedKFoldParams, {"k": 3, "repeats": 2, "seed": 1})
    )
    result = cv(data, folds, aggregation="fold_mean")
    n_lv = int(result.metrics["n_lv"])
    p = cast(dict[str, NDArray[Any]], result.predictions)
    e = p["y_pred_y0"] - p["y_true_y0"]
    keys = sorted({(int(r), int(f)) for r, f in zip(p["repeat"], p["fold"], strict=True)})
    fold_rmse = np.array(
        [np.sqrt(np.mean(e[(p["repeat"] == r) & (p["fold"] == f)] ** 2)) for r, f in keys]
    )
    press = np.mean([np.sum(e[p["repeat"] == r] ** 2) for r in (0, 1)])
    fold_mean = np.mean(
        [fold_rmse[[i for i, k in enumerate(keys) if k[0] == r]].mean() for r in (0, 1)]
    )
    assert result.details["press"][n_lv] == pytest.approx(press, rel=1e-12)
    assert result.details["rmsecv"][n_lv] == pytest.approx(fold_mean, rel=1e-12)
    assert result.details["rmsecv_fold_sd"][n_lv] == pytest.approx(
        np.std(fold_rmse, ddof=1), rel=1e-12
    )
    assert result.details["rmsecv_fold_se"][n_lv] == pytest.approx(np.std(fold_rmse, ddof=1) / np.sqrt(6), rel=1e-12)  # fmt: skip


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


def test_haaland_thomas_and_van_der_voet_use_the_row_residuals_averaged_over_repeats() -> None:
    data = dataset()
    folds = RepeatedKFold().apply(
        data, parse_params(RepeatedKFoldParams, {"k": 3, "repeats": 2, "seed": 1})
    )
    # squared residual per row (sorted row_index) and LV count, mean over repeats, by scikit-learn
    order = {r: i for i, r in enumerate(sorted(data.row_index.tolist()))}
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    y = cast(NDArray[np.float64], data.y)[:, 0]
    rows = np.zeros((N_LV + 1, data.n_samples))
    for f in folds.folds:
        tr = [position[r] for r in f.train.tolist()]
        va = [position[r] for r in f.validation.tolist()]
        at = [order[r] for r in f.validation.tolist()]
        rows[0, at] += (y[va] - y[tr].mean()) ** 2 / 2
        for a in range(1, N_LV + 1):
            pls: Any = PLSRegression(n_components=a, scale=False)
            pls.fit(data.X[tr], y[tr])
            rows[a, at] += (pls.predict(data.X[va]).ravel() - y[va]) ** 2 / 2
    state = PLS().fit(data, parse_params(PLSParams, {"n_components": N_LV}))
    fold_runs = runs(data, folds)

    def seeded(seed: int | None) -> np.random.Generator | None:
        return None if seed is None else np.random.default_rng(seed)

    chosen: list[float] = []
    for values in (
        {"lv_rule": "haaland_thomas"},
        {"lv_rule": "van_der_voet"},
        {"lv_rule": "haaland_thomas", "f_alpha": 1e-6},
    ):
        rule = cast(str, values["lv_rule"])
        params = parse_params(CVParams, values)
        out = CrossValidation().apply(state, folds, params, fold_runs, rng=np.random.default_rng(5))
        result = cast(Results, out["results"])
        np.testing.assert_allclose(result.details["press"], rows.sum(axis=1), rtol=1e-10)  # T-lib
        expected = select_lv(
            rule, result.details["rmsecv"], rows.sum(axis=1), np.ones((N_LV + 1, 6)),
            row_sq_err=rows, rng=seeded(result.details["randomisation_seed"]),
            f_alpha=params.f_alpha, randomisation_alpha=params.randomisation_alpha,
        )  # fmt: skip
        assert result.metrics["n_lv"] == expected
        chosen.append(expected)
    assert chosen[2] < chosen[0]  # a looser test leaves a_min: the a < a_min branch runs


def test_pls2_is_not_supported_yet() -> None:
    data = dataset(k=2)
    with pytest.raises(BlockInputError) as err:
        cv(data, kfold(data))
    assert err.value.code == BLOCK_INPUT_REQUIREMENT_MISSING
