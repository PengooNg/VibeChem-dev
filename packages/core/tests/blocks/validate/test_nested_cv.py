# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/blocks/validate/test_nested_cv.py
"""``validate.nested_cv`` (docs/METHODS.md#nested-cv) on outer fold models fitted by hand,
the ``block_ref`` parameter and the ``inner_folds`` check; the engine runner with the inner
searches is tested against scikit-learn in ``packages/engine/tests/runners/``."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest
from numpy.typing import NDArray
from sklearn.cross_decomposition import PLSRegression  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import SearchOption, parse_params
from vibechem_core.blocks.model.pls import PLS, PLSParams
from vibechem_core.blocks.model.plsda import PLSDA, PLSDAParams
from vibechem_core.blocks.preprocess.snv import SNV
from vibechem_core.blocks.validate.cv import CrossValidation, FoldRun
from vibechem_core.blocks.validate.folds import KFold, ShuffledFoldParams
from vibechem_core.blocks.validate.nested_cv import (
    LV_ONLY,
    InnerChoice,
    NestedCV,
    NestedCVParams,
    check_inner_folds,
)
from vibechem_core.data import Axis, FoldSet, SpectralDataset
from vibechem_core.errors import ParamError
from vibechem_core.registry import Registry


def dataset(n: int = 24) -> SpectralDataset:
    rng = np.random.default_rng(3)
    X = rng.normal(size=(n, 6))
    y = X[:, :2] @ rng.normal(size=(2, 1)) + 0.3 * rng.normal(size=(n, 1))
    return SpectralDataset(
        X,
        Axis(np.arange(6.0), "nm"),
        signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n)[::-1] + 40,  # offset and reversed
        source_id="ds",
        y=y,
        y_columns=["y0"],
        y_units=["%"],
    )


def test_block_ref_parameter_parses_and_defaults() -> None:
    assert parse_params(NestedCVParams, {}).inner_folds == SearchOption("validate.kfold")
    assert parse_params(NestedCVParams, {}).search_space == LV_ONLY
    got = parse_params(NestedCVParams, {"inner_folds": {"block_id": "validate.loo"}})
    assert got.inner_folds == SearchOption("validate.loo", {})
    bads: list[object] = ["validate.loo", {"block_id": 3}, {"block_id": "a.b", "extra": 1}, {"block_id": "a.b", "params": []}]  # fmt: skip
    for bad in bads:
        with pytest.raises(ParamError) as exc:
            parse_params(NestedCVParams, {"inner_folds": bad})
        assert (exc.value.params["param_id"], exc.value.params["reason"]) == ("inner_folds", "type")
    params = cast(list[dict[str, Any]], NestedCV.metadata().to_detail_dict()["params"])
    entry = next(p for p in params if p["param_id"] == "inner_folds")
    assert entry["type"] == "block_ref"
    assert entry["default"] == {"block_id": "validate.kfold", "params": {}}


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        (SearchOption("validate.nope"), {"reason": "unknown_block", "value": "validate.nope"}),
        (SearchOption("preprocess.snv"), {"reason": "not_a_fold_block", "value": "preprocess.snv"}),
        (SearchOption("validate.cv"), {"reason": "not_a_fold_block", "value": "validate.cv"}),
        (SearchOption("validate.kfold", {"k": 1}), {"reason": "below_min", "value": "k"}),
        (SearchOption("validate.kfold", {"kk": 3}), {"reason": "unknown", "value": "kk"}),
    ],
)
def test_inner_folds_must_be_a_registered_fold_block(ref: SearchOption, expected: dict[str, Any]) -> None:  # fmt: skip
    registry = Registry()
    for block in (KFold, SNV, CrossValidation):
        registry.register(block)
    with pytest.raises(ParamError) as exc:
        check_inner_folds(ref, registry)
    assert exc.value.params == {"param_id": "inner_folds", **expected}
    check_inner_folds(SearchOption("validate.kfold", {"k": 3}), registry)  # a fold block passes


def test_outer_predictions_use_each_folds_own_lv_count() -> None:
    data = dataset()
    folds: FoldSet = KFold().apply(data, parse_params(ShuffledFoldParams, {"k": 3, "shuffle": False}))  # fmt: skip
    pls = parse_params(PLSParams, {"n_components": 4})
    runs = [FoldRun(f, PLS().fit(data.rows(f.train), pls), data.rows(f.validation)) for f in folds.folds]  # fmt: skip
    choices = [InnerChoice(0, "[]", n, 0.1 * n) for n in (1, 3, 2)]
    out = NestedCV().apply(PLS().fit(data, pls), folds, parse_params(NestedCVParams, {}), runs, choices)  # fmt: skip

    # Reference: scikit-learn PLS at each fold's LV count on positions (independent)
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    y = cast(NDArray[np.float64], data.y)[:, 0]
    sq: list[float] = []
    for f, c in zip(folds.folds, choices, strict=True):
        tr = [position[r] for r in f.train.tolist()]
        va = [position[r] for r in f.validation.tolist()]
        model: Any = PLSRegression(n_components=c.n_lv, scale=False)
        model.fit(data.X[tr], y[tr])
        sq += ((model.predict(data.X[va]).ravel() - y[va]) ** 2).tolist()
    assert out.kind == "nested_cv"
    assert out.metrics["rmsecv"] == pytest.approx(np.sqrt(np.mean(sq)), rel=1e-10)
    assert "n_lv" not in out.metrics
    predictions = cast(dict[str, NDArray[Any]], out.predictions)
    assert predictions["n_lv"].tolist() == [1] * 8 + [3] * 8 + [2] * 8
    assert [o["n_lv"] for o in out.details["outer"]] == [1, 3, 2]
    assert out.details["inner_folds"] == {"block_id": "validate.kfold", "params": {}}


def test_a_fold_lv_count_above_the_fold_model_is_refused() -> None:
    data = dataset()
    folds: FoldSet = KFold().apply(data, parse_params(ShuffledFoldParams, {"k": 3, "shuffle": False}))  # fmt: skip
    pls = parse_params(PLSParams, {"n_components": 2})
    runs = [FoldRun(f, PLS().fit(data.rows(f.train), pls), data.rows(f.validation)) for f in folds.folds]  # fmt: skip
    with pytest.raises(ValueError, match="n_lv_per_fold"):
        NestedCV().apply(PLS().fit(data, pls), folds, parse_params(NestedCVParams, {}), runs,
                         [InnerChoice(0, "[]", n, 0.0) for n in (1, 3, 2)])  # fmt: skip


def test_plsda_outer_metrics_use_each_folds_own_lv_count() -> None:
    labels = ["a", "b", "c"] * 8 + ["a", "c", "a"]
    rng = np.random.default_rng(11)
    centre = rng.normal(size=(3, 6))
    X = centre[[["a", "b", "c"].index(c) for c in labels]] + 0.8 * rng.normal(size=(27, 6))
    data = SpectralDataset(
        X, Axis(np.arange(6.0), "nm"), signal_unit="absorbance",
        sample_ids=[f"s{i}" for i in range(27)], row_index=np.arange(27)[::-1] + 40,
        source_id="ds", classes=labels, class_column="type",
    )  # fmt: skip
    folds: FoldSet = KFold().apply(data, parse_params(ShuffledFoldParams, {"k": 3, "shuffle": False}))  # fmt: skip
    params = parse_params(PLSDAParams, {"n_components": 4})
    runs = [FoldRun(f, PLSDA().fit(data.rows(f.train), params), data.rows(f.validation)) for f in folds.folds]  # fmt: skip
    choices = [InnerChoice(0, "[]", n, 0.0) for n in (2, 1, 3)]
    out = NestedCV().apply(PLSDA().fit(data, params), folds, parse_params(NestedCVParams, {}), runs, choices)  # fmt: skip

    # Reference: scikit-learn PLS on the indicator matrix at each fold's LV count, argmax
    position = {r: i for i, r in enumerate(data.row_index.tolist())}
    names, truth = np.array(["a", "b", "c"]), np.array(labels)
    Y = (truth[:, None] == names[None, :]).astype(float)
    pred = np.empty(27, dtype=object)
    for f, c in zip(folds.folds, choices, strict=True):
        tr = [position[r] for r in f.train.tolist()]
        va = [position[r] for r in f.validation.tolist()]
        pls: Any = PLSRegression(n_components=c.n_lv, scale=False, max_iter=10_000, tol=1e-20)
        pls.fit(data.X[tr], Y[tr])
        pred[va] = names[np.asarray(pls.predict(data.X[va])).argmax(axis=1)]
    assert out.metrics["accuracy_cv"] == pytest.approx(float((pred == truth).mean()))
    assert set(out.details["per_class"]) == {"a", "b", "c"}
