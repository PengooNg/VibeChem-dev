# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/snv.py
"""
Block:          Standard Normal Variate (SNV)
Class:          preprocess
Ports:          in  -> spectra : Spectra
                out -> spectra : Spectra
Reference:      Barnes, Dhanoa & Lister (1989), Appl. Spectrosc. 43(5), 772-777
METHODS:        docs/METHODS.md#snv
Implementation: own NumPy code (simpler than wrapping; see TECH_STACK.md §11)
Fitted:         No (row-wise transform; safe inside CV without refitting)
Reviewers:      algorithm -> Quan | structure -> K
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vibechem_core.block import Block, Param, port
from vibechem_core.blocks.preprocess import BLOCK_CONSTANT_SPECTRA
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError, ErrorParam


@dataclass(frozen=True)
class SNVParams:
    ddof: int = Param(1, choices=(0, 1))


class SNV(Block):
    block_id = "preprocess.snv"
    version = "1.0.0"
    icon = "glyph-snv"
    references = ("barnes1989snv",)
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = SNVParams

    def apply(self, spectra: SpectralDataset, params: SNVParams) -> SpectralDataset:
        X = spectra.X

        # Step 1: Mean of each spectrum over all axis points (one value per row)
        row_mean = X.mean(axis=1, keepdims=True)

        # Step 2: Standard deviation of each spectrum; with p <= ddof it is undefined,
        # so every row counts as flat in Step 3 (METHODS.md#snv: p = 1, ddof = 1)
        if X.shape[1] > params.ddof:
            row_std = X.std(axis=1, ddof=params.ddof, keepdims=True)
        else:
            row_std = np.zeros_like(row_mean)

        # Step 3: Reject flat spectra (std = 0 would divide by zero); no +1e-10 guard
        flat_rows = np.flatnonzero(row_std.ravel() == 0)
        if flat_rows.size > 0:
            rows: list[ErrorParam] = [int(r) for r in flat_rows]
            raise BlockInputError(BLOCK_CONSTANT_SPECTRA, {"rows": rows})

        # Step 4: Centre and scale each spectrum individually
        X_snv = (X - row_mean) / row_std

        return spectra.with_X(X_snv, step=f"SNV(ddof={params.ddof})")
