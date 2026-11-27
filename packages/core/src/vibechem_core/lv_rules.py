# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/lv_rules.py
"""LV-number rules: choose a PLS latent-variable count from a CV curve (docs/METHODS.md#lv-rules).

Inputs are indexed by the LV count a = 0 ... A: the CV curve ``rmsecv[a]`` and ``press[a]``,
and ``fold_rmse[a, f]``, the RMSE of fold f (all folds of all repeats, the same folds for
every a). Candidates are a = 1 ... A (METHODS.md N17). Ported from pengoo
``select_n_components`` and ``_wold_r_criterion`` (TECH_STACK.md §11.2); the paired t-test's
alpha is a parameter here, and an unknown rule raises as in pengoo.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.stats import ttest_rel  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

type LVRule = Literal["global_min", "one_se", "ttest", "wold"]
LV_RULES: tuple[LVRule, ...] = ("global_min", "one_se", "ttest", "wold")


def fold_sd_se(fold_rmse: ArrayLike) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """SD (ddof 1) and SE = SD / sqrt(K) of the K fold RMSEs, one value per LV count."""
    folds = np.asarray(fold_rmse, dtype=np.float64)
    sd = folds.std(axis=1, ddof=1)
    return sd, sd / np.sqrt(folds.shape[1])


def select_lv(
    rule: str,
    rmsecv: ArrayLike,
    press: ArrayLike,
    fold_rmse: ArrayLike,
    *,
    alpha: float = 0.05,
    wold_threshold: float = 0.95,
) -> int:
    """The LV count (1 ... A) that ``rule`` chooses; see the module docstring."""
    if rule not in LV_RULES:
        raise ValueError(f"unknown LV rule {rule!r}; one of {LV_RULES}")
    curve = np.asarray(rmsecv, dtype=np.float64)
    sums = np.asarray(press, dtype=np.float64)
    folds = np.asarray(fold_rmse, dtype=np.float64)
    if curve.ndim != 1 or sums.shape != curve.shape or folds.ndim != 2 or len(folds) != len(curve):
        raise ValueError("rmsecv, press and fold_rmse need shapes (A + 1,), (A + 1,), (A + 1, K)")
    if curve.size < 2:
        raise ValueError("the curve needs at least one LV (a = 0 ... A with A >= 1)")
    if not (np.isfinite(curve).all() and np.isfinite(sums).all() and np.isfinite(folds).all()):
        raise ValueError("the CV curve must be finite")
    n_lv = curve.size - 1
    best = 1 + int(np.argmin(curve[1:]))  # argmin takes the first of equal values

    if rule == "global_min":
        return best
    if rule == "one_se":
        threshold = curve[best] + fold_sd_se(folds)[1][best]
        return 1 + int(np.flatnonzero(curve[1:] <= threshold)[0])
    if rule == "ttest":
        a = 1
        while a < n_lv:
            d = folds[a] - folds[a + 1]
            if d.size < 2:
                break
            if np.ptp(d) == 0.0:  # SD 0: t is infinite (p = 0) unless every difference is 0
                p = 0.0 if d[0] != 0.0 else 1.0
            else:
                p = float(ttest_rel(folds[a], folds[a + 1]).pvalue)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            if not (p < alpha and curve[a + 1] < curve[a]):
                break
            a += 1
        return a
    # wold: R(a) = PRESS(a) / PRESS(a - 1) from a = 2; stop before the first R >= threshold
    for a in range(2, n_lv + 1):
        if sums[a - 1] == 0.0 or sums[a] / sums[a - 1] >= wold_threshold:
            return a - 1
    return n_lv
