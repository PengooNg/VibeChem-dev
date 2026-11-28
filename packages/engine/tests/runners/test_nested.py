# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/runners/test_nested.py
"""Nested CV runner (T2.10d "Done when", METHODS.md#nested-cv): results equal a
hand-written scikit-learn nested CV (``GridSearchCV`` inside the outer folds,
``PLSRegression``) on gasoline rows 1-50, ``row_index`` offset and reversed (R40).
"""

from __future__ import annotations

import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.model_selection import GridSearchCV, KFold  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.pipeline import Pipeline  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]
from sklearn.preprocessing import FunctionTransformer  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import Block, port
from vibechem_core.blocks.model.pls import PLS
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.validate.cv import CrossValidation
from vibechem_core.blocks.validate.folds import ContiguousBlocks
from vibechem_core.blocks.validate.folds import KFold as KFoldBlock
from vibechem_core.blocks.validate.grid_search import GridSearch
from vibechem_core.blocks.validate.nested_cv import NestedCV
from vibechem_core.data import Axis, FoldSet, Results, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.reference_datasets import load_reference_dataset
from vibechem_core.registry import Registry
from vibechem_core.testing import assert_reference
from vibechem_engine import runners
from vibechem_engine.compiler import compile_pipeline
from vibechem_engine.runners import PipelineRun, run_pipeline
from vibechem_engine.scheduler import Job, RunResult, run_jobs


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


class ThreadExecutor:
    def __init__(self, workers: int = 2) -> None:
        self._workers = workers
        self._pool = ThreadPoolExecutor(workers)

    @property
    def max_workers(self) -> int:
        return self._workers

    def submit[R](self, fn: Callable[..., R], /, *args: object) -> Future[R]:
        return self._pool.submit(fn, *args)

    def restart(self) -> None:
        pass

    def shutdown(self) -> None:
        self._pool.shutdown()


REGISTRY = Registry()
for _block in (
    Source,
    SNV,
    PLS,
    ContiguousBlocks,
    KFoldBlock,
    CrossValidation,
    GridSearch,
    NestedCV,
):
    REGISTRY.register(_block)
INNER: dict[str, Any] = {"block_id": "validate.contiguous_blocks", "params": {"k": 4}}
SNV_: dict[str, Any] = {"block_id": "preprocess.snv", "params": {}}


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


def run(params: dict[str, Any], data: SpectralDataset, registry: Registry = REGISTRY, workers: int = 2) -> PipelineRun:  # fmt: skip
    """src -> folds (5 contiguous blocks); src -> pls (10 LV) -> nested; folds -> nested."""
    nodes: list[dict[str, Any]] = [
        {"node_id": "src", "block_id": "test.source", "params": {}},
        {"node_id": "folds", "block_id": "validate.contiguous_blocks", "params": {"k": 5}},
        {"node_id": "pls", "block_id": "model.pls", "params": {"n_components": 10}},
        {"node_id": "nest", "block_id": "validate.nested_cv", "params": params},
    ]
    edges = [("src", "spectra", "folds", "spectra"), ("src", "spectra", "pls", "spectra"),
             ("pls", "model", "nest", "model"), ("folds", "folds", "nest", "folds")]  # fmt: skip
    doc: dict[str, Any] = {
        "nodes": nodes,
        "edges": [
            {"edge_id": f"e{i}", "from_node": a, "from_port": ap, "to_node": b, "to_port": bp}
            for i, (a, ap, b, bp) in enumerate(edges)
        ],
    }
    compiled = compile_pipeline(doc, registry)
    return run_pipeline(compiled, doc, registry, {"src": {"spectra": data}}, ThreadExecutor(workers), root_seed=5)  # fmt: skip


def snv(X: NDArray[np.float64]) -> NDArray[np.float64]:
    return (X - X.mean(axis=1, keepdims=True)) / X.std(axis=1, ddof=1, keepdims=True)


