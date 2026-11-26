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

from vibechem_core.errors import ErrorParam, VibeChemWarning

METRIC_UNDEFINED = "METRIC_UNDEFINED"
METRIC_FEW_SAMPLES = "METRIC_FEW_SAMPLES"

type MetricSet = Literal["c", "cv", "p"]

# ISO 12099:2010: at least 20 validation samples for SEP, 10 for bias.
_ISO_MINIMUM = {"se": 20, "bias": 10}


def _names(set_: MetricSet) -> dict[str, str]:
    s = {"c": "c", "cv": "cv", "p": "p"}[set_]
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


def _warn(code: str, **params: ErrorParam) -> None:
    warnings.warn(VibeChemWarning(code, params), stacklevel=4)


def _pair(y: ArrayLike, y_pred: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    a = np.asarray(y, dtype=np.float64)
    b = np.asarray(y_pred, dtype=np.float64)
    if a.ndim != 1 or a.shape != b.shape:
        raise ValueError(f"y and y_pred need the same 1-D shape, got {a.shape} and {b.shape}")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise ValueError("y and y_pred must be finite")
    return a, b


def regression_metrics(y: ArrayLike, y_pred: ArrayLike, set_: MetricSet) -> dict[str, float]:
    """All regression metrics of one set (``c`` calibration, ``cv`` pooled CV, ``p`` test).

    For CV with ``fold_mean`` aggregation use :func:`cv_metrics`.
    """
    a, b = _pair(y, y_pred)
    return _regression(a, b, set_, float(np.sqrt(np.mean((b - a) ** 2))) if a.size else math.nan)


def _regression(
    y: NDArray[np.float64], y_pred: NDArray[np.float64], set_: MetricSet, rmse: float
) -> dict[str, float]:
    names = _names(set_)
    n = y.size
    e = y_pred - y
    bias = float(e.mean()) if n else math.nan
    m = {"rmse": rmse, "bias": bias}
    undefined: dict[str, str] = {}
    if n < 2:
        for key in ("se", "r2", "slope", "intercept", "rpd", "rpiq"):
            m[key] = math.nan
            undefined[key] = "n_lt_2"
    else:
        m["se"] = float(np.sqrt(np.sum((e - bias) ** 2) / (n - 1)))
        sst = float(np.sum((y - y.mean()) ** 2))
        sxx = float(np.sum((y_pred - y_pred.mean()) ** 2))
        if sst == 0.0:
            for key in ("r2", "rpd", "rpiq"):
                m[key] = math.nan
                undefined[key] = "constant_y"
        else:
            m["r2"] = 1.0 - float(np.sum(e**2)) / sst
        if sxx == 0.0:
            m["slope"] = m["intercept"] = math.nan
            undefined["slope"] = undefined["intercept"] = "constant_prediction"
        else:
            # Reference on prediction: y = intercept + slope * y_pred (ISO 12099 §5.4.1)
            m["slope"] = float(np.sum((y_pred - y_pred.mean()) * (y - y.mean()))) / sxx
            m["intercept"] = float(y.mean()) - m["slope"] * float(y_pred.mean())
        if sst > 0.0:
            q1, q3 = np.quantile(y, [0.25, 0.75])
            # RMSE 0 (perfect fit) gives inf, as pengoo
            with np.errstate(divide="ignore", invalid="ignore"):
                m["rpd"] = float(np.float64(np.std(y, ddof=1)) / np.float64(rmse))
                m["rpiq"] = float(np.float64(q3 - q1) / np.float64(rmse))
    m["rss"] = float(np.sum(e**2))
    for key, reason in undefined.items():
        _warn(METRIC_UNDEFINED, metric=names[key], reason=reason)
    if set_ != "c":
        for key, minimum in _ISO_MINIMUM.items():
            if n < minimum:
                _warn(METRIC_FEW_SAMPLES, metric=names[key], n=n, minimum=minimum)
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
        rmse = float(np.sqrt(np.mean((b - a) ** 2))) if a.size else math.nan
    elif aggregation == "fold_mean":
        rmse = float(per_fold.mean()) if per_fold.size else math.nan
    else:
        raise ValueError(f"unknown aggregation {aggregation!r}")
    return _regression(a, b, "cv", rmse)
