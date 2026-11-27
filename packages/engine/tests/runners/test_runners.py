# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/runners/test_runners.py
"""``vibechem_engine.runners``: the CV runner (T2.10a "Done when", METHODS.md#cv).

Gasoline rows 1-50 with ``row_index`` offset from the positions and reversed (R40): fold
rows are taken by ``row_index`` only, so a position-based selection would pick other rows.
"""

from __future__ import annotations

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
from vibechem_core.data import Axis, FoldSet, Results, SpectralDataset
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
