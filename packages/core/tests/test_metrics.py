# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_metrics.py
"""Tests for ``vibechem_core.metrics`` (docs/METHODS.md §8)."""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pytest
from sklearn.metrics import r2_score  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import parse_params
from vibechem_core.blocks.model.pls import PLS, PLSParams, predict_sweep
from vibechem_core.blocks.preprocess.scaling import Autoscale, ScalingParams
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import VibeChemWarning
from vibechem_core.metrics import (
    METRIC_CLASSES_SEVERELY_UNBALANCED,
    METRIC_FEW_SAMPLES,
    METRIC_UNDEFINED,
    accuracy,
    classification_metrics,
    confusion_matrix,
    cv_metrics,
    fold_rmse,
    regression_metrics,
    roc_auc,
    sensitivity,
    specificity,
)
from vibechem_core.reference_datasets import load_expected, load_reference_dataset
from vibechem_core.testing import assert_close, assert_reference


def exact(actual: Any, expected: Any, name: str) -> None:
    assert_close(actual, expected, rtol=1e-10, atol=1e-12, name=name)  # T-exact (METHODS §1)


def hand(method: str, dataset: str, actual: float, expected: float) -> None:
    assert_reference(method=method, dataset=dataset, actual=actual, expected=expected,
                     rtol=1e-10, atol=1e-12, source="hand calculation (METHODS.md §8)")  # fmt: skip


def codes(record: list[warnings.WarningMessage]) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for w in record:
        assert isinstance(w.message, VibeChemWarning), w.message
        out.append((w.message.code, dict(w.message.params)))
    return out


# 5-sample example, worked by hand: e = y_pred - y = [1, 0, 0, 1, 0].
Y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
Y_PRED = np.array([2.0, 2.0, 3.0, 5.0, 5.0])
HAND = {
    "rmse": math.sqrt(2 / 5),  # sqrt(sum e^2 / n)
    "bias": 2 / 5,  # mean e
    "se": math.sqrt(1.2 / 4),  # sum (e - 0.4)^2 = 3*0.16 + 2*0.36 = 1.2
    "r2": 1 - 2 / 10,  # SSE 2, sum (y - 3)^2 = 10
    "slope": 45 / 46,  # y on y_pred: Sxy = 9.0, Sxx = 9.2
    "intercept": -15 / 46,  # 3 - (45/46) * 3.4
    "rpd": math.sqrt(10 / 4) / math.sqrt(2 / 5),  # = 2.5
    "rpiq": (4 - 2) / math.sqrt(2 / 5),  # quartiles of 1..5 are 2 and 4
    "rss": 2.0,
}
NAMES = {
    "c": ["rmsec", "bias_c", "sec", "r2c", "slope_c", "intercept_c", "rpd_c", "rpiq_c", "rss_c"],
    "cv": [
        "rmsecv",
        "bias_cv",
        "secv",
        "r2cv",
        "slope_cv",
        "intercept_cv",
        "rpd_cv",
        "rpiq_cv",
        "press",
    ],
    "p": ["rmsep", "bias_p", "sep", "r2p", "slope_p", "intercept_p", "rpd_p", "rpiq_p", "rss_p"],
}


@pytest.mark.parametrize("set_", ["c", "cv", "p"])
def test_regression_metrics_match_hand_calculation(set_: str) -> None:
    with warnings.catch_warnings(record=True):  # few-samples warnings, tested below
        warnings.simplefilter("always")
        m = regression_metrics(Y, Y_PRED, set_)  # type: ignore[arg-type]
    assert list(m) == NAMES[set_]
    for name, key in zip(NAMES[set_], HAND, strict=True):
        hand(f"Metric {name}", "hand calculation, 5 samples", m[name], HAND[key])
    sklearn_r2: float = r2_score(Y, Y_PRED)  # pyright: ignore[reportUnknownVariableType]
    exact(m[NAMES[set_][3]], sklearn_r2, "r2 vs scikit-learn")  # T-lib check
    # Identity RMSE^2 = bias^2 + SE^2 (n - 1) / n
    exact(m[NAMES[set_][0]] ** 2, m[NAMES[set_][1]] ** 2 + m[NAMES[set_][2]] ** 2 * 4 / 5, "id")


