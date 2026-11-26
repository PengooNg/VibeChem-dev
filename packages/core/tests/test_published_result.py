# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_published_result.py
"""Phase 1 exit check: the published gasoline PLS result, reproduced end to end (T1.15).

Mevik & Wehrens (2007), section 2: training samples 1-50, test 51-60, PLS 0-10
components on mean-centred data, leave-one-out CV. The chain is the one a user builds
from Phase 1 blocks: ``validate.loo`` folds -> ``model.pls`` sweep per fold ->
``cv_metrics`` (pooled) for RMSECV, ``regression_metrics`` for the test set.
"""

from __future__ import annotations

import warnings

import numpy as np

from vibechem_core.block import NoParams, parse_params
from vibechem_core.blocks.model.pls import PLS, PLSParams, predict_sweep
from vibechem_core.blocks.validate.folds import LeaveOneOut
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.metrics import cv_metrics, regression_metrics
from vibechem_core.reference_datasets import load_expected, load_reference_dataset
from vibechem_core.testing import assert_reference

SOURCE = "Mevik & Wehrens 2007, testdata/expected/gasoline_nir_pls.json"
METHOD = "Published result (PLS, LOO)"


def test_gasoline_published_result_end_to_end() -> None:
    data = load_reference_dataset("gasoline_nir")
    expected = load_expected("gasoline_nir_pls")
    values, rtol = expected["values"], expected["tolerance"]["rtol"]  # T-pub
    full = SpectralDataset(
        data.spectra,
        Axis(data.axis, "nm"),
        signal_unit="absorbance",
        sample_ids=[str(s) for s in data.sample_ids],
        row_index=np.arange(60),
        source_id="gasoline_nir",
        y=data.target.astype(np.float64)[:, None],
        y_columns=["octane"],
        y_units=["octane number"],
    )
    train, test = full.subset(np.arange(50)), full.subset(np.arange(50, 60))
    assert train.y is not None
    assert test.y is not None
    pls_params = parse_params(PLSParams, {"n_components": 10})

    folds = LeaveOneOut().apply(train, NoParams())
    oof = np.empty((11, 50))
    fold_of = np.empty(50, dtype=np.int64)
    for fold in folds.folds:
        state = PLS().fit(train.subset(fold.train), pls_params)
        oof[:, fold.validation] = predict_sweep(state, train.subset(fold.validation))[:, :, 0]
        fold_of[fold.validation] = fold.fold

    state = PLS().fit(train, pls_params)
    sweep = predict_sweep(state, test)
    x_cumulative = 100 * np.cumsum(state.arrays["x_explained"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # METRIC_FEW_SAMPLES: 10 test samples < ISO 12099 minimum
        for a in range(11):
            assert_reference(method=f"{METHOD} RMSECV", dataset=f"gasoline_nir, {a} LV",
                             actual=cv_metrics(train.y[:, 0], oof[a], fold_of)["rmsecv"],
                             expected=values["rmsep_cv"][a], rtol=rtol, atol=0.0, source=SOURCE)  # fmt: skip
        # LV 0 skipped: pls computes the intercept-only test RMSEP with the test-set mean.
        for a in range(1, 11):
            assert_reference(method=f"{METHOD} RMSEP", dataset=f"gasoline_nir test, {a} LV",
                             actual=regression_metrics(test.y[:, 0], sweep[a, :, 0], "p")["rmsep"],
                             expected=values["rmsep_test"][a], rtol=rtol, atol=0.0, source=SOURCE)  # fmt: skip
            assert_reference(method=f"{METHOD} cumulative X variance %", dataset=f"gasoline_nir, {a} LV",
                             actual=float(x_cumulative[a - 1]),
                             expected=values["x_variance_explained_cumulative_pct"][a - 1],
                             rtol=rtol, atol=0.0, source=SOURCE)  # fmt: skip
