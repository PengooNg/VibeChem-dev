# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/leakage/test_rules.py
"""Leakage rules (``vibechem_engine.compiler.leakage``): a fit task that could see rows
outside its training subset is ``PIPELINE_LEAKAGE`` on the fitted node and the input
port it came through (T2.05 "Done when", R39)."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

import pytest

from vibechem_core.block import Block
from vibechem_engine.compiler import CompiledPipeline

type CompileEdges = Callable[..., CompiledPipeline]

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
    # inside a fold the first input must be the fold's training rows too (unsplit spectra
    # with a fold-train reference refits on every row, test and validation rows included)
    "unsplit_spectra_in_fold_scope": (
        [
            "src.spectra -> split.spectra",
            "split.train -> kfold.spectra",
            "kfold.folds -> cv.folds",
            "src.spectra -> msc.spectra",
            "split.train -> msc.reference",
            "msc.spectra -> pls.spectra",
            "pls.model -> cv.model",
        ],
        "msc",
        "spectra",
    ),
    # a second data node loading the same dataset is the same source (same block, params)
    "msc_reference_from_a_twin_source_node": (
        [*_CV_ON_TRAIN, "src2.spectra -> msc.reference"],
        "msc",
        "reference",
    ),
    # centring fitted once on all rows before the hold-out split saw the test rows
    "fitted_before_holdout_split": (
        [
            "src.spectra -> centre.spectra",
            "centre.spectra -> split.spectra",
            "split.train -> pls.spectra",
            "pls.model -> pred.model",
            "split.test -> pred.spectra",
        ],
        "centre",
        None,
    ),
    # external test set: the model was fitted on all rows, test rows included
    "model_fitted_on_all_rows_applied_to_test": (
        [
            "src.spectra -> pls.spectra",
            "src.spectra -> split.spectra",
            "pls.model -> pred.model",
            "split.test -> pred.spectra",
        ],
        "pred",
        "model",
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
    # a subset of the training rows as reference
    "msc_reference_from_a_training_subset": [
        *_HOLDOUT,
        "split.train -> split2.spectra",
        "split2.train -> msc.reference",
    ],
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
    compiled = compile_edges(SAFE[case], {"src2": {"dataset": "another file"}})
    assert compiled.issues == ()
    assert compiled.tasks != ()


def test_every_fitted_core_block_takes_its_training_rows_first() -> None:
    # the provenance rule treats a fitted block's first input as its training rows
    package = importlib.import_module("vibechem_core.blocks")
    for module in pkgutil.walk_packages(package.__path__, "vibechem_core.blocks."):
        importlib.import_module(module.name)
    fitted = [
        b
        for b in _subclasses(Block)
        if getattr(b, "fitted", False) and b.__module__.startswith("vibechem_core.blocks")
    ]
    assert fitted
    for block in fitted:
        assert block.inputs[0].port_type == "Spectra", block.block_id


def _subclasses(cls: type[Block]) -> list[type[Block]]:
    return [s for c in cls.__subclasses__() for s in (c, *_subclasses(c))]