def test_identity_holds_on_random_data() -> None:
    rng = np.random.default_rng(3)
    y = rng.normal(size=40)
    m = regression_metrics(y, y + rng.normal(0.3, 0.5, size=40), "c")
    exact(m["rmsec"] ** 2, m["bias_c"] ** 2 + m["sec"] ** 2 * 39 / 40, "identity")


def test_fold_mean_differs_from_pooled_with_unequal_folds() -> None:
    fold = np.array([0, 0, 0, 1, 1])  # e = [1, 0, 0 | 1, 0]
    exact(fold_rmse(Y, Y_PRED, fold), [math.sqrt(1 / 3), math.sqrt(1 / 2)], "fold RMSE")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        pooled = cv_metrics(Y, Y_PRED, fold)
        mean = cv_metrics(Y, Y_PRED, fold, aggregation="fold_mean")
    exact(pooled["rmsecv"], math.sqrt(2 / 5), "pooled")
    rmsecv = (math.sqrt(1 / 3) + math.sqrt(1 / 2)) / 2
    exact(mean["rmsecv"], rmsecv, "fold_mean")
    exact(mean["rpd_cv"], math.sqrt(10 / 4) / rmsecv, "RPDcv divides by the reported RMSECV")
    exact(mean["rpiq_cv"], 2 / rmsecv, "RPIQcv divides by the reported RMSECV")
    for name in ("bias_cv", "secv", "r2cv", "slope_cv", "intercept_cv", "press"):
        exact(mean[name], pooled[name], f"{name} from pooled predictions")


def test_edge_cases_give_nan_with_coded_warnings() -> None:
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        m = regression_metrics(np.array([1.0]), np.array([1.5]), "c")
    exact(m["rmsec"], 0.5, "one sample RMSE")
    for name in ("sec", "r2c", "slope_c", "intercept_c", "rpd_c", "rpiq_c"):
        assert math.isnan(m[name]), name
    assert (METRIC_UNDEFINED, {"metric": "sec", "reason": "n_lt_2"}) in codes(record)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        m = regression_metrics(np.full(4, 2.0), np.array([1.0, 2.0, 3.0, 2.5]), "c")
    for name in ("r2c", "rpd_c", "rpiq_c"):
        assert math.isnan(m[name]), name
    assert (METRIC_UNDEFINED, {"metric": "r2c", "reason": "constant_y"}) in codes(record)

    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        regression_metrics(Y, Y_PRED, "c")
    assert record == []  # ISO 12099 sample counts concern validation sets only
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        regression_metrics(Y, Y_PRED, "p")
    assert codes(record) == [
        (METRIC_FEW_SAMPLES, {"metric": "sep", "n": 5, "minimum": 20}),
        (METRIC_FEW_SAMPLES, {"metric": "bias_p", "n": 5, "minimum": 10}),
    ]

    with pytest.raises(ValueError, match="shape"):
        regression_metrics(Y, Y_PRED[:4], "c")
    with pytest.raises(ValueError, match="finite"):
        regression_metrics(Y, np.array([1.0, np.nan, 3.0, 4.0, 5.0]), "c")


def test_gasoline_loo_rmsecv_in_original_units_matches_published() -> None:
    # Each LOO fold scales y on its own training rows (y_transform); PLS maps the
    # predictions back, so the pooled RMSECV is in octane numbers (Mevik & Wehrens 2007).
    data = load_reference_dataset("gasoline_nir")
    expected = load_expected("gasoline_nir_pls")
    full = SpectralDataset(
        data.spectra[:50],
        Axis(data.axis, "nm"),
        signal_unit="absorbance",
        sample_ids=[str(s) for s in data.sample_ids[:50]],
        row_index=np.arange(50),
        source_id="gasoline_nir",
        y=data.target[:50].astype(np.float64)[:, None],
        y_columns=["octane"],
        y_units=["octane number"],
    )
    y_params = parse_params(ScalingParams, {"target": "y"})
    pls_params = parse_params(PLSParams, {"n_components": 10})
    sweep = np.empty((11, 50))
    for i in range(50):
        train = full.subset(np.delete(np.arange(50), i))
        y_state = Autoscale().fit(train, y_params)
        scaled = Autoscale().apply(train, y_params, y_state)
        state = PLS().fit(scaled, pls_params, y_transform=y_state)
        sweep[:, i] = predict_sweep(state, full.subset(np.array([i])))[:, 0, 0]
    assert full.y is not None
    y = full.y[:, 0]
    for a in range(1, 11):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            m = cv_metrics(y, sweep[a], np.arange(50))
            mae = cv_metrics(y, sweep[a], np.arange(50), aggregation="fold_mean")["rmsecv"]
        assert_reference(method="RMSECV (LOO, pooled)", dataset=f"gasoline_nir, {a} LV",
                         actual=m["rmsecv"], expected=expected["values"]["rmsep_cv"][a],
                         rtol=expected["tolerance"]["rtol"], atol=0.0,
                         source="Mevik & Wehrens 2007, testdata/expected/gasoline_nir_pls.json")  # fmt: skip
        exact(mae, float(np.abs(sweep[a] - y).mean()), "LOO fold_mean = mean absolute error")


