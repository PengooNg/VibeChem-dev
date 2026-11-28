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
from sklearn.metrics import accuracy_score, recall_score, roc_auc_score  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import parse_params
from vibechem_core.blocks.model.pls import PLS, PLSParams
from vibechem_core.blocks.model.plsda import PLSDA, PLSDAParams
from vibechem_core.blocks.validate.cv import (
    VALIDATION_CLASS_MISSING_IN_FOLD,
    VALIDATION_FOLDS_INVALID,
    VALIDATION_GROUPS_IGNORED,
    VALIDATION_Y_SCALES_DIFFER,
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


def sklearn_pls2_curve(
    data: SpectralDataset, folds: FoldSet, Y: NDArray[np.float64], scale: bool
) -> NDArray[np.float64]:
    """RMSECV = sqrt(PRESS / (n k)) for a = 1 ... N_LV, residuals divided by each fold's
    training Y SD when ``scale`` (the fitted space, N28); scikit-learn on positions."""
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    curve: list[float] = []
    for a in range(1, N_LV + 1):
        sse = 0.0
        for f in folds.folds:
            tr = [position[r] for r in f.train.tolist()]
            va = [position[r] for r in f.validation.tolist()]
            pls: Any = PLSRegression(n_components=a, scale=scale, max_iter=10_000, tol=1e-20)
            pred = np.asarray(pls.fit(data.X[tr], Y[tr]).predict(data.X[va]))
            sd = Y[tr].std(axis=0, ddof=1) if scale else np.ones(Y.shape[1])
            sse += float((((pred - Y[va]) / sd) ** 2).sum())
        curve.append(np.sqrt(sse / Y.size))
    return np.array(curve)


def pls_cv(data: SpectralDataset, scale: bool) -> Results:
    folds = kfold(data)
    params = parse_params(PLSParams, {"n_components": N_LV, "scale": scale})
    fold_runs = [FoldRun(f, PLS().fit(data.rows(f.train), params), data.rows(f.validation)) for f in folds.folds]  # fmt: skip
    out = CrossValidation().apply(PLS().fit(data, params), folds, parse_params(CVParams, {}), fold_runs)  # fmt: skip
    return cast(Results, out["results"])


@pytest.mark.parametrize("scale", [False, True])
def test_pls2_curve_sums_press_over_columns_in_the_fitted_space(scale: bool) -> None:
    data = dataset(k=2)
    Y = cast(NDArray[np.float64], data.y)
    result = pls_cv(data, scale)
    expected = sklearn_pls2_curve(data, kfold(data), Y, scale)
    np.testing.assert_allclose(
        result.details["rmsecv"][1:], expected, rtol=1e-6, atol=1e-9
    )  # T-iter
    n_lv = int(result.metrics["n_lv"])
    assert set(result.metrics) == {"rmsecv", "press", "n_lv"}
    assert result.metrics["press"] == pytest.approx(result.details["press"][n_lv])
    assert set(result.details["per_column"]) == {"y0", "y1"}
    assert result.y_unit == (None if scale else "%")
    preds = cast(Any, result.predictions)
    e1 = cast(NDArray[np.float64], preds["y_pred_y1"] - preds["y_true_y1"])
    rmse_y1 = float(np.sqrt(np.mean(e1**2)))  # original Y units
    assert result.details["per_column"]["y1"]["rmsecv"] == pytest.approx(rmse_y1)


def test_unscaled_pls2_with_very_different_y_variances_warns() -> None:
    base = dataset(k=2)
    Y = cast(NDArray[np.float64], base.y) * np.array([1.0, 10.0])  # variance ratio about 100
    data = SpectralDataset(
        base.X, base.axis, signal_unit="absorbance", sample_ids=base.sample_ids,
        row_index=base.row_index, source_id="ds", y=Y, y_columns=["y0", "y1"], y_units=["%", "%"],
    )  # fmt: skip
    found: dict[bool, list[dict[str, Any]]] = {}
    for scale in (False, True):
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            pls_cv(data, scale)
        found[scale] = [
            dict(w.message.params)
            for w in record
            if isinstance(w.message, VibeChemWarning)
            and w.message.code == VALIDATION_Y_SCALES_DIFFER
        ]
    assert found[True] == []
    assert len(found[False]) == 1
    assert found[False][0]["threshold"] == 10.0
    assert found[False][0]["ratio"] > 10.0


def classes_dataset(labels: list[str]) -> SpectralDataset:
    rng = np.random.default_rng(11)
    names = sorted(set(labels))
    centre = rng.normal(size=(len(names), 6))
    X = centre[[names.index(c) for c in labels]] + 0.8 * rng.normal(size=(len(labels), 6))
    return SpectralDataset(
        X, Axis(np.arange(6.0), "nm"), signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(len(labels))],
        row_index=np.arange(len(labels))[::-1] + 40, source_id="ds",
        classes=labels, class_column="type",
    )  # fmt: skip


