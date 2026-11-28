# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/runners/test_runners.py
"""``vibechem_engine.runners``: the CV runner (T2.10a "Done when", METHODS.md#cv) and the
grid search (T2.10c "Done when", METHODS.md#grid-search).

Gasoline rows 1-50 with ``row_index`` offset from the positions and reversed (R40): fold
rows are taken by ``row_index`` only, so a position-based selection would pick other rows.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import Block, State, port
from vibechem_core.blocks.model.pls import PLS
from vibechem_core.blocks.preprocess.scaling import Autoscale
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.validate.cv import CrossValidation
from vibechem_core.blocks.validate.folds import ContiguousBlocks, LeaveOneOut
from vibechem_core.blocks.validate.grid_search import GridSearch
from vibechem_core.data import Axis, FoldSet, Results, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.reference_datasets import load_expected, load_reference_dataset
from vibechem_core.registry import Registry
from vibechem_core.testing import assert_reference
from vibechem_engine.compiler import compile_pipeline
from vibechem_engine.executor import ProcessExecutor
from vibechem_engine.runners import PipelineRun, run_pipeline

SOURCE = "Mevik & Wehrens 2007, testdata/expected/gasoline_nir_pls.json"


class Source(Block):
    """A data node; the test supplies its output."""

    block_id = "test.source"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = ()
    outputs = (port("spectra", "Spectra"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        return None


REGISTRY = Registry()
for _block in (Source, SNV, Autoscale, PLS, ContiguousBlocks, LeaveOneOut, CrossValidation):
    REGISTRY.register(_block)


class ThreadExecutor:
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(2)
        self._lock = threading.Lock()

    @property
    def max_workers(self) -> int:
        return 2

    def submit[R](self, fn: Callable[..., R], /, *args: object) -> Future[R]:
        return self._pool.submit(fn, *args)

    def restart(self) -> None:
        pass

    def shutdown(self) -> None:
        self._pool.shutdown()


@pytest.fixture(scope="module")
def gasoline() -> SpectralDataset:
    data = load_reference_dataset("gasoline_nir")
    return SpectralDataset(
        data.spectra[:50],
        Axis(data.axis, "nm"),
        signal_unit="absorbance",
        sample_ids=[str(s) for s in data.sample_ids[:50]],
        row_index=np.arange(50)[::-1] + 1000,
        source_id="gasoline_nir",
        y=data.target.astype(np.float64)[:50, None],
        y_columns=["octane"],
        y_units=["octane number"],
    )


def pipeline(folds_block: str, folds_params: dict[str, Any], pre: str | None) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {"node_id": "src", "block_id": "test.source", "params": {}},
        {"node_id": "folds", "block_id": folds_block, "params": folds_params},
        {"node_id": "pls", "block_id": "model.pls", "params": {"n_components": 10}},
        {"node_id": "cv", "block_id": "validate.cv", "params": {}},
    ]
    edges: list[tuple[str, str, str, str]] = [("src", "spectra", "folds", "spectra"), ("pls", "model", "cv", "model"),
             ("folds", "folds", "cv", "folds")]  # fmt: skip
    if pre:
        nodes.append({"node_id": "pre", "block_id": pre, "params": {}})
        edges += [("src", "spectra", "pre", "spectra"), ("pre", "spectra", "pls", "spectra")]
    else:
        edges.append(("src", "spectra", "pls", "spectra"))
    return {
        "nodes": nodes,
        "edges": [
            {"edge_id": f"eg_{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
            for i, (a, ap, b, bp) in enumerate(edges)
        ],
    }


def run(doc: dict[str, Any], data: SpectralDataset, executor: Any) -> PipelineRun:
    compiled = compile_pipeline(doc, REGISTRY)
    return run_pipeline(compiled, doc, REGISTRY, {"src": {"spectra": data}}, executor, root_seed=7)


def results(out: PipelineRun) -> Results:
    assert out.status == "succeeded", out.errors
    return cast(Results, out.output("cv", "results"))


def test_loo_rmsecv_matches_the_published_gasoline_values(gasoline: SpectralDataset) -> None:
    out = results(run(pipeline("validate.loo", {}, pre=None), gasoline, ThreadExecutor()))
    expected = load_expected("gasoline_nir_pls")
    for a in range(1, 11):
        assert_reference(method="CV runner RMSECV (LOO, pooled)", dataset=f"gasoline_nir rows 1-50, {a} LV",
                         actual=out.details["rmsecv"][a], expected=expected["values"]["rmsep_cv"][a],
                         rtol=expected["tolerance"]["rtol"], atol=0.0, source=SOURCE)  # fmt: skip


type Scaler = Callable[[NDArray[np.float64]], tuple[NDArray[np.float64], NDArray[np.float64]]]


def snv(X: NDArray[np.float64]) -> NDArray[np.float64]:
    return (X - X.mean(axis=1, keepdims=True)) / X.std(axis=1, ddof=1, keepdims=True)


def sklearn_curve(
    data: SpectralDataset, folds: FoldSet, scaling_rows: str | None = None
) -> NDArray[np.float64]:
    """Hand-written scikit-learn CV, rows mapped to positions independently. ``scaling_rows``
    None: SNV; ``train``: autoscaling fitted on the fold's training rows; ``all``: on all rows."""
    y = cast(NDArray[np.float64], data.y)[:, 0]
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    sse = np.zeros(10)
    for f in folds.folds:
        tr = [position[r] for r in f.train.tolist()]
        va = [position[r] for r in f.validation.tolist()]
        if scaling_rows is None:
            x = snv(data.X)
        else:
            ref = data.X[tr] if scaling_rows == "train" else data.X
            x = (data.X - ref.mean(axis=0)) / ref.std(axis=0, ddof=1)
        for a in range(1, 11):
            pls: Any = PLSRegression(n_components=a, scale=False)
            pls.fit(x[tr], y[tr])
            pred: NDArray[np.float64] = pls.predict(x[va]).ravel()
            sse[a - 1] += float(((pred - y[va]) ** 2).sum())
    return np.sqrt(sse / y.size)


