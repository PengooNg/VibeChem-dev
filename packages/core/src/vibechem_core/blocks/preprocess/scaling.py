# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/scaling.py
"""
Block:          Mean-centring, autoscaling and Pareto scaling (column scalings)
Class:          preprocess
Ports:          in  -> spectra   : Spectra
                out -> spectra   : Spectra
                out -> transform : Transform
Reference:      van den Berg et al. (2006), BMC Genomics 7, 142
METHODS:        docs/METHODS.md#mean-centre, #autoscale, #pareto, #y-scaling
Implementation: own NumPy code (StandardScaler uses ddof 0, METHODS.md N2)
Fitted:         Yes (column means and SDs learned in ``fit`` from training rows only)
Reviewer:       Quan

The three blocks share one implementation: x~ = (x - mean) / s**power with s the
training column SD (ddof 1) and power 0 (mean-centring), 1 (autoscaling) or 0.5
(Pareto). The ``# Step`` numbers follow METHODS.md#autoscale; mean-centring skips
Steps 2-3. ``target = y`` scales the responses instead of X (METHODS.md#y-scaling);
:func:`inverse_y` maps scaled predictions back to original Y units.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from typing import ClassVar, cast

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, Block, Param, State, port
from vibechem_core.blocks.preprocess import BLOCK_CONSTANT_COLUMNS, check_axis
from vibechem_core.data import Axis, AxisUnit, SpectralDataset
from vibechem_core.errors import BlockInputError, ErrorParam, VibeChemWarning


@dataclass(frozen=True)
class ScalingParams:
    target: str = Param("X", choices=("X", "y"))


class _ColumnScaling(Block):
    version = "1.0.0"
    references = ("vandenberg2006scaling",)
    fitted = True
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"), port("transform", "Transform"))
    params_type = ScalingParams
    power: ClassVar[float]

    def fit(self, spectra: SpectralDataset, params: ScalingParams) -> State:
        values = spectra.X if params.target == "X" else _y(spectra, None)

        # Step 1: Column means of the training rows
        mean = values.mean(axis=0)

        # Step 2: Column SDs (ddof 1), raised to ``power``. Step 3: a column whose
        # training values are all equal (also n = 1) gets scale 1, with a warning (N3)
        scale = np.ones_like(mean)
        if self.power:
            flat = np.ptp(values, axis=0) == 0
            if flat.any():
                columns: list[ErrorParam] = [int(j) for j in np.flatnonzero(flat)]
                warnings.warn(
                    VibeChemWarning(BLOCK_CONSTANT_COLUMNS, {"columns": columns}), stacklevel=2
                )
            scale[~flat] = values[:, ~flat].std(axis=0, ddof=1) ** self.power

        if params.target == "X":
            return State(
                {"target": "X", "axis_unit": spectra.axis.unit},
                {"mean": mean, "scale": scale, "axis": spectra.axis.values},
            )
        return State(
            {"target": "y", "y_columns": list(spectra.y_columns)}, {"mean": mean, "scale": scale}
        )

    def apply(
        self,
        spectra: SpectralDataset,
        params: ScalingParams,  # noqa: ARG002  (the target is read from the state)
        state: State,
    ) -> SpectralDataset:
        mean, scale = state.arrays["mean"], state.arrays["scale"]
        target = state.values["target"]
        step = f"{type(self).__name__}(target={target})"

        # Step 4: (values - training mean) / training scale
        if target == "X":
            fitted_axis = Axis(state.arrays["axis"], cast(AxisUnit, state.values["axis_unit"]))
            check_axis("spectra", spectra.axis, fitted_axis)
            return spectra.with_X((spectra.X - mean) / scale, step=step)
        y = _y(spectra, cast(list[str], state.values["y_columns"]))
        return replace(spectra, y=(y - mean) / scale, history=(*spectra.history, step))


class MeanCentre(_ColumnScaling):
    block_id = "preprocess.mean_centre"
    icon = "glyph-mean-centre"
    power = 0.0


class Autoscale(_ColumnScaling):
    block_id = "preprocess.autoscale"
    icon = "glyph-autoscale"
    power = 1.0


class Pareto(_ColumnScaling):
    block_id = "preprocess.pareto"
    icon = "glyph-pareto"
    power = 0.5


def inverse_y(state: State, y_scaled: NDArray[np.float64]) -> NDArray[np.float64]:
    """Map scaled responses (e.g. predictions, shape (n, k)) back to original Y units."""
    if state.values["target"] != "y":
        raise ValueError("inverse_y needs the state of a scaling block fitted with target = y")
    k = state.arrays["scale"].size
    if y_scaled.ndim != 2 or y_scaled.shape[1] != k:  # (n, 1) would broadcast to (n, k)
        raise ValueError(f"inverse_y expects shape (n, {k}), got {y_scaled.shape}")
    return y_scaled * state.arrays["scale"] + state.arrays["mean"]


def _y(spectra: SpectralDataset, expected: list[str] | None) -> NDArray[np.float64]:
    """``spectra.y``; ``BLOCK_INPUT_REQUIREMENT_MISSING`` when absent or when its columns
    differ from the fitted ``expected`` ones (a k = 1 y would broadcast silently)."""
    if spectra.y is None or (expected is not None and list(spectra.y_columns) != expected):
        params: dict[str, ErrorParam] = {"port_id": "spectra", "requirement": "y"}
        if expected is not None:
            params["expected"] = ", ".join(expected)
        raise BlockInputError(BLOCK_INPUT_REQUIREMENT_MISSING, params)
    return spectra.y
