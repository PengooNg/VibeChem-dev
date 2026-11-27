# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/leakage/test_rules.py
"""Leakage rules (``vibechem_engine.compiler.leakage``): a fit task that could see rows
outside its training subset is ``PIPELINE_LEAKAGE`` on the fitted node and the input
port it came through (T2.05 "Done when", R39)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from vibechem_engine.compiler import CompiledPipeline

type CompileEdges = Callable[[list[str]], CompiledPipeline]

_CV_ON_TRAIN = [
    "src.spectra -> split.spectra",
    "split.train -> kfold.spectra",
    "split.train -> msc.spectra",
    "msc.spectra -> pls.spectra",
    "pls.model -> cv.model",
    "kfold.folds -> cv.folds",
]
_HOLDOUT = [
    "src.spectra -> split.spectra",
    "split.train -> msc.spectra",
    "msc.spectra -> pls.spectra",
    "pls.model -> pred.model",
    "split.test -> pred.spectra",
]

LEAKY = {
    # R39: MSC reference from the unsplit dataset holds test and every fold's validation rows
    "msc_reference_unsplit_in_cv": (
        [*_CV_ON_TRAIN, "src.spectra -> msc.reference"],
        "msc",
        "reference",
    ),
    # R39 without a split: folds made after a stateless step, reference from the raw data
    "msc_reference_upstream_of_fold_source": (
        [
            "src.spectra -> snv.spectra",
            "snv.spectra -> kfold.spectra",
            "snv.spectra -> msc.spectra",
            "src.spectra -> msc.reference",
            "msc.spectra -> pls.spectra",
            "pls.model -> cv.model",
            "kfold.folds -> cv.folds",
        ],
        "msc",
        "reference",
    ),
    "msc_reference_from_test_in_cv": (
        [*_CV_ON_TRAIN, "split.test -> msc.reference"],
        "msc",
        "reference",
    ),
    "msc_reference_unsplit_holdout": (
        [*_HOLDOUT, "src.spectra -> msc.reference"],
        "msc",
        "reference",
    ),
    "fit_on_test_rows": (
        [
            "src.spectra -> split.spectra",
            "split.test -> pls.spectra",
            "pls.model -> pred.model",
            "split.train -> pred.spectra",
        ],
        "pls",
        "spectra",
    ),
    # a y scaling fitted once on all rows, handed to the per-fold PLS
    "y_transform_fitted_on_all_rows": (
        [
            "src.spectra -> split.spectra",
            "split.train -> kfold.spectra",
            "split.train -> pls.spectra",
            "src.spectra -> centre.spectra",
            "centre.transform -> pls.y_transform",
            "pls.model -> cv.model",
            "kfold.folds -> cv.folds",
        ],
        "pls",
        "y_transform",
    ),
}


@pytest.mark.parametrize("case", LEAKY)
def test_leaky_pipeline_is_rejected(compile_edges: CompileEdges, case: str) -> None:
    edges, node_id, port_id = LEAKY[case]
    compiled = compile_edges(edges)
    assert compiled.tasks == ()
    assert compiled.fold_plans == {}
    assert [(i.code, i.node_id, i.port_id) for i in compiled.issues] == [
        ("PIPELINE_LEAKAGE", node_id, port_id)
    ]


SAFE = {
    "msc_reference_from_another_dataset": [*_CV_ON_TRAIN, "src2.spectra -> msc.reference"],
    # the fold source stream itself is cut to the fold's train rows for every fit
    "msc_reference_from_fold_source": [
        "src.spectra -> kfold.spectra",
        "src.spectra -> msc.spectra",
        "src.spectra -> msc.reference",
        "msc.spectra -> pls.spectra",
        "pls.model -> cv.model",
        "kfold.folds -> cv.folds",
    ],
    "msc_reference_from_train_in_holdout": [*_HOLDOUT, "split.train -> msc.reference"],
    "y_transform_inside_the_folds": [
        "src.spectra -> kfold.spectra",
        "src.spectra -> centre.spectra",
        "centre.transform -> pls.y_transform",
        "src.spectra -> pls.spectra",
        "pls.model -> cv.model",
        "kfold.folds -> cv.folds",
    ],
}


@pytest.mark.parametrize("case", SAFE)
def test_safe_pipeline_compiles(compile_edges: CompileEdges, case: str) -> None:
    compiled = compile_edges(SAFE[case])
    assert compiled.issues == ()
    assert compiled.tasks != ()
