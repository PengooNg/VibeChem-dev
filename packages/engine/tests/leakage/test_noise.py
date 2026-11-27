# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/leakage/test_noise.py
"""Noise-data leakage test (QA.md §3, T2.05 "Done when"): X and y are independent
noise, so an honest CV R² is about 0 or below. A supervised variable selection fitted on
all rows before the folds inflates it (shown with scikit-learn); the compiler rejects
that graph, and the compiled fold plan of the safe graph reproduces scikit-learn
``Pipeline`` + ``cross_val_predict`` on the same folds (the independent reference).

scikit-learn ships no type information, so pyright's unknown-type checks are off here.
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.metrics import r2_score
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from vibechem_core.block import Block, Param, State, parse_params, port
from vibechem_core.data import Axis, FoldSet, SpectralDataset
from vibechem_core.registry import Registry
from vibechem_engine.compiler import STATE, CompiledPipeline, Task, compile_pipeline, fold_rows

_N, _P, _K, _OFFSET = 60, 500, 10, 1000
_STATE_TYPES = {"Model", "Transform"}


@dataclass(frozen=True)
class _TopKParams:
    k: int = Param(_K, min=1)


class _SelectTopK(Block):
    """Supervised selection: keep the k variables most correlated with y (training rows)."""

    block_id = "test.select_top_k"
    version = "1.0.0"
    icon = "glyph-dummy"
    fitted = True
    inputs = (port("spectra", "Spectra", requires=("y",)),)
    outputs = (port("spectra", "Spectra"), port("transform", "Transform"))
    params_type = _TopKParams

    def fit(self, spectra: SpectralDataset, params: _TopKParams) -> State:
        assert spectra.y is not None
        X = spectra.X - spectra.X.mean(axis=0)
        y = spectra.y[:, 0] - spectra.y[:, 0].mean()
        r = np.abs(X.T @ y) / np.sqrt((X**2).sum(axis=0) * (y**2).sum())
        return State({}, {"keep": np.sort(np.argsort(-r)[: params.k])})

    def apply(
        self,
        spectra: SpectralDataset,
        params: _TopKParams,  # noqa: ARG002
        state: State,
    ) -> SpectralDataset:
        keep = state.arrays["keep"]
        axis = Axis(spectra.axis.values[keep], spectra.axis.unit)
        return spectra.with_X(spectra.X[:, keep], axis=axis)


_PARAMS = {
    "kfold": {"k": 5, "shuffle": True, "seed": 0},
    "pls": {"n_components": 2, "n_components_mode": "fixed"},
}
_SAFE = [
    "src.spectra -> kfold.spectra",
    "src.spectra -> centre.spectra",
    "centre.spectra -> sel.spectra",
    "sel.spectra -> pls.spectra",
    "pls.model -> cv.model",
    "kfold.folds -> cv.folds",
]
_LEAKY = [  # centring and selection fitted once on all rows, folds made after them
    "src.spectra -> centre.spectra",
    "centre.spectra -> sel.spectra",
    "sel.spectra -> kfold.spectra",
    "sel.spectra -> pls.spectra",
    "pls.model -> cv.model",
    "kfold.folds -> cv.folds",
]

type Values = dict[tuple[str, str], Any]


class _Runner:
    """Executes compiled tasks the way the CV runner will (T2.10a): inputs by port_id."""

    def __init__(self, pipeline: dict[str, Any], registry: Registry) -> None:
        self.pipeline, self.registry = pipeline, registry
        self.block_of = {n["node_id"]: n["block_id"] for n in pipeline["nodes"]}

    def compile(self) -> CompiledPipeline:
        return compile_pipeline(self.pipeline, self.registry)

    def params(self, node_id: str) -> Any:
        cls = self.registry.get(self.block_of[node_id])
        return parse_params(cls.params_type, _PARAMS.get(node_id, {}))

    def run(self, task: Task, values: Values) -> None:
        kwargs = {i.port_id: values[(i.task_id, i.output)] for i in task.inputs}
        assert all(i.rule is None for i in task.inputs)
        if task.kind == "select":
            folds: FoldSet = kwargs["folds"]
            fold = next(f for f in folds.folds if (f.fold, f.repeat) == task.fold)
            assert task.part is not None
            values[(task.task_id, "rows")] = fold_rows(kwargs["data"], fold, task.part)
            return
        cls = self.registry.get(self.block_of[task.node_id])
        params = self.params(task.node_id)
        if task.kind == "fit":
            values[(task.task_id, STATE)] = cls().fit(**kwargs, params=params)
            return
        meta = cls.metadata()
        ports = [
            p.port_id for p in meta.outputs if not (meta.fitted and p.port_type in _STATE_TYPES)
        ]
        out = cls().apply(**kwargs, params=params)
        for port_id, value in out.items() if len(ports) > 1 else [(ports[0], out)]:
            values[(task.task_id, port_id)] = value

    def cv_predictions(self, data: SpectralDataset) -> NDArray[np.float64]:
        """Out-of-fold predictions of node ``cv`` by position; ``src`` gives ``data``."""
        compiled = self.compile()
        assert compiled.issues == ()
        values: Values = {("src:run", "spectra"): data}
        for task in compiled.tasks:
            if task.node_id not in {"src", "cv"}:
                self.run(task, values)
        plan = compiled.fold_plans["cv"]
        y_pred = np.full(data.n_samples, np.nan)
        folds: FoldSet = values[(plan.folds.task_id, plan.folds.output)]
        for f in folds.folds:
            fold = plan.expand(f.fold, f.repeat)
            for task in fold.tasks:
                self.run(task, values)
            table = values[(fold.validation, "predictions")]
            y_pred[table["row_index"] - _OFFSET] = table["y_pred_y"]
        return y_pred

    def splits(self, data: SpectralDataset) -> list[tuple[NDArray[np.int64], NDArray[np.int64]]]:
        """The ``kfold`` node's folds as scikit-learn (train, test) positions."""
        folds: FoldSet = self.registry.get("validate.kfold")().apply(data, self.params("kfold"))
        return [(f.train - _OFFSET, f.validation - _OFFSET) for f in folds.folds]


