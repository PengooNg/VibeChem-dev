# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/metrics.py
"""Regression and classification metrics (docs/METHODS.md §8).

Inputs are predictions and reference values **in original Y units**: ``model.pls`` maps
every prediction back through its ``y_transform`` (METHODS.md#pls), so nothing here
converts units. One Y column per call; PLS2 callers loop over the columns.

Result names are the ``Results.metrics`` names of METHODS.md §8 (``rmsecv``, ``bias_p``,
``press`` ...). A metric that is undefined for the data (fewer than 2 samples, constant
y, a class absent from the set) is NaN with a ``METRIC_UNDEFINED`` warning; metrics are
reported, not block inputs, so nothing raises for them. Definitions ported from pengoo
``regression_metrics`` and its ``pooled``/``fold_mean`` RMSECV aggregation (TECH_STACK.md
§11.2), plus RPIQ and slope/intercept; reference values in the tests are hand-computed.
"""

from __future__ import annotations

import math
import warnings
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from sklearn.metrics import confusion_matrix as sk_confusion_matrix  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.metrics import roc_auc_score  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.errors import ErrorParam, VibeChemWarning

METRIC_UNDEFINED = "METRIC_UNDEFINED"
METRIC_FEW_SAMPLES = "METRIC_FEW_SAMPLES"
METRIC_CLASSES_SEVERELY_UNBALANCED = "METRIC_CLASSES_SEVERELY_UNBALANCED"

type MetricSet = Literal["c", "cv", "p"]

# ISO 12099:2010: at least 20 validation samples for SEP, 10 for bias.
_ISO_MINIMUM = {"se": 20, "bias": 10}


def _names(set_: MetricSet) -> dict[str, str]:
    s = set_
    return {
        "rmse": f"rmse{s}",
        "bias": f"bias_{s}",
        "se": f"se{s}",
        "r2": f"r2{s}",
        "slope": f"slope_{s}",
        "intercept": f"intercept_{s}",
        "rpd": f"rpd_{s}",
        "rpiq": f"rpiq_{s}",
        "rss": {"c": "rss_c", "cv": "press", "p": "rss_p"}[set_],
    }


def _warn(code: str, params: dict[str, ErrorParam], stacklevel: int = 4) -> None:
    warnings.warn(VibeChemWarning(code, params), stacklevel=stacklevel)


