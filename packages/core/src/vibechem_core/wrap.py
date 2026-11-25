# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/wrap.py
"""Wrap a scikit-learn-style transformer as a fitted block (ARCHITECTURE.md §3.1).

A block file subclasses :class:`TransformerBlock`, sets the usual block metadata, a
params dataclass and ``estimator`` (the estimator class), and is done::

    class Autoscale(TransformerBlock):
        block_id = "preprocess.autoscale"
        ...
        params_type = AutoscaleParams
        estimator = StandardScaler

``fit`` builds ``estimator(**estimator_params(params))``, fits it on the training rows'
``X`` and stores every attribute that ``fit`` added (scikit-learn's ``mean_`` style
attributes and private ``_x`` ones) in a :class:`~vibechem_core.block.State`: arrays
as arrays, everything else as JSON values. ``apply`` rebuilds the estimator from the
params, sets those attributes back and calls ``transform``. The estimator object
itself is never pickled (ADR-007); an attribute that is neither an array nor JSON
raises ``TypeError``, and such an estimator needs a block with its own state.

Covered: transformers that use ``X`` only and keep the number of columns (the axis is
kept). Estimators that use ``y`` or change the columns get their own blocks.
The library itself is imported only in the block files that use it (ADR-009).
"""

from __future__ import annotations

import copy
import dataclasses
from typing import Any, ClassVar, Protocol

import numpy as np

from vibechem_core.block import Block, State, port
from vibechem_core.data import SpectralDataset


class Transformer(Protocol):
    """What :class:`TransformerBlock` needs from an estimator."""

    def fit(self, X: Any, /) -> Any: ...
    def transform(self, X: Any, /) -> Any: ...


class TransformerBlock(Block):
    """Base of a fitted block around a scikit-learn-style transformer (see module)."""

    fitted = True
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"), port("transform", "Transform"))
    estimator: ClassVar[type[Transformer]]

    def estimator_params(self, params: Any) -> dict[str, Any]:
        """Constructor arguments of the estimator; default: the params fields."""
        return dataclasses.asdict(params)

    def fit(self, spectra: SpectralDataset, params: Any) -> State:
        estimator = self.estimator(**self.estimator_params(params))
        return estimator_state(estimator, spectra.X)

    def apply(self, spectra: SpectralDataset, params: Any, state: State) -> SpectralDataset:
        kwargs = self.estimator_params(params)
        estimator = restore_estimator(self.estimator(**kwargs), state)
        X = np.asarray(estimator.transform(spectra.X))
        arguments = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        return spectra.with_X(X, step=f"{self.estimator.__name__}({arguments})")


def estimator_state(estimator: Transformer, X: Any) -> State:
    """Fit ``estimator`` on ``X`` and return the attributes ``fit`` added as a State.

    Arrays go to ``State.arrays``; NumPy scalars are converted with ``.item()``; other
    values must be JSON (``TypeError`` otherwise, naming the attribute).
    """
    before = set(vars(estimator))
    estimator.fit(X)
    values: dict[str, object] = {}
    arrays: dict[str, np.ndarray[Any, Any]] = {}
    for name, value in vars(estimator).items():
        if name in before:
            continue
        if isinstance(value, np.ndarray):
            arrays[name] = value
        elif isinstance(value, np.generic):
            values[name] = value.item()
        else:
            values[name] = value
    return State(values, arrays)


def restore_estimator[E: Transformer](estimator: E, state: State) -> E:
    """Set the fitted attributes in ``state`` on a freshly built ``estimator``.

    Values are deep copies; arrays are the state's read-only arrays, so an estimator
    that would change its state fails loudly.
    """
    for name, value in state.values.items():
        setattr(estimator, name, copy.deepcopy(value))
    for name, array in state.arrays.items():
        setattr(estimator, name, array)
    return estimator