def test_five_fold_curve_matches_hand_written_scikit_learn_cv(gasoline: SpectralDataset) -> None:
    out = run(
        pipeline("validate.contiguous_blocks", {"k": 5}, pre="preprocess.snv"),
        gasoline,
        ThreadExecutor(),
    )
    folds = cast(FoldSet, out.output("folds", "folds"))
    got = results(out)
    np.testing.assert_allclose(got.details["rmsecv"][1:], sklearn_curve(gasoline, folds), rtol=1e-10, atol=1e-12)  # fmt: skip
    rows = cast(NDArray[np.int64], cast(Any, got.predictions)["row_index"])
    assert sorted(rows.tolist()) == sorted(gasoline.row_index.tolist())  # one OOF row each
    model = cast(State, out.output("cv", "model"))  # the full-data model at the chosen LV
    assert model.values["n_components"] == got.metrics["n_lv"]


def test_fitted_preprocessing_is_refitted_on_each_fold(gasoline: SpectralDataset) -> None:
    doc = pipeline("validate.contiguous_blocks", {"k": 5}, pre="preprocess.autoscale")
    out = run(doc, gasoline, ThreadExecutor())
    folds = cast(FoldSet, out.output("folds", "folds"))
    curve = np.array(results(out).details["rmsecv"][1:])
    np.testing.assert_allclose(curve, sklearn_curve(gasoline, folds, "train"), rtol=1e-10, atol=1e-12)  # fmt: skip
    leaky = sklearn_curve(gasoline, folds, "all")  # scaling fitted on the validation rows too
    assert np.abs(curve - leaky).max() > 1e-6


def test_process_pool_gives_the_same_curve(gasoline: SpectralDataset, tmp_path: Path) -> None:
    doc = pipeline("validate.contiguous_blocks", {"k": 5}, pre="preprocess.snv")
    with ProcessExecutor(2, tmp_path) as executor:
        pooled = results(run(doc, gasoline, executor))
    threaded = results(run(doc, gasoline, ThreadExecutor()))
    assert pooled.details["rmsecv"] == threaded.details["rmsecv"]


def test_compile_errors_are_refused(gasoline: SpectralDataset) -> None:
    doc = pipeline("validate.loo", {}, pre=None)
    doc["edges"] = [e for e in doc["edges"] if e["to_port"] != "folds"]
    compiled = compile_pipeline(doc, REGISTRY)
    with pytest.raises(ValueError, match="pipeline has errors"):
        run_pipeline(
            compiled, doc, REGISTRY, {"src": {"spectra": gasoline}}, ThreadExecutor(), root_seed=1
        )


# ---- Grid search (T2.10c) ---------------------------------------------------------


class Boom(Block):
    """A chain step that fails, to check that a branch error reaches the search node."""

    block_id = "test.boom"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        raise RuntimeError("boom")


SEARCH_REGISTRY = Registry()
for _block in (Source, SNV, Autoscale, PLS, ContiguousBlocks, CrossValidation, GridSearch, Boom):
    SEARCH_REGISTRY.register(_block)

SNV_: dict[str, Any] = {"block_id": "preprocess.snv", "params": {}}
AUTO: dict[str, Any] = {"block_id": "preprocess.autoscale", "params": {}}


