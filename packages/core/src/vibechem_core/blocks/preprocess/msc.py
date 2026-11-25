# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/msc.py
"""
Block:          Multiplicative Scatter Correction (MSC)
Class:          preprocess
Ports:          in  -> spectra   : Spectra
                in  -> reference : Spectra (optional, axis_match: spectra)
                out -> spectra   : Spectra
                out -> transform : Transform
Reference:      Geladi, MacDougall & Martens (1985), Appl. Spectrosc. 39(3), 491-500
METHODS:        docs/METHODS.md#msc
Implementation: port of pengoo ``msc`` with the D1 fix (one least-squares solve)
Fitted:         Yes (reference spectrum m learned in ``fit`` from training rows only)
Reviewers:      algorithm -> Quan | structure -> K

The reference m has two options (METHODS.md#msc): with the ``reference`` input
unconnected, m is the column mean of the training rows; with it connected, m is the
user's reference spectrum (the mean of its rows when it holds more than one).
"""

from __future__ import annotations

import numpy as np

from vibechem_core.block import Block, NoParams, State, port
from vibechem_core.blocks.preprocess import BLOCK_CONSTANT_SPECTRA, BLOCK_MSC_SLOPE_INVALID
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError, ErrorParam


class MSC(Block):
    block_id = "preprocess.msc"
    version = "1.0.0"
    icon = "glyph-msc"
    references = ("geladi1985msc",)
    fitted = True
    inputs = (
        port("spectra", "Spectra"),
        port("reference", "Spectra", required=False, axis_match="spectra"),
    )
    outputs = (port("spectra", "Spectra"), port("transform", "Transform"))

    def fit(
        self,
        spectra: SpectralDataset,
        params: NoParams,  # noqa: ARG002
        reference: SpectralDataset | None = None,
    ) -> State:
        # Step 1: Reference spectrum m: column mean of the training rows, or the user's
        # reference input (mean of its rows; one row = that spectrum)
        source = spectra if reference is None else reference
        m = source.X.mean(axis=0)
        kind = "mean" if reference is None else "input"

        # A constant reference cannot be fitted (var(m) = 0 makes [1, m] rank 1)
        if np.ptp(m) == 0:
            raise BlockInputError(BLOCK_CONSTANT_SPECTRA, {"reference": kind})

        return State({"reference": kind, "n_reference_rows": source.n_samples}, {"m": m})

    def apply(
        self,
        spectra: SpectralDataset,
        params: NoParams,  # noqa: ARG002
        state: State,
        reference: SpectralDataset | None = None,  # noqa: ARG002  (used in fit only)
    ) -> SpectralDataset:
        X = spectra.X
        m = state.arrays["m"]

        # Step 2: Least-squares fit x_i = a_i + b_i * m for all spectra in one solve
        # (D1: never cov(x, m) / var(m) with mixed ddof). The solve is done on centred
        # m and x, which gives the same a_i, b_i as [1, m] but an exact b_i = 0 for a
        # constant spectrum (uncentred, rounding leaves b_i ~ 1e-16 > 0); then
        # a_i = mean(x_i) - b_i * mean(m).
        m_mean = m.mean()
        x_mean = X.mean(axis=1)
        (b,), *_ = np.linalg.lstsq((m - m_mean)[:, np.newaxis], (X - x_mean[:, np.newaxis]).T)
        a = x_mean - b * m_mean

        # Step 3: Reject spectra whose slope b_i is <= 0 (anti-correlated with m)
        bad_rows = np.flatnonzero(b <= 0)
        if bad_rows.size > 0:
            rows: list[ErrorParam] = [int(r) for r in bad_rows]
            raise BlockInputError(BLOCK_MSC_SLOPE_INVALID, {"rows": rows})

        # Step 4: Remove offset and multiplicative effect: (x_i - a_i) / b_i
        X_msc = (X - a[:, np.newaxis]) / b[:, np.newaxis]

        step = (
            f"MSC(reference={state.values['reference']}, rows={state.values['n_reference_rows']})"
        )
        return spectra.with_X(X_msc, step=step)