# 3-class example, worked by hand: rows true, columns predicted, classes a < b < c.
TRUE = np.array(["a", "a", "a", "b", "b", "c", "c", "c"])
PRED = np.array(["a", "a", "b", "b", "c", "c", "c", "a"])


def test_classification_metrics_match_hand_calculation() -> None:
    C = confusion_matrix(TRUE, PRED, ["a", "b", "c"])
    np.testing.assert_array_equal(C, [[2, 1, 0], [0, 1, 1], [1, 0, 2]])
    hand("Metric accuracy", "hand calculation, 3 classes", accuracy(C), 5 / 8)
    exact(sensitivity(C, ["a", "b", "c"]), [2 / 3, 1 / 2, 2 / 3], "sensitivity")
    # Specificity of a: rows b, c (5 samples), predicted not a: 2 + 2
    exact(specificity(C, ["a", "b", "c"]), [4 / 5, 5 / 6, 4 / 5], "specificity")


def test_classification_set_metrics_match_hand_calculation() -> None:
    # TRUE/PRED above, scores = one-hot of PRED. Class counts 3, 2, 3 (weights 3/8, 2/8, 3/8).
    # One-vs-rest AUC by pair counting (ties 1/2): a 11/15, b 8/12, c 11/15. Micro: 8 pooled
    # positives (5 scored 1) vs 16 negatives (3 scored 1): (5*13 + 5*3/2 + 3*13/2) / 128.
    classes = ["a", "b", "c"]
    scores = (PRED[:, None] == np.array(classes)[None, :]).astype(float)
    m, per_class = classification_metrics(TRUE, PRED, scores, classes, "cv", micro=True)
    auc, w = np.array([11 / 15, 8 / 12, 11 / 15]), np.array([3, 2, 3]) / 8
    sens, spec = np.array([2 / 3, 1 / 2, 2 / 3]), np.array([4 / 5, 5 / 6, 4 / 5])
    expected = {
        "accuracy_cv": 5 / 8,
        "sensitivity_cv": sens.mean(),
        "specificity_cv": spec.mean(),
        "auc_cv": auc.mean(),
        "sensitivity_w_cv": 5 / 8,  # = accuracy (N22 identity)
        "specificity_w_cv": float(w @ spec),
        "auc_w_cv": float(w @ auc),
        "class_ratio_cv": 1.5,
        "sensitivity_micro_cv": 5 / 8,
        "specificity_micro_cv": 13 / 16,
        "auc_micro_cv": 92 / 128,
    }
    assert list(m) == list(expected)
    for name, value in expected.items():
        hand(f"Metric {name}", "hand calculation, 3 classes", m[name], value)
    assert per_class["b"] == {"sensitivity": 0.5, "specificity": pytest.approx(5 / 6)}
    assert "auc_micro_cv" not in classification_metrics(TRUE, PRED, scores, classes, "cv")[0]

    # Binary: the class-2 AUC for both classes; class ratio 21 > 20 warns, 20 does not.
    true = np.array(["n"] * 21 + ["p"])
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        m, _ = classification_metrics(
            true, true, np.eye(2)[(true == "p").astype(int)], ["n", "p"], "p"
        )
        classification_metrics(
            true[1:], true[1:], np.eye(2)[(true[1:] == "p").astype(int)], ["n", "p"], "p"
        )
    assert m["auc_p"] == m["auc_w_p"] == 1.0

    # A class absent from the set has weight 0: weighted means stay defined (macro is NaN)
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        m, _ = classification_metrics(TRUE[:5], PRED[:5], scores[:5], classes, "p")
    assert m["sensitivity_w_p"] == pytest.approx(m["accuracy_p"])
    assert math.isnan(m["sensitivity_p"])
    assert m["class_ratio_p"] == math.inf
    assert codes(record) == [
        (METRIC_CLASSES_SEVERELY_UNBALANCED, {"ratio": 21.0, "threshold": 20.0, "set": "p"})
    ]


