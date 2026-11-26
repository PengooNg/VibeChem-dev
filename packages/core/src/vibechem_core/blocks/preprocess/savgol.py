# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/savgol.py
"""
Block:          Savitzky-Golay smoothing and derivatives
Class:          preprocess
Ports:          in  -> spectra : Spectra
                out -> spectra : Spectra
Reference:      Savitzky & Golay (1964), Anal. Chem. 36(8), 1627-1639;
                Steinier, Termonia & Deltour (1972), Anal. Chem. 44(11), 1906-1909
METHODS:        docs/METHODS.md#savgol
Implementation: wraps scipy.signal.savgol_filter (one call on the whole matrix, axis=1)
Fitted:         No (row-wise transform; safe inside CV without refitting)
Reviewer:       Quan

Edges follow ``mode`` (METHODS.md Q2): ``interp`` (default) fits the window's
polynomial to the first and last ``window`` points and evaluates it at the edge
points; ``nearest``, ``mirror``, ``constant`` (zeros) and ``wrap`` pad the spectrum
and filter as in the interior. Derivatives are per axis unit to the power ``deriv``,
taken in the axis direction (a descending wavenumber axis gives d/dnu, Q3). An axis
whose steps deviate by more than 1 % from the mean step falls back to per-point
derivatives with warning ``BLOCK_AXIS_NOT_UNIFORM`` (N4). The step used ("-3.857 cm-1"
or "1 per point") is written into the ``history`` entry; ``signal_unit`` is unchanged.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import cast

import numpy as np
from scipy.signal import savgol_filter  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import BLOCK_PARAM_INVALID, Block, Param, port
from vibechem_core.blocks.preprocess import BLOCK_AXIS_NOT_UNIFORM
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import ParamError, VibeChemWarning

MODES = ("interp", "nearest", "mirror", "constant", "wrap")
MAX_SPACING_DEVIATION = 0.01  # relative; METHODS.md N4


@dataclass(frozen=True)
class SavitzkyGolayParams:
    window: int = Param(11, min=3, odd_only=True)
    polyorder: int = Param(2, min=0, constraint="polyorder < window")
    deriv: int = Param(0, min=0, constraint="deriv <= polyorder")
    mode: str = Param("interp", choices=MODES)


class SavitzkyGolay(Block):
    block_id = "preprocess.savgol"
    version = "1.0.0"
    icon = "glyph-savgol"
    references = ("savitzky1964", "steinier1972")
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = SavitzkyGolayParams

    def apply(self, spectra: SpectralDataset, params: SavitzkyGolayParams) -> SpectralDataset:
        lam = spectra.axis.values

        # Step 2: Validate w, P, d: bounds, odd w, P < w and d <= P by the parameter
        # schema; w <= p here. Done before Step 1, which needs at least 3 axis points
        if params.window > spectra.n_variables:
            raise ParamError(
                BLOCK_PARAM_INVALID,
                {"param_id": "window", "reason": "constraint", "value": params.window},
            )

        # Step 1: Spacing check (N4): steps within 1 % of the mean signed step -> use the
        # mean step (derivatives per axis unit, Q3); otherwise per point, with a warning
        mean_step = float(lam[-1] - lam[0]) / (lam.size - 1)
        deviation = float(np.abs(np.diff(lam) - mean_step).max()) / abs(mean_step)
        if deviation <= MAX_SPACING_DEVIATION:
            delta = mean_step
            delta_text = f"{delta:.6g} {spectra.axis.unit}"
        else:
            delta = 1.0
            delta_text = "1 per point"
            warnings.warn(
                VibeChemWarning(BLOCK_AXIS_NOT_UNIFORM, {"max_deviation": deviation}),
                stacklevel=2,
            )

        # Step 3: Least-squares polynomial of order P in each moving window of w points;
        # value (d = 0) or d-th derivative at the window centre, edges by mode
        X_sg = cast(
            np.ndarray,
            savgol_filter(
                spectra.X,
                params.window,
                params.polyorder,
                deriv=params.deriv,
                delta=delta,
                axis=1,
                mode=params.mode,
            ),
        )

        step = (
            f"SavitzkyGolay(window={params.window}, polyorder={params.polyorder}, "
            f"deriv={params.deriv}, mode={params.mode}, delta={delta_text})"
        )
        return spectra.with_X(X_sg, step=step)
