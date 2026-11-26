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
Reviewers:      algorithm -> Quan | structure -> K

Edges follow ``mode`` (METHODS.md Q2): ``interp`` (default) fits the window's
polynomial to the first and last ``window`` points and evaluates it at the edge
points; ``nearest``, ``mirror``, ``constant`` (zeros) and ``wrap`` pad the spectrum
and filter as in the interior. Derivatives are per axis unit to the power ``deriv``,
taken in the axis direction (a descending wavenumber axis gives d/dnu, Q3). The axis
step used is written into the ``history`` entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
from scipy.signal import savgol_filter  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import BLOCK_PARAM_INVALID, Block, Param, port
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import ParamError

MODES = ("interp", "nearest", "mirror", "constant", "wrap")


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

        # Step 1: Axis step = mean signed step (derivatives per axis unit, Q3)
        delta = float(lam[-1] - lam[0]) / (lam.size - 1)
        delta_text = f"{delta:.6g} {spectra.axis.unit}"

        # Step 2: The window must fit in the spectrum (constraint w <= p; w, P, d were
        # checked by the parameter schema)
        if params.window > spectra.n_variables:
            raise ParamError(
                BLOCK_PARAM_INVALID,
                {"param_id": "window", "reason": "constraint", "value": params.window},
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
