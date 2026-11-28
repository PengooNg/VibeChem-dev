# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/runners/test_nested.py
"""Nested CV runner (T2.10d "Done when", METHODS.md#nested-cv): results equal a
hand-written scikit-learn nested CV (``GridSearchCV`` inside the outer folds,
``PLSRegression``) on gasoline rows 1-50, ``row_index`` offset and reversed (R40).
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
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
from vibechem_core.blocks.validate.grid_search import GridSearch
from vibechem_core.blocks.validate.nested_cv import NestedCV
from vibechem_core.data import Axis, FoldSet, Results, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.reference_datasets import load_reference_dataset
from vibechem_core.registry import Registry
from vibechem_core.testing import assert_reference
from vibechem_engine.compiler import compile_pipeline
from vibechem_engine.runners import PipelineRun, run_pipeline


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
    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(2)

    @property
    def max_workers(self) -> int:
        return 2

    def submit[R](self, fn: Callable[..., R], /, *args: object) -> Future[R]:
        return self._pool.submit(fn, *args)

    def restart(self) -> None:
        pass

    def shutdown(self) -> None:
        self._pool.shutdown()


REGISTRY = Registry()
for _block in (Source, SNV, PLS, ContiguousBlocks, CrossValidation, GridSearch, NestedCV):
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


def run(params: dict[str, Any], data: SpectralDataset, registry: Registry = REGISTRY) -> PipelineRun:  # fmt: skip
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
    return run_pipeline(compiled, doc, registry, {"src": {"spectra": data}}, ThreadExecutor(), root_seed=5)  # fmt: skip


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