def search_doc(validation: str, params: dict[str, Any], chain: list[str]) -> dict[str, Any]:
    """src -> folds; src -> chain -> pls -> <validation>; folds -> <validation>."""
    nodes: list[dict[str, Any]] = [
        {"node_id": "src", "block_id": "test.source", "params": {}},
        {"node_id": "folds", "block_id": "validate.contiguous_blocks", "params": {"k": 5}},
        {"node_id": "pls", "block_id": "model.pls", "params": {"n_components": 8}},
        {"node_id": "val", "block_id": validation, "params": params},
    ]
    edges = [("src", "spectra", "folds", "spectra"), ("pls", "model", "val", "model"),
             ("folds", "folds", "val", "folds")]  # fmt: skip
    prev = "src"
    for i, block_id in enumerate(chain):
        nodes.append({"node_id": f"p{i}", "block_id": block_id, "params": {}})
        edges.append((prev, "spectra", f"p{i}", "spectra"))
        prev = f"p{i}"
    edges.append((prev, "spectra", "pls", "spectra"))
    return {
        "nodes": nodes,
        "edges": [
            {"edge_id": f"e{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
            for i, (a, ap, b, bp) in enumerate(edges)
        ],
    }


def run_search(pipeline: dict[str, Any], data: SpectralDataset) -> PipelineRun:
    compiled = compile_pipeline(pipeline, SEARCH_REGISTRY)
    return run_pipeline(
        compiled,
        pipeline,
        SEARCH_REGISTRY,
        {"src": {"spectra": data}},
        ThreadExecutor(),
        root_seed=3,
    )


def test_each_candidate_equals_a_separate_cv_run_of_its_chain(gasoline: SpectralDataset) -> None:
    params: dict[str, Any] = {
        "lv_rule": "one_se",
        "search_space": [[None, SNV_, SNV_], [None, AUTO]],
    }
    out = run_search(search_doc("validate.grid_search", params, []), gasoline)
    assert out.status == "succeeded", out.errors
    search = cast(Results, out.output("val", "results"))
    assert search.kind == "search"
    table = cast(dict[str, Any], search.candidates)
    chains = [[], ["preprocess.autoscale"], ["preprocess.snv"], ["preprocess.snv", "preprocess.autoscale"]]  # fmt: skip
    assert [[s["block_id"] for s in json.loads(c)] for c in table["chain"]] == chains
    criterion: list[float] = []
    for i, chain in enumerate(chains):
        alone = run_search(search_doc("validate.cv", {"lv_rule": "one_se"}, chain), gasoline)
        assert alone.status == "succeeded", alone.errors
        cv = cast(Results, alone.output("val", "results"))
        branch = cast(Results, out.output(f"val.c{i}", "results"))
        assert json.dumps(branch.details) == json.dumps(cv.details)  # NaN-safe equality
        for name, value in cv.metrics.items():
            assert table[name][i] == value, (chain, name)
        assert_reference(method="Grid search candidate RMSECV", dataset=f"gasoline_nir rows 1-50, 5-fold, chain {chain}",
                         actual=float(table["rmsecv"][i]), expected=cv.metrics["rmsecv"], rtol=1e-10, atol=1e-12,
                         source="separate validate.cv run of the same chain")  # fmt: skip
        criterion.append(cv.details["rmsecv"][int(cv.metrics["n_lv"])])
    best = int(np.argmin(criterion))
    assert search.details["best"] == best
    assert table["rmsecv_at_n_lv"].tolist() == criterion


def test_unknown_block_id_is_a_node_error(gasoline: SpectralDataset) -> None:
    params: dict[str, Any] = {
        "search_space": [[None, {"block_id": "preprocess.nope", "params": {}}]]
    }
    out = run_search(search_doc("validate.grid_search", params, []), gasoline)
    assert out.status == "failed"
    err = out.errors["val:run"]
    assert isinstance(err, ParamError)
    assert err.params["reason"] == "unknown_block"
    assert err.params["value"] == "preprocess.nope"


def test_a_failing_branch_is_reported_on_the_search_node(gasoline: SpectralDataset) -> None:
    params: dict[str, Any] = {"search_space": [[None, {"block_id": "test.boom", "params": {}}]]}
    out = run_search(search_doc("validate.grid_search", params, []), gasoline)
    assert out.status == "failed"
    assert isinstance(out.errors["val:run"], RuntimeError)
    assert any(t.startswith("val.c1.s0:") for t in out.errors)


def test_search_needs_validate_cv_in_the_registry(gasoline: SpectralDataset) -> None:
    registry = Registry()
    for block in (Source, PLS, ContiguousBlocks, GridSearch):
        registry.register(block)
    doc_ = search_doc("validate.grid_search", {"search_space": [[None]]}, [])
    with pytest.raises(ValueError, match=r"validate.cv"):
        run_pipeline(
            compile_pipeline(doc_, registry), doc_, registry,
            {"src": {"spectra": gasoline}}, ThreadExecutor(), root_seed=3,
        )  # fmt: skip