def plsda_cv(data: SpectralDataset, folds: FoldSet, **values: Any) -> Results:
    params = parse_params(PLSDAParams, {"n_components": N_LV})
    fold_runs = [FoldRun(f, PLSDA().fit(data.rows(f.train), params), data.rows(f.validation)) for f in folds.folds]  # fmt: skip
    out = CrossValidation().apply(PLSDA().fit(data, params), folds, parse_params(CVParams, values), fold_runs)  # fmt: skip
    return cast(Results, out["results"])


def test_plsda_cv_matches_a_hand_written_scikit_learn_loop() -> None:
    labels = ["a", "b", "c"] * 8 + ["a", "c", "a"]  # 10, 8, 9; every fold has every class
    data = classes_dataset(labels)
    folds = kfold(data)
    result = plsda_cv(data, folds, micro_metrics=True)

    # Independent loop: indicator matrix, scikit-learn PLS per fold and LV count, argmax
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    names = np.array(["a", "b", "c"])
    truth = np.array(labels)
    Y = (truth[:, None] == names[None, :]).astype(float)
    oof = np.zeros((N_LV + 1, len(labels), 3))
    for f in folds.folds:
        tr = [position[r] for r in f.train.tolist()]
        va = [position[r] for r in f.validation.tolist()]
        oof[0][va] = Y[tr].mean(axis=0)
        for a in range(1, N_LV + 1):
            pls: Any = PLSRegression(n_components=a, scale=False, max_iter=10_000, tol=1e-20)
            oof[a][va] = pls.fit(data.X[tr], Y[tr]).predict(data.X[va])
    press = ((oof - Y[None]) ** 2).sum(axis=(1, 2))
    np.testing.assert_allclose(result.details["press"], press, rtol=1e-6, atol=1e-9)  # T-iter
    n_lv = int(result.metrics["n_lv"])
    assert n_lv == 1 + int(np.argmin(press[1:]))
    pred = names[oof[n_lv].argmax(axis=1)]
    error = [float((names[o.argmax(axis=1)] != truth).mean()) for o in oof]
    np.testing.assert_allclose(result.details["error_rate"], error)
    m = result.metrics
    s = oof[n_lv]
    recall, auc = cast(Any, recall_score), cast(Any, roc_auc_score)
    assert m["accuracy_cv"] == pytest.approx(accuracy_score(truth, pred))
    assert m["sensitivity_cv"] == pytest.approx(recall(truth, pred, average="macro"))
    assert m["sensitivity_w_cv"] == pytest.approx(recall(truth, pred, average="weighted"))
    assert m["auc_cv"] == pytest.approx(auc(truth, s, multi_class="ovr", average="macro"))
    assert m["auc_w_cv"] == pytest.approx(auc(truth, s, multi_class="ovr", average="weighted"))
    assert m["auc_micro_cv"] == pytest.approx(auc(Y, s, average="micro"))
    assert m["class_ratio_cv"] == pytest.approx(10 / 8)
    preds = cast(Any, result.predictions)
    order = [position[r] for r in preds["row_index"].tolist()]
    np.testing.assert_array_equal(preds["class_true"], truth[order])
    np.testing.assert_array_equal(preds["class_pred"], pred[order])
    np.testing.assert_allclose(preds["score_b"], s[order, 1], rtol=1e-6, atol=1e-9)
    assert result.y_unit is None
    assert set(result.details["per_class"]) == {"a", "b", "c"}


def test_class_missing_from_a_training_fold_warns_and_scores_zero() -> None:
    labels = ["a"] * 8 + ["b"] * 8 + ["c"] * 2  # contiguous 3-fold: one fold holds every c
    data = classes_dataset(labels)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        result = plsda_cv(data, kfold(data))
    found = [
        dict(w.message.params)
        for w in record
        if isinstance(w.message, VibeChemWarning)
        and w.message.code == VALIDATION_CLASS_MISSING_IN_FOLD
    ]
    assert found
    assert all(p["class"] == "c" for p in found)
    preds = cast(Any, result.predictions)
    assert (preds["score_c"][preds["class_true"] == "c"] == 0).all()
