# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/tests/test_wrap.py
"""Tests for ``vibechem_core.wrap``: scikit-learn transformers as fitted blocks."""

# scikit-learn ships no type stubs.
# pyright: reportMissingTypeStubs=false

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

from vibechem_core.block import NoParams, Param, State, load_state, save_state
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.registry import Registry
from vibechem_core.wrap import TransformerBlock, estimator_state, restore_estimator


def make_dataset(X: list[list[float]]) -> SpectralDataset:
    x = np.asarray(X, dtype=np.float64)
    n, p = x.shape
    return SpectralDataset(
        x,
        Axis(np.arange(p), "index"),
        signal_unit="arbitrary",
        sample_ids=[f"s{i}" for i in range(n)],
        row_index=np.arange(n),
        source_id="ds_test",
    )


@dataclass(frozen=True)
class ScaleParams:
    with_mean: bool = Param(True)
    with_std: bool = Param(True)


class Scale(TransformerBlock):
    """StandardScaler wrapped as a block (test only)."""

    block_id = "testing.scale"
    version = "1.0.0"
    icon = "glyph-dummy"
    params_type = ScaleParams
    estimator = StandardScaler


TRAIN = [[1.0, 10.0], [3.0, 30.0], [5.0, 20.0]]
OTHER = [[100.0, 0.0]]


def test_wrapped_transformer_fits_on_train_rows_and_applies_to_other_rows() -> None:
    data = make_dataset([*TRAIN, *OTHER])
    block = Scale()
    state = block.fit(spectra=data.subset([0, 1, 2]), params=ScaleParams())
    # Hand calculation on the training rows: means (3, 20), population std (ddof=0)
    # sqrt(8/3) and sqrt(200/3).
    std = np.sqrt([8 / 3, 200 / 3])
    np.testing.assert_allclose(state.arrays["mean_"], [3.0, 20.0], rtol=1e-15)
    np.testing.assert_allclose(state.arrays["scale_"], std, rtol=1e-15)
    assert state.values["n_features_in_"] == 2
    assert state.values["n_samples_seen_"] == 3
    out = block.apply(spectra=data.subset([3]), params=ScaleParams(), state=state)
    np.testing.assert_allclose(out.X, [[97.0 / std[0], -20.0 / std[1]]], rtol=1e-14)
    assert list(out.row_index) == [3]
    assert out.history == ("StandardScaler(with_mean=True, with_std=True)",)
    np.testing.assert_array_equal(data.X, [*TRAIN, *OTHER])  # input unchanged


def test_wrapped_transformer_round_trips_state(tmp_path: Path) -> None:
    data = make_dataset([*TRAIN, *OTHER])
    block = Scale()
    for params in (ScaleParams(), ScaleParams(with_std=False)):
        state = block.fit(spectra=data.subset([0, 1, 2]), params=params)
        directory = tmp_path / str(params.with_std)
        save_state(state, directory)
        loaded = load_state(directory)
        assert dict(loaded.values) == dict(state.values)
        assert list(loaded.arrays) == list(state.arrays)
        expected = block.apply(spectra=data, params=params, state=state)
        actual = block.apply(spectra=data, params=params, state=loaded)
        np.testing.assert_array_equal(actual.X, expected.X)
    assert loaded.values["scale_"] is None  # with_std=False: stored as JSON null


def test_wrapped_transformer_is_a_valid_fitted_block() -> None:
    meta = Scale.metadata()
    assert meta.fitted
    assert [p.port_id for p in meta.outputs] == ["spectra", "transform"]
    assert [name for name, _ in meta.params] == ["with_mean", "with_std"]
    registry = Registry()
    registry.register(Scale)
    assert registry.get("testing.scale") is Scale


class _Private:
    """Smallest scikit-learn-style transformer with a private fitted attribute."""

    def __init__(self, factor: float = 2.0) -> None:
        self.factor = factor

    def fit(self, X: Any) -> Self:
        self._total = float(np.sum(np.asarray(X, dtype=np.float64)))
        self.shape_ = list(np.shape(X))
        return self

    def transform(self, X: Any) -> Any:
        return np.asarray(X) * self.factor + self._total


def test_state_holds_every_attribute_added_by_fit_and_restores_it() -> None:
    state = estimator_state(_Private(3.0), np.ones((2, 2)))
    assert dict(state.values) == {"_total": 4.0, "shape_": [2, 2]}  # not the param `factor`
    restored = restore_estimator(_Private(3.0), state)
    np.testing.assert_array_equal(restored.transform(np.zeros((1, 2))), [[4.0, 4.0]])
    restored.shape_.append(9)
    assert state.values["shape_"] == [2, 2]  # restored values are copies


class _Unsaveable(_Private):
    def fit(self, X: Any) -> Self:
        self.rng_ = np.random.default_rng(0)
        return super().fit(X)


def test_attribute_that_is_not_an_array_or_json_raises() -> None:
    with pytest.raises(TypeError, match=r"'rng_' is a Generator, not JSON"):
        estimator_state(_Unsaveable(), np.ones((1, 1)))


class _Writes(_Private):
    def fit(self, X: Any) -> Self:
        self.offset_ = np.zeros(1)
        return super().fit(X)

    def transform(self, X: Any) -> Any:
        self.offset_ += 1.0
        return np.asarray(X)


def test_restored_arrays_are_read_only() -> None:
    state = estimator_state(_Writes(), np.ones((1, 1)))
    with pytest.raises(ValueError, match="read-only"):
        restore_estimator(_Writes(), state).transform(np.ones((1, 1)))
    np.testing.assert_array_equal(state.arrays["offset_"], [0.0])


def test_no_params_gives_no_constructor_arguments() -> None:
    class Plain(TransformerBlock):
        estimator = StandardScaler

    assert Plain().estimator_params(NoParams()) == {}
    assert isinstance(Plain().fit(spectra=make_dataset(TRAIN), params=NoParams()), State)
