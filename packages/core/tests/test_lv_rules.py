# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_lv_rules.py
"""LV-number rules (docs/METHODS.md#lv-rules): hand-built curves, each decision worked out."""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy.stats import ttest_rel  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.lv_rules import fold_sd_se, select_lv

FLAT = np.ones((5, 4))  # fold RMSEs the rule under test does not use


def test_global_min_takes_the_smallest_lv_of_a_tie_and_never_zero() -> None:
    assert select_lv("global_min", [5, 3, 2, 2, 2.5], np.zeros(5), FLAT) == 2
    # a = 0 is not a candidate
    assert select_lv("global_min", [1, 3, 2, 2, 2.5], np.zeros(5), FLAT) == 2


def test_one_se_takes_the_smallest_lv_within_one_se_of_the_minimum() -> None:
    folds = np.ones((5, 4))
    folds[3] = [1.8, 2.2, 1.6, 2.4]  # minimum at a = 3: SD = sqrt(0.4 / 3), SE = SD / 2 = 0.18257
    sd, se = fold_sd_se(folds)
    assert sd[3] == pytest.approx(np.sqrt(0.4 / 3), rel=1e-12)
    assert se[3] == pytest.approx(np.sqrt(0.4 / 3) / 2, rel=1e-12)
    # threshold 2.0 + 0.18257 = 2.18257: a = 2 (2.1) is inside, a = 1 (3.0) is not
    assert select_lv("one_se", [5, 3.0, 2.1, 2.0, 2.05], np.zeros(5), folds) == 2


def _ttest_folds() -> NDArray[np.float64]:
    return np.array(
        [
            [5.0, 5.0, 5.0, 5.0],
            [3.0, 3.2, 2.9, 3.1],
            # a1 - a2 = [1, 1.1, 1, 0.9]: t = 1 / (0.08165 / 2) = 24.5, p = 1.5e-4
            [2.0, 2.1, 1.9, 2.2],
            [2.05, 2.0, 1.95, 2.15],  # a2 - a3 = [-0.05, 0.1, -0.05, 0.05]: not significant
        ]
    )


def test_ttest_steps_forward_while_the_next_lv_is_significantly_better() -> None:
    rmsecv = [5.0, 3.05, 2.05, 2.04]
    assert select_lv("ttest", rmsecv, np.zeros(4), _ttest_folds()) == 2
    assert select_lv("ttest", rmsecv, np.zeros(4), _ttest_folds(), alpha=1e-5) == 1
    # significant but RMSECV does not fall: no step
    assert select_lv("ttest", [5.0, 2.0, 2.05, 2.04], np.zeros(4), _ttest_folds()) == 1
    # equal fold errors: p undefined, not significant; a constant non-zero gain: p = 0
    assert select_lv("ttest", rmsecv, np.zeros(4), np.ones((4, 4))) == 1
    assert select_lv("ttest", [5.0, 3.0, 2.0], np.zeros(3), [[5.0] * 4, [3.0] * 4, [2.0] * 4]) == 2
    # the hand t statistic of the comment (T-exact) is what SciPy tests
    folds = _ttest_folds()
    t = float(ttest_rel(folds[1], folds[2]).statistic)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
    assert t == pytest.approx(1.0 / (np.sqrt(0.02 / 3) / 2), rel=1e-12)


def test_wold_stops_before_the_first_ratio_at_or_above_the_threshold() -> None:
    folds = np.ones((5, 4))
    # R(3) = 29/30 >= 0.95
    assert select_lv("wold", np.ones(5), [100, 40, 30, 29, 28.5], folds) == 2
    assert select_lv("wold", np.ones(4), [100, 50, 25, 12], folds[:4]) == 3  # every ratio < 0.95
    assert select_lv("wold", np.ones(3), [10, 0, 0], folds[:3]) == 1  # PRESS(1) = 0
    assert select_lv("wold", np.ones(5), [100, 40, 30, 29, 28.5], folds, wold_threshold=0.7) == 1


def test_bad_inputs_raise() -> None:
    with pytest.raises(ValueError, match="unknown LV rule"):
        select_lv("1se", [2, 1], [2, 1], np.ones((2, 3)))
    with pytest.raises(ValueError, match="at least one LV"):
        select_lv("global_min", [2], [2], np.ones((1, 3)))
    with pytest.raises(ValueError, match="finite"):
        select_lv("global_min", [2, np.nan], [2, 1], np.ones((2, 3)))
    with pytest.raises(ValueError, match="shape"):
        select_lv("global_min", [2, 1], [2, 1], np.ones((3, 3)))
