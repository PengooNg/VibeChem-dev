# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_lv_rules.py
"""LV-number rules (docs/METHODS.md#lv-rules): hand-built curves, each decision worked out."""

from __future__ import annotations

import itertools

import numpy as np
import pytest
from numpy.typing import NDArray
from scipy.stats import ttest_rel  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.lv_rules import fold_sd_se, randomisation_p, select_lv

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


def test_haaland_thomas_takes_the_fewest_lvs_whose_press_ratio_is_not_significant() -> None:
    # n = 2 rows: P(F(2, 2) >= x) = 1 / (1 + x) in closed form (T-exact)
    rows = np.ones((5, 2))
    press = [10, 4, 1.5, 1.0, 1.2]  # a_min = 3; p(1) = 1/5, p(2) = 1/2.5, p(3) = 1/2
    assert select_lv("haaland_thomas", np.ones(5), press, FLAT, row_sq_err=rows) == 2
    assert select_lv("haaland_thomas", np.ones(5), press, FLAT, row_sq_err=rows, f_alpha=0.1) == 1
    assert select_lv("haaland_thomas", np.ones(5), press, FLAT, row_sq_err=rows, f_alpha=0.45) == 3
    assert select_lv("haaland_thomas", np.ones(3), [3, 0, 0], FLAT[:3], row_sq_err=rows[:3]) == 1


def test_randomisation_p_matches_the_exact_sign_flip_p() -> None:
    d = np.array([0.9, 1.4, -0.3, 0.6, 2.0, -0.8, 0.5, 1.1, -0.2, 0.7])
    # exact p over all 2^10 sign vectors (the identity included), independent of our code
    t = d.mean()
    flips = [np.mean(d * np.array(s)) >= t - 1e-12 for s in itertools.product((-1, 1), repeat=10)]
    exact = float(np.mean(flips))
    b = 4000
    p = randomisation_p(d, b, np.random.default_rng(0))
    assert abs(p - exact) <= 4 * np.sqrt(exact * (1 - exact) / b) + 1 / b
    # all d = 0: every T* equals T, p = (B + 1/2) / (B + 1)
    assert randomisation_p(np.zeros(4), 99, np.random.default_rng(0)) == pytest.approx(99.5 / 100)


def test_van_der_voet_takes_the_fewest_lvs_not_significantly_worse_than_the_minimum() -> None:
    rng = np.random.default_rng(1)
    base = rng.uniform(0.5, 1.5, size=30)
    noise = rng.normal(0, 0.05, size=30)
    noise += 0.01 - noise.mean()  # mean d = 0.01, t about 1.1: not significant
    rows = np.stack([base + 9, base + 4, base + noise, base, base + 0.3])  # a_min = 3
    press = rows.sum(axis=1)

    def pick(randomisation_alpha: float = 0.05) -> int:
        return select_lv(
            "van_der_voet", np.ones(5), press, FLAT, row_sq_err=rows,
            rng=np.random.default_rng(7), randomisation_alpha=randomisation_alpha,
        )  # fmt: skip

    assert pick() == 2  # a = 1 is far worse (p about 0); a = 2 differs only by noise
    assert pick(randomisation_alpha=0.999) == 3  # nothing passes: a_min
    with pytest.raises(ValueError, match="Generator"):
        select_lv("van_der_voet", np.ones(5), press, FLAT, row_sq_err=rows)
    with pytest.raises(ValueError, match="row_sq_err"):
        select_lv("haaland_thomas", np.ones(5), press, FLAT)
