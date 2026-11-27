# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/cut.py
"""
Block:          Range cut
Class:          preprocess
Ports:          in  -> spectra : Spectra
                out -> spectra : Spectra
Reference:      — (selection of axis points; behaviour as orange-spectroscopy ``Cut``)
METHODS:        docs/METHODS.md#cut
Implementation: own NumPy code (inclusive bounds, several ranges, axis order kept)
Fitted:         No (column selection by axis value; safe inside CV without refitting)
Reviewer:       Quan
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vibechem_core.block import BLOCK_PARAM_INVALID, Block, Param, port
from vibechem_core.data import Axis, SpectralDataset
from vibechem_core.errors import ParamError


@dataclass(frozen=True)
class CutParams:
    # Default keeps every point of any real spectral axis (no-op until ranges are set).
    ranges: tuple[tuple[float, float], ...] = Param(((-1e9, 1e9),))


class Cut(Block):
    block_id = "preprocess.cut"
    version = "1.0.0"
    icon = "glyph-cut"
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = (port("spectra", "Spectra"),)
    params_type = CutParams

    def apply(self, spectra: SpectralDataset, params: CutParams) -> SpectralDataset:
        lam = spectra.axis.values

        # Step 1: For each range, mark the axis points with lo <= lambda <= hi
        # (parse_params already sorted every pair to (lo, hi))
        marks = [(lam >= lo) & (lam <= hi) for lo, hi in params.ranges]

        # Step 2: Union of the marks (overlapping ranges give no duplicate columns)
        keep = np.logical_or.reduce(marks)

        # Step 3: Reject an empty selection
        if not keep.any():
            raise ParamError(BLOCK_PARAM_INVALID, {"param_id": "ranges", "reason": "constraint"})

        # Step 4: Keep the marked columns in their original axis order
        axis = Axis(lam[keep], spectra.axis.unit)
        ranges = [list(pair) for pair in params.ranges]
        return spectra.with_X(spectra.X[:, keep], axis=axis, step=f"Cut(ranges={ranges})")
