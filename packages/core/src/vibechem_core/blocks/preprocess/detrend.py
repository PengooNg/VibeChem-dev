# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/detrend.py
"""
Block:          Detrend (polynomial in the axis value)
Class:          preprocess
Ports:          in  -> spectra : Spectra
                out -> spectra : Spectra
Reference:      Barnes, Dhanoa & Lister (1989), Appl. Spectrosc. 43(5), 772-777
METHODS:        docs/METHODS.md#detrend
Implementation: own NumPy code (np.linalg.lstsq); a 4-line solve, no dependency needed
Fitted:         No (row-wise transform; safe inside CV without refitting)
Reviewers:      algorithm -> Quan | structure -> K
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vibechem_core.block import BLOCK_PARAM_INVALID, Block, Param, port
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import ParamError


@dataclass(frozen=True)
class DetrendParams:
    degree: int = Param(2, min=1)


class Detrend(Block):
    block_id = "preprocess.detrend"
    version = "1.0.0"
    icon = "glyph-detrend"
    references = ("barnes1989snv",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = DetrendParams

    def apply(self, spectra: SpectralDataset, params: DetrendParams) -> SpectralDataset:
        X = spectra.X
        degree = params.degree

        # The polynomial needs fewer coefficients than points (constraint D < p)
        if degree >= spectra.n_variables:
            raise ParamError(
                BLOCK_PARAM_INVALID,
                {"param_id": "degree", "reason": "constraint", "value": degree},
            )

        # Step 1: Map the real axis (never the index) linearly to u in [-1, 1]
        lam = spectra.axis.values
        u = 2.0 * (lam - lam.min()) / (lam.max() - lam.min()) - 1.0

        # Step 2: Vandermonde matrix [1, u, u^2, ..., u^D]  (p x (D + 1))
        V = np.vander(u, degree + 1, increasing=True)

        # Step 3: Least-squares polynomial coefficients for all spectra at once
        coef, *_ = np.linalg.lstsq(V, X.T)

        # Step 4: Subtract each fitted curve from its spectrum
        X_detrended = X - (V @ coef).T

        return spectra.with_X(X_detrended, step=f"Detrend(degree={degree})")