def _pair(y: ArrayLike, y_pred: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    a = np.asarray(y, dtype=np.float64)
    b = np.asarray(y_pred, dtype=np.float64)
    if a.ndim != 1 or a.shape != b.shape:
        raise ValueError(f"y and y_pred need the same 1-D shape, got {a.shape} and {b.shape}")
    if a.size == 0:
        raise ValueError("y and y_pred are empty")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("y and y_pred must be finite")
    return a, b


def regression_metrics(y: ArrayLike, y_pred: ArrayLike, set_: MetricSet) -> dict[str, float]:
    """All regression metrics of one set (``c`` calibration, ``cv`` pooled CV, ``p`` test).

    For CV with ``fold_mean`` aggregation use :func:`cv_metrics`.
    """
    a, b = _pair(y, y_pred)
    return _regression(a, b, set_, float(np.sqrt(np.mean((b - a) ** 2))))


def _regression(
    y: NDArray[np.float64], y_pred: NDArray[np.float64], set_: MetricSet, rmse: float
) -> dict[str, float]:
    names = _names(set_)
    n = y.size
    e = y_pred - y
    bias = float(e.mean())
    m = {"rmse": rmse, "bias": bias}
    undefined: dict[str, str] = {}
    if n < 2:
        for key in ("se", "r2", "slope", "intercept", "rpd", "rpiq"):
            m[key] = math.nan
            undefined[key] = "n_lt_2"
    else:
        m["se"] = float(np.sqrt(np.sum((e - bias) ** 2) / (n - 1)))
        # Constant means equal values: the sums of squares keep rounding noise (6e-34 for 0.1s)
        if np.ptp(y) == 0.0:
            for key in ("r2", "rpd", "rpiq"):
                m[key] = math.nan
                undefined[key] = "constant_y"
        else:
            m["r2"] = 1.0 - float(np.sum(e**2)) / float(np.sum((y - y.mean()) ** 2))
            if rmse == 0.0:
                m["rpd"] = m["rpiq"] = math.nan
                undefined["rpd"] = undefined["rpiq"] = "zero_rmse"
            else:
                q1, q3 = np.quantile(y, [0.25, 0.75])
                m["rpd"] = float(np.std(y, ddof=1)) / rmse
                m["rpiq"] = float(q3 - q1) / rmse
        if np.ptp(y_pred) == 0.0:
            m["slope"] = m["intercept"] = math.nan
            undefined["slope"] = undefined["intercept"] = "constant_prediction"
        else:
            # Reference on prediction: y = intercept + slope * y_pred (ISO 12099 §5.4.1)
            dp = y_pred - y_pred.mean()
            m["slope"] = float(np.sum(dp * (y - y.mean()))) / float(np.sum(dp**2))
            m["intercept"] = float(y.mean()) - m["slope"] * float(y_pred.mean())
    m["rss"] = float(np.sum(e**2))
    for key, reason in undefined.items():
        _warn(METRIC_UNDEFINED, {"metric": names[key], "reason": reason})
    if set_ != "c":
        for key, minimum in _ISO_MINIMUM.items():
            if n < minimum:
                _warn(METRIC_FEW_SAMPLES, {"metric": names[key], "n": n, "minimum": minimum})
    return {names[key]: m[key] for key in names}


def fold_rmse(y: ArrayLike, y_pred: ArrayLike, fold: ArrayLike) -> NDArray[np.float64]:
    """RMSE of each fold's out-of-fold predictions, folds in sorted label order."""
    a, b = _pair(y, y_pred)
    labels = np.asarray(fold)
    if labels.shape != a.shape:
        raise ValueError(f"fold needs shape {a.shape}, got {labels.shape}")
    inverse = np.unique(labels, return_inverse=True)[1]
    sse = np.bincount(inverse, weights=(b - a) ** 2)
    return np.sqrt(sse / np.bincount(inverse))


def cv_metrics(
    y: ArrayLike,
    y_pred: ArrayLike,
    fold: ArrayLike,
    aggregation: Literal["pooled", "fold_mean"] = "pooled",
) -> dict[str, float]:
    """CV metrics from out-of-fold predictions of one repeat (METHODS.md#rmsecv).

    ``pooled``: RMSECV = sqrt(PRESS / n). ``fold_mean``: the mean of the per-fold RMSEs.
    Every other metric uses the pooled predictions; RPDcv and RPIQcv divide by the
    reported RMSECV.
    """
    a, b = _pair(y, y_pred)
    per_fold = fold_rmse(a, b, fold)
    if aggregation == "pooled":
        rmse = float(np.sqrt(np.mean((b - a) ** 2)))
    elif aggregation == "fold_mean":
        rmse = float(per_fold.mean())
    else:
        raise ValueError(f"unknown aggregation {aggregation!r}")
    return _regression(a, b, "cv", rmse)


def _check_labels(classes: ArrayLike, *labels: ArrayLike) -> None:
    # scikit-learn's labels= would silently drop such samples
    unknown = set(np.concatenate([np.asarray(x).ravel() for x in labels]).tolist()) - set(
        np.asarray(classes).tolist()
    )
    if unknown:
        raise ValueError(f"labels not in classes: {sorted(map(str, unknown))}")


def confusion_matrix(y_true: ArrayLike, y_pred: ArrayLike, classes: ArrayLike) -> NDArray[np.int64]:
    """C[t, p] = samples of true class t predicted as p, in the order of ``classes``."""
    _check_labels(classes, y_true, y_pred)
    C: NDArray[np.int64] = sk_confusion_matrix(y_true, y_pred, labels=classes)  # pyright: ignore[reportUnknownVariableType]
    return C


def accuracy(C: NDArray[np.int64]) -> float:
    """Fraction of samples on the diagonal of the confusion matrix."""
    return float(np.trace(C) / C.sum())


def _per_class(
    num: NDArray[np.int64], den: NDArray[np.int64], classes: ArrayLike, metric: str, reason: str
) -> NDArray[np.float64]:
    labels = np.asarray(classes)
    for g in np.flatnonzero(den == 0):
        _warn(METRIC_UNDEFINED, {"metric": metric, "reason": reason, "class": str(labels[g])})
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / np.maximum(den, 1), np.nan)


def sensitivity(C: NDArray[np.int64], classes: ArrayLike) -> NDArray[np.float64]:
    """Per class: correctly predicted / samples of that class (NaN if the class is absent)."""
    return _per_class(np.diag(C), C.sum(axis=1), classes, "sensitivity", "class_absent")