@pytest.fixture
def runner(
    registry: Registry, build_pipeline: Callable[..., dict[str, Any]]
) -> Callable[[list[str]], _Runner]:
    with_selection = Registry()
    for block in (*registry, _SelectTopK):
        with_selection.register(block)
    return lambda edges: _Runner(build_pipeline(edges, _PARAMS), with_selection)


def _sk_predict(estimator: Any, X: Any, y: Any, cv: Any) -> NDArray[np.float64]:
    predictions: Any = cross_val_predict(estimator, X, y, cv=cv)
    return np.ravel(predictions)


def _noise() -> SpectralDataset:
    rng = np.random.default_rng(20261127)
    return SpectralDataset(
        rng.normal(size=(_N, _P)),
        Axis(np.arange(_P, dtype=np.float64), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(_N)],
        row_index=np.arange(_N) + _OFFSET,  # row_index is not the position (R40)
        source_id="ds_noise",
        y=rng.normal(size=(_N, 1)),
        y_columns=["y"],
        y_units=["%"],
    )


def test_selection_before_the_folds_inflates_and_is_rejected(
    runner: Callable[[list[str]], _Runner],
) -> None:
    data = _noise()
    assert data.y is not None
    leaky = runner(_LEAKY)
    X_sel = SelectKBest(f_regression, k=_K).fit_transform(data.X, data.y[:, 0])
    pls = PLSRegression(2, scale=False)
    y_pred = _sk_predict(pls, X_sel, data.y[:, 0], leaky.splits(data))
    assert r2_score(data.y[:, 0], y_pred) > 0.3  # the suite can see inflation

    compiled = leaky.compile()
    assert compiled.tasks == ()
    assert [(i.code, i.node_id) for i in compiled.issues] == [
        ("PIPELINE_LEAKAGE", "centre"),
        ("PIPELINE_LEAKAGE", "sel"),
    ]


def test_safe_pipeline_matches_scikit_learn_and_shows_no_inflation(
    runner: Callable[[list[str]], _Runner],
) -> None:
    data = _noise()
    assert data.y is not None
    safe = runner(_SAFE)
    reference = Pipeline(
        [
            ("centre", StandardScaler(with_std=False)),
            ("sel", SelectKBest(f_regression, k=_K)),
            ("pls", PLSRegression(2, scale=False)),
        ]
    )
    expected = _sk_predict(reference, data.X, data.y[:, 0], safe.splits(data))

    y_pred = safe.cv_predictions(data)
    np.testing.assert_allclose(y_pred, expected, rtol=1e-9, atol=1e-12)
    assert r2_score(data.y[:, 0], y_pred) < 0.1
