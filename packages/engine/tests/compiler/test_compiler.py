# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/compiler/test_compiler.py
"""``vibechem_engine.compiler``: compiled task graphs of three example pipelines match
the expected structures; fold rows go by ``row_index`` (T2.04 "Done when", R40)."""

from __future__ import annotations

from typing import Any

import numpy as np

from vibechem_core.block import Block, port
from vibechem_core.blocks.model.pls import PLS
from vibechem_core.blocks.preprocess.msc import MSC
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.split.random_split import RandomSplit
from vibechem_core.blocks.validate.folds import KFold
from vibechem_core.data import Axis, Fold, SpectralDataset
from vibechem_core.registry import Registry
from vibechem_engine.compiler import CompiledPipeline, Task, TaskInput, compile_pipeline, fold_rows


class _Source(Block):
    block_id = "test.source"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = ()
    outputs = (port("spectra", "Spectra"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


class _Sink(Block):
    block_id = "test.sink"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("table", "Table"),)
    outputs = ()

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


class _Predict(Block):
    block_id = "test.predict"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("model", "Model"), port("spectra", "Spectra"))
    outputs = (port("predictions", "Table"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


class _CV(Block):
    block_id = "test.cv"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("model", "Model", refit_per_fold=True), port("folds", "Folds"))
    outputs = (port("results", "Results"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


REGISTRY = Registry()
for _block in (_Source, _Sink, _Predict, _CV, SNV, MSC, PLS, RandomSplit, KFold):
    REGISTRY.register(_block)

_BLOCKS = {
    "src": "test.source",
    "src2": "test.source",
    "sink": "test.sink",
    "pred": "test.predict",
    "cv": "test.cv",
    "snv": "preprocess.snv",
    "msc": "preprocess.msc",
    "pls": "model.pls",
    "split": "split.random",
    "kfold": "validate.kfold",
}


def _compile(edges: list[str]) -> CompiledPipeline:
    """Edges as ``"a.port -> b.port"``; nodes are named after ``_BLOCKS``."""
    pairs = [tuple(x.strip().split(".") for x in e.split("->")) for e in edges]
    names = list(dict.fromkeys(n for (a, _), (b, _) in pairs for n in (a, b)))
    pipeline = {
        "nodes": [{"node_id": n, "block_id": _BLOCKS[n]} for n in names],
        "edges": [
            {"edge_id": f"eg_{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
            for i, ((a, ap), (b, bp)) in enumerate(pairs)
        ],
    }
    return compile_pipeline(pipeline, REGISTRY)


def _structure(tasks: tuple[Task, ...]) -> dict[str, tuple[str, set[tuple[str, ...]]]]:
    """task_id -> (kind, {(port_id, task_id, output[, rule])})."""
    return {
        t.task_id: (
            t.kind,
            {(i.port_id, i.task_id, i.output) + ((i.rule,) if i.rule else ()) for i in t.inputs},
        )
        for t in tasks
    }


def test_chain_fit_apply_split_and_implicit_view() -> None:
    compiled = _compile(
        ["src.spectra -> snv.spectra", "snv.spectra -> msc.spectra", "msc.spectra -> sink.table"]
    )
    assert compiled.issues == ()
    assert compiled.fold_plans == {}
    assert _structure(compiled.tasks) == {
        "src:run": ("run", set()),
        "snv:run": ("run", {("spectra", "src:run", "spectra")}),
        "msc:fit": ("fit", {("spectra", "snv:run", "spectra")}),
        "msc:apply": (
            "apply",
            {("spectra", "snv:run", "spectra"), ("state", "msc:fit", "state")},
        ),
        "sink:run": ("run", {("table", "msc:apply", "spectra", "implicit_view")}),
    }
    order = [t.task_id for t in compiled.tasks]
    assert order.index("msc:fit") < order.index("msc:apply") < order.index("sink:run")


def test_holdout_model_state_applied_to_test_rows() -> None:
    compiled = _compile(
        [
            "src.spectra -> split.spectra",
            "split.train -> pls.spectra",
            "pls.model -> pred.model",
            "split.test -> pred.spectra",
        ]
    )
    structure = _structure(compiled.tasks)
    assert structure["pls:fit"] == ("fit", {("spectra", "split:run", "train")})
    assert structure["pred:run"] == (
        "run",
        {("model", "pls:fit", "state"), ("spectra", "split:run", "test")},
    )
    assert all(t.fold is None and t.part is None for t in compiled.tasks)


def test_graph_errors_give_no_tasks() -> None:
    compiled = _compile(["src.spectra -> pred.spectra"])
    assert compiled.tasks == ()
    assert [(i.code, i.node_id, i.port_id) for i in compiled.issues] == [
        ("PIPELINE_REQUIRED_INPUT_MISSING", "pred", "model")
    ]


_CV_EDGES = [
    "src.spectra -> snv.spectra",
    "snv.spectra -> msc.spectra",
    "msc.spectra -> pls.spectra",
    "src.spectra -> kfold.spectra",
    "pls.model -> cv.model",
    "kfold.folds -> cv.folds",
]


def _parts_seen(task_id: str, by_id: dict[str, Task]) -> set[str]:
    """Fold parts (train/validation) of every select task upstream of ``task_id``."""
    task = by_id.get(task_id)
    if task is None:  # a full-row task outside the fold
        return set()
    if task.kind == "select":
        assert task.part is not None
        return {task.part}
    seen: set[str] = set()
    return seen.union(*(_parts_seen(i.task_id, by_id) for i in task.inputs))


def test_kfold_cv_fold_expansion() -> None:
    compiled = _compile(_CV_EDGES)
    assert compiled.issues == ()
    # outside the folds the model is refitted on all rows and handed to the CV node
    assert _structure(compiled.tasks)["cv:run"] == (
        "run",
        {("model", "pls:fit", "state"), ("folds", "kfold:run", "folds")},
    )
    plan = compiled.fold_plans["cv"]
    assert (plan.port_id, plan.nodes) == ("model", ("snv", "msc", "pls"))
    assert plan.source == TaskInput("data", "src:run", "spectra")
    assert plan.folds == TaskInput("folds", "kfold:run", "folds")

    fold = plan.expand(1, 0)
    t = "@cv/f1r0"
    assert _structure(fold.tasks) == {
        f"src:select{t}/train": (
            "select",
            {("data", "src:run", "spectra"), ("folds", "kfold:run", "folds")},
        ),
        f"src:select{t}/validation": (
            "select",
            {("data", "src:run", "spectra"), ("folds", "kfold:run", "folds")},
        ),
        f"snv:run{t}/train": ("run", {("spectra", f"src:select{t}/train", "rows")}),
        f"snv:run{t}/validation": ("run", {("spectra", f"src:select{t}/validation", "rows")}),
        f"msc:fit{t}": ("fit", {("spectra", f"snv:run{t}/train", "spectra")}),
        f"msc:apply{t}/train": (
            "apply",
            {("spectra", f"snv:run{t}/train", "spectra"), ("state", f"msc:fit{t}", "state")},
        ),
        f"msc:apply{t}/validation": (
            "apply",
            {("spectra", f"snv:run{t}/validation", "spectra"), ("state", f"msc:fit{t}", "state")},
        ),
        f"pls:fit{t}": ("fit", {("spectra", f"msc:apply{t}/train", "spectra")}),
        f"pls:apply{t}/train": (
            "apply",
            {("spectra", f"msc:apply{t}/train", "spectra"), ("state", f"pls:fit{t}", "state")},
        ),
        f"pls:apply{t}/validation": (
            "apply",
            {("spectra", f"msc:apply{t}/validation", "spectra"), ("state", f"pls:fit{t}", "state")},
        ),
    }
    assert fold.state == TaskInput("model", f"pls:fit{t}", "state")
    assert fold.validation == f"pls:apply{t}/validation"
    assert all(task.fold == (1, 0) for task in fold.tasks)
    by_id = {task.task_id: task for task in fold.tasks}
    for task in fold.tasks:
        if task.kind == "fit":
            assert _parts_seen(task.task_id, by_id) == {"train"}, task.task_id


def test_folds_on_split_train_refit_only_downstream_nodes() -> None:
    compiled = _compile(
        [
            "src.spectra -> split.spectra",
            "split.train -> pls.spectra",
            "split.train -> kfold.spectra",
            "pls.model -> cv.model",
            "kfold.folds -> cv.folds",
        ]
    )
    plan = compiled.fold_plans["cv"]
    assert plan.nodes == ("pls",)  # the hold-out split is not re-run per fold
    assert plan.source == TaskInput("data", "split:run", "train")


def test_folds_from_another_source_is_a_mismatch() -> None:
    compiled = _compile(
        [
            "src.spectra -> pls.spectra",
            "src2.spectra -> kfold.spectra",
            "pls.model -> cv.model",
            "kfold.folds -> cv.folds",
        ]
    )
    assert compiled.tasks == ()
    assert [(i.code, i.node_id, i.port_id) for i in compiled.issues] == [
        ("PIPELINE_FOLDS_SOURCE_MISMATCH", "cv", "model")
    ]


def test_fold_rows_use_row_index_on_an_offset_dataset() -> None:
    data = SpectralDataset(
        np.arange(8.0).reshape(4, 2),
        Axis([1.0, 2.0], "nm"),
        signal_unit="absorbance",
        sample_ids=["a", "b", "c", "d"],
        row_index=[103, 100, 102, 101],  # offset from positions 0..3 and not sorted
        source_id="ds_test",
    )
    fold = Fold(0, 0, train=[100, 101], validation=[103])
    assert fold_rows(data, fold, "train").sample_ids == ("b", "d")
    assert fold_rows(data, fold, "validation").sample_ids == ("a",)


def test_fitted_node_before_the_fold_source_is_leakage() -> None:
    # MSC fitted once on all rows, then folds made on its output: validation rows leak
    compiled = _compile(
        [
            "src.spectra -> msc.spectra",
            "msc.spectra -> kfold.spectra",
            "msc.spectra -> pls.spectra",
            "pls.model -> cv.model",
            "kfold.folds -> cv.folds",
        ]
    )
    assert compiled.tasks == ()
    assert [(i.code, i.node_id, i.port_id) for i in compiled.issues] == [
        ("PIPELINE_LEAKAGE", "msc", None)
    ]