def specificity(C: NDArray[np.int64], classes: ArrayLike) -> NDArray[np.float64]:
    """Per class g: samples of other classes not predicted as g / samples of other classes."""
    others = C.sum() - C.sum(axis=1)
    not_predicted_g = others - (C.sum(axis=0) - np.diag(C))
    return _per_class(not_predicted_g, others, classes, "specificity", "only_class")


def roc_auc(y_true: ArrayLike, scores: ArrayLike, classes: ArrayLike) -> float:
    """ROC-AUC of the predicted values (``scores``: one column per class, ``classes`` order).

    Binary: AUC of the second class's column. More classes: one-vs-rest AUC of each
    class's column, then the unweighted mean (NaN if any class's AUC is undefined).
    """
    return float(np.mean(_auc_per_class(y_true, scores, classes, 4)))


def _auc_per_class(
    y_true: ArrayLike, scores: ArrayLike, classes: ArrayLike, stacklevel: int
) -> NDArray[np.float64]:
    """One-vs-rest AUC per class; binary: the second class's AUC for both classes
    (class 1 against class 2 on -score_2 is the same ROC)."""
    _check_labels(classes, y_true)
    labels = np.asarray(classes)
    truth = np.asarray(y_true)
    s = np.asarray(scores, dtype=np.float64)
    if s.shape != (truth.size, labels.size):
        raise ValueError(f"scores need shape {(truth.size, labels.size)}, got {s.shape}")
    aucs: list[float] = []
    for g in [1] if labels.size == 2 else range(labels.size):
        positive = truth == labels[g]
        if positive.all() or not positive.any():
            reason = "only_class" if positive.all() else "class_absent"
            _warn(
                METRIC_UNDEFINED,
                {"metric": "auc", "reason": reason, "class": str(labels[g])},
                stacklevel,
            )
            aucs.append(math.nan)
        else:
            aucs.append(float(roc_auc_score(positive, s[:, g])))  # pyright: ignore[reportUnknownArgumentType]
    return np.array(aucs * 2 if labels.size == 2 else aucs)


def classification_metrics(
    y_true: ArrayLike,
    y_pred: ArrayLike,
    scores: ArrayLike,
    classes: ArrayLike,
    set_: MetricSet,
    *,
    micro: bool = False,
    severe_imbalance_ratio: float | None = 20.0,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """``Results.metrics`` names of one classification set (METHODS.md N22, N27) and the
    per-class sensitivity and specificity (``details.per_class``).

    Macro (unweighted) and weighted (n_g / n) means always, ``accuracy`` and
    ``class_ratio``; micro means only with ``micro``. ``class_ratio`` above
    ``severe_imbalance_ratio`` warns ``METRIC_CLASSES_SEVERELY_UNBALANCED`` (None: no check).
    """
    labels = np.asarray(classes)
    truth = np.asarray(y_true)
    C = confusion_matrix(truth, y_pred, labels)
    sens, spec = sensitivity(C, labels), specificity(C, labels)
    auc = _auc_per_class(truth, scores, labels, 4)
    n_g = C.sum(axis=1)
    w = n_g / n_g.sum()
    ratio = float(n_g.max() / n_g.min()) if n_g.min() > 0 else math.inf
    s = set_
    m = {
        f"accuracy_{s}": accuracy(C),
        f"sensitivity_{s}": float(sens.mean()),
        f"specificity_{s}": float(spec.mean()),
        f"auc_{s}": float(auc.mean()),
        f"sensitivity_w_{s}": float(w @ sens),
        f"specificity_w_{s}": float(w @ spec),
        f"auc_w_{s}": float(w @ auc),
        f"class_ratio_{s}": ratio,
    }
    if micro:
        others = C.sum() - n_g
        true_negative = others - (C.sum(axis=0) - np.diag(C))
        onehot = truth[:, None] == labels[None, :]
        m[f"sensitivity_micro_{s}"] = float(np.trace(C) / C.sum())
        m[f"specificity_micro_{s}"] = float(true_negative.sum() / others.sum())
        m[f"auc_micro_{s}"] = float(roc_auc_score(onehot.ravel(), np.asarray(scores, dtype=np.float64).ravel()))  # pyright: ignore[reportUnknownArgumentType]  # fmt: skip
    if severe_imbalance_ratio is not None and ratio > severe_imbalance_ratio:
        _warn(
            METRIC_CLASSES_SEVERELY_UNBALANCED,
            {"ratio": ratio, "threshold": severe_imbalance_ratio, "set": set_},
            3,
        )
    per_class = {
        str(c): {"sensitivity": float(sens[g]), "specificity": float(spec[g])}
        for g, c in enumerate(labels)
    }
    return m, per_class