def test_roc_auc_matches_pair_counting() -> None:
    # Positives 0.35, 1.3, 0.4 vs negatives -0.2, 0.4: 4 pairs right, one tie (1/2) of 6.
    # PLS-DA scores outside [0, 1] are accepted.
    scores = np.array([[0, -0.2], [0, 0.4], [0, 0.35], [0, 1.3], [0, 0.4]])
    auc = roc_auc(np.array([0, 0, 1, 1, 1]), scores, [0, 1])
    hand("Metric ROC-AUC (binary)", "pair counting, 5 samples", auc, 4.5 / 6)

    # One-vs-rest per class: a 7/8, b 7.5/8 (one tie), c 7/8; macro mean.
    true = np.array(["a", "a", "b", "b", "c", "c"])
    scores = np.array([[0.9, 0.6, 0.7, 0.1, 0.2, 0.3],
                       [0.1, 0.2, 0.8, 0.5, 0.5, 0.0],
                       [0.0, 0.2, -0.5, 0.4, 0.3, 0.7]]).T  # fmt: skip
    auc = roc_auc(true, scores, ["a", "b", "c"])
    hand("Metric ROC-AUC (macro one-vs-rest)", "pair counting, 3 classes", auc, (7 + 7.5 + 7) / 24)


def test_absent_class_gives_nan_with_coded_warnings() -> None:
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        C = confusion_matrix(np.array(["a", "a", "b"]), np.array(["a", "b", "b"]), ["a", "b", "c"])
        assert math.isnan(sensitivity(C, ["a", "b", "c"])[2])
        auc = roc_auc(np.array(["a", "a", "b"]), np.eye(3)[[0, 1, 1]], ["a", "b", "c"])
    assert math.isnan(auc)
    assert codes(record) == [
        (METRIC_UNDEFINED, {"metric": "sensitivity", "class": "c", "reason": "class_absent"}),
        (METRIC_UNDEFINED, {"metric": "auc", "class": "c", "reason": "class_absent"}),
    ]


def test_review_regressions() -> None:
    # y constant up to rounding: sum (y - mean)^2 is 6e-34, not 0, but y is constant.
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        m = regression_metrics(np.full(3, 0.1), np.array([0.1, 0.2, 0.3]), "c")
        flat = regression_metrics(np.array([1.0, 2.0, 3.0]), np.full(3, 0.1), "c")
        perfect = regression_metrics(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]), "c")
    for name in ("r2c", "rpd_c", "rpiq_c"):
        assert math.isnan(m[name]), name
    assert math.isnan(flat["slope_c"])
    assert math.isnan(perfect["rpd_c"])
    assert math.isnan(perfect["rpiq_c"])
    assert (METRIC_UNDEFINED, {"metric": "rpd_c", "reason": "zero_rmse"}) in codes(record)

    # Linear-interpolation quartiles (NumPy default): 1..6 -> Q1 2.25, Q3 4.75.
    y = np.arange(1.0, 7.0)
    m = regression_metrics(y, y + np.array([1.0, 0, 0, 0, 0, 0]), "c")
    hand("Metric rpiq_c", "hand calculation, 6 samples", m["rpiq_c"], 2.5 / math.sqrt(1 / 6))

    with pytest.raises(ValueError, match="empty"):
        regression_metrics(np.array([]), np.array([]), "c")
    with pytest.raises(ValueError, match="not in classes"):
        confusion_matrix(np.array(["a", "b", "x"]), np.array(["a", "b", "a"]), ["a", "b"])
    with pytest.raises(ValueError, match="not in classes"):
        roc_auc(np.array(["a", "b", "x"]), np.eye(2)[[0, 1, 0]], ["a", "b"])