def sklearn_nested(
    data: SpectralDataset, folds: FoldSet, chains: list[Any]
) -> tuple[NDArray[np.float64], list[tuple[int, int]]]:
    """scikit-learn nested CV on positions: per outer fold ``GridSearchCV`` over the chains
    and 1-10 LV on 4 contiguous inner folds of the outer training rows (in their order),
    refit on them, predict the outer validation rows. Returns the out-of-fold predictions
    by position and per fold (chain index, LV count)."""
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    y = cast(NDArray[np.float64], data.y)[:, 0]
    pred = np.full(y.size, np.nan)
    chosen: list[tuple[int, int]] = []
    for f in folds.folds:
        tr = [position[r] for r in f.train.tolist()]
        va = [position[r] for r in f.validation.tolist()]
        pipe: Any = Pipeline([("pre", "passthrough"), ("pls", PLSRegression(scale=False))])
        grid = {"pre": chains, "pls__n_components": list(range(1, 11))}
        kfold: Any = KFold(4)
        inner = list(kfold.split(np.arange(len(tr))))  # equal folds: mean fold MSE = pooled
        search: Any = GridSearchCV(pipe, grid, cv=inner, scoring="neg_mean_squared_error")
        search.fit(data.X[tr], y[tr])
        pred[va] = np.asarray(search.predict(data.X[va])).ravel()
        best = search.best_params_
        chosen.append((chains.index(best["pre"]), best["pls__n_components"]))
    return pred, chosen


@pytest.mark.parametrize("with_snv", [False, True])
def test_nested_cv_matches_hand_written_scikit_learn_nested_cv(
    gasoline: SpectralDataset, with_snv: bool
) -> None:
    params: dict[str, Any] = {"inner_folds": INNER}
    chains: list[Any] = ["passthrough"]
    if with_snv:
        params["search_space"] = [[None, SNV_]]
        chains.append(FunctionTransformer(snv))
    out = run(params, gasoline)
    assert out.status == "succeeded", out.errors
    got = cast(Results, out.output("nest", "results"))
    folds = cast(FoldSet, out.output("folds", "folds"))
    pred, chosen = sklearn_nested(gasoline, folds, chains)

    assert got.kind == "nested_cv"
    assert [(o["candidate"], o["n_lv"]) for o in got.details["outer"]] == chosen
    y = cast(NDArray[np.float64], gasoline.y)[:, 0]
    assert_reference(method="Nested CV RMSECV (outer, pooled)", dataset=f"gasoline_nir rows 1-50, 5x4 contiguous, snv={with_snv}",
                     actual=got.metrics["rmsecv"], expected=float(np.sqrt(np.mean((pred - y) ** 2))),
                     rtol=1e-10, atol=1e-12, source="hand-written scikit-learn GridSearchCV nested CV")  # fmt: skip
    table = cast(dict[str, NDArray[Any]], got.predictions)
    position = {r: i for i, r in enumerate(gasoline.row_index.tolist())}
    at = [position[r] for r in table["row_index"].tolist()]
    np.testing.assert_allclose(table["y_pred_octane"], pred[at], rtol=1e-10, atol=1e-12)
    if with_snv:  # gasoline picks SNV in some outer folds, none in others; chains in full
        assert {o["candidate"] for o in got.details["outer"]} == {0, 1}
        assert all(o["chain"] in ("[]", '[{"block_id":"preprocess.snv","params":{"ddof":1}}]') for o in got.details["outer"])  # fmt: skip


def test_only_the_chosen_branch_runs_per_outer_fold(gasoline: SpectralDataset) -> None:
    out = run({"inner_folds": INNER, "search_space": [[None, SNV_]]}, gasoline)
    assert out.status == "succeeded", out.errors
    got = cast(Results, out.output("nest", "results"))
    for o in got.details["outer"]:
        tag = f"@nest.c{o['candidate']}/f{o['fold']}r{o['repeat']}"
        other = f"@nest.c{1 - o['candidate']}/f{o['fold']}r{o['repeat']}"
        assert any(tag in t for t in out.outputs)
        assert not any(other in t for t in out.outputs)
    assert not any(
        t.startswith("nest.c") and "@" not in t for t in out.outputs
    )  # no full-data branch fits


def test_bad_inner_folds_is_a_node_error(gasoline: SpectralDataset) -> None:
    out = run({"inner_folds": {"block_id": "preprocess.snv"}}, gasoline)
    assert out.status == "failed"
    err = out.errors["nest:run"]
    assert isinstance(err, ParamError)
    assert err.params["reason"] == "not_a_fold_block"


def test_nested_cv_needs_grid_search_in_the_registry(gasoline: SpectralDataset) -> None:
    registry = Registry()
    for block in (Source, PLS, ContiguousBlocks, CrossValidation, NestedCV):
        registry.register(block)
    with pytest.raises(ValueError, match=r"validate.grid_search"):
        run({"inner_folds": INNER}, gasoline, registry)


