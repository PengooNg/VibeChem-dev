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
Reviewer:       Quan

The reference m has two options (METHODS.md#msc): with the ``reference`` input
unconnected, m is the column mean of the training rows; with it connected, m is the
user's reference spectrum (the mean of its rows when it holds more than one).
"""

from __future__ import annotations

from typing import cast

import numpy as np

from vibechem_core.block import Block, NoParams, State, port
from vibechem_core.blocks.preprocess import (
    BLOCK_CONSTANT_SPECTRA,
    BLOCK_MSC_SLOPE_INVALID,
    check_axis,
)
from vibechem_core.data import Axis, AxisUnit, SpectralDataset
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
        if reference is not None:
            check_axis("reference", reference.axis, spectra.axis)
        source = spectra if reference is None else reference
        m = source.X.mean(axis=0)
        kind = "mean" if reference is None else "input"

        # A constant reference cannot be fitted (var(m) = 0 makes [1, m] rank 1)
        if np.ptp(m) == 0:
            raise BlockInputError(BLOCK_CONSTANT_SPECTRA, {"reference": kind})

        values = {"reference": kind, "n_reference_rows": source.n_samples}
        return State(
            values | {"axis_unit": spectra.axis.unit}, {"m": m, "axis": spectra.axis.values}
        )

    def apply(
        self,
        spectra: SpectralDataset,
        params: NoParams,  # noqa: ARG002
        state: State,
        reference: SpectralDataset | None = None,  # noqa: ARG002  (used in fit only)
    ) -> SpectralDataset:
        X = spectra.X
        m = state.arrays["m"]
        fitted_axis = Axis(state.arrays["axis"], cast(AxisUnit, state.values["axis_unit"]))
        check_axis("spectra", spectra.axis, fitted_axis)

        # Step 2: Least-squares fit x_i = a_i + b_i * m for all spectra in one solve
        # (D1: never cov(x, m) / var(m) with mixed ddof)
        design = np.column_stack([np.ones_like(m), m])
        (a, b), *_ = np.linalg.lstsq(design, X.T)

        # Step 3: Reject spectra whose slope b_i is <= 0 (anti-correlated with m). A
        # constant spectrum has b_i = 0 exactly, but rounding can leave a tiny b_i > 0,
        # so constant rows are rejected by testing that all their values are equal.
        bad_rows = np.flatnonzero((b <= 0) | (np.ptp(X, axis=1) == 0))
        if bad_rows.size > 0:
            rows: list[ErrorParam] = [int(r) for r in bad_rows]
            raise BlockInputError(BLOCK_MSC_SLOPE_INVALID, {"rows": rows})

        # Step 4: Remove offset and multiplicative effect: (x_i - a_i) / b_i
        X_msc = (X - a[:, np.newaxis]) / b[:, np.newaxis]

        step = (
            f"MSC(reference={state.values['reference']}, rows={state.values['n_reference_rows']})"
        )
        return spectra.with_X(X_msc, step=step)