SHUFFLED: dict[str, Any] = {"block_id": "validate.kfold", "params": {"k": 3, "shuffle": True}}


def serial(subs: Any) -> Any:
    """The sub-runs one after another, each stage alone (the order before Quan's decision)."""
    out: list[Any] = []
    for sub in subs:
        out.append((yield from sub))
    return out


@pytest.mark.parametrize("workers", [1, 4])
def test_shared_scheduler_gives_the_serial_results(
    gasoline: SpectralDataset, workers: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Inner sub-runs merged into one scheduler stage = run one outer fold after another
    (shuffled inner folds: each sub-run's seeds must survive the merge), bit for bit."""
    params: dict[str, Any] = {
        "inner_folds": SHUFFLED,
        "search_space": [[None, SNV_]],
        "n_jobs": workers,
    }
    merged = cast(Results, run(params, gasoline, workers=workers).output("nest", "results"))
    with monkeypatch.context() as m:
        m.setattr(runners, "_together", serial)
        alone = cast(Results, run(params, gasoline, workers=workers).output("nest", "results"))
    assert merged.details["outer"] == alone.details["outer"]
    assert merged.metrics == alone.metrics
    got, want = cast(dict[str, Any], merged.predictions), cast(dict[str, Any], alone.predictions)
    assert got.keys() == want.keys()
    for column in got:
        np.testing.assert_array_equal(got[column], want[column])


def test_idle_workers_take_the_next_outer_folds_inner_tasks(
    gasoline: SpectralDataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    """8 workers, one candidate on 2 inner folds: one outer fold cannot fill the workers,
    so inner tasks of several outer folds run at once."""
    lock, running, peak = threading.Lock(), Counter[str](), [0]
    real = run_jobs

    def tracked(job: Job) -> Job:
        outer = job.task_id.split("|", 1)[0] if "|" in job.task_id else ""

        def work(seed: int, *args: object) -> object:
            with lock:
                running[outer] += 1
                peak[0] = max(peak[0], len([k for k, n in running.items() if k and n]))
            time.sleep(0.01)
            try:
                return job.fn(seed, *args)
            finally:
                with lock:
                    running[outer] -= 1

        return replace(job, fn=work)

    def spy(jobs: list[Job], executor: Any, **kw: Any) -> RunResult:
        return real([tracked(j) for j in jobs], executor, **kw)

    monkeypatch.setattr(runners, "run_jobs", spy)
    inner = {"block_id": "validate.contiguous_blocks", "params": {"k": 2}}
    out = run(
        {"inner_folds": inner, "n_jobs": 8}, gasoline, workers=8
    )  # default n_jobs = cores - 10
    assert out.status == "succeeded", out.errors
    assert peak[0] >= 2


class Boom(Block):
    """A Spectra step that fails on any data holding row 1049 (outer fold 0's validation)."""

    block_id = "test.boom"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)

    def apply(self, spectra: SpectralDataset, **kwargs: Any) -> SpectralDataset:  # noqa: ARG002
        if 1049 in spectra.row_index.tolist():
            raise ValueError("boom")
        return spectra


@pytest.mark.parametrize("workers", [1, 8])
def test_failed_inner_runs_report_the_first_outer_fold_in_fold_order(
    gasoline: SpectralDataset, workers: int
) -> None:
    """Every outer fold but the one without row 1049 fails; whatever finishes first, the
    node error is the first failing fold's, named in a note."""
    registry = Registry()
    for block in (Source, PLS, ContiguousBlocks, CrossValidation, GridSearch, NestedCV, Boom):
        registry.register(block)
    boom: dict[str, Any] = {"block_id": "test.boom", "params": {}}
    params: dict[str, Any] = {"inner_folds": INNER, "search_space": [[boom]], "n_jobs": workers}
    out = run(params, gasoline, registry, workers)
    assert out.status == "failed"
    folds = cast(FoldSet, out.output("folds", "folds"))
    first = next(f for f in folds.folds if 1049 in f.train.tolist())
    err = out.errors["nest:run"]
    assert str(err) == "boom"
    assert f"inner search of nest, outer fold {first.fold} repeat {first.repeat}" in err.__notes__
