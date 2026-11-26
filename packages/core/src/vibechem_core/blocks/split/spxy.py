# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/split/spxy.py
"""
Block:          SPXY hold-out split (Kennard-Stone on a joint X-y distance)
Class:          split
Ports:          in  -> spectra : Spectra (requires y)
                out -> folds   : Folds
                out -> train   : Spectra
                out -> test    : Spectra
Reference:      Galvao et al. (2005), Talanta 67(4), 736-740
METHODS:        docs/METHODS.md#spxy, #kennard-stone, #group-aware-split
Implementation: port of the pengoo SPXY distance (Dx/max + Dy/max), Kennard-Stone loop
                from ``split.kennard_stone``
Fitted:         No (row selection is a design step; nothing is fitted on test rows)
Reviewer:       Quan

``start = nearest_mean`` starts with the row whose joint distance to the mean,
||z - mean z|| / max d_x + ||y - mean y|| / max d_y, is smallest. With groups, each
group is replaced by its mean spectrum and mean y.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial.distance import pdist, squareform

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING, Block, port
from vibechem_core.blocks.split import (
    BLOCK_CONSTANT_RESPONSE,
    SPLIT_OUTPUTS,
    SplitOutputs,
    holdout,
    n_test_units,
    sampling_units,
    unit_means,
)
from vibechem_core.blocks.split.kennard_stone import KennardStoneParams, distance_space, ks_order
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError


class SPXY(Block):
    block_id = "split.spxy"
    version = "1.0.0"
    icon = "glyph-spxy"
    references = ("galvao2005spxy", "kennard1969", "esbensen2010validation")
    fitted = False
    inputs = (port("spectra", "Spectra", requires=("y",)),)
    outputs = SPLIT_OUTPUTS
    params_type = KennardStoneParams

    def apply(self, spectra: SpectralDataset, params: KennardStoneParams) -> SplitOutputs:
        if spectra.y is None:  # the engine checks ``requires``; direct calls still need y
            raise BlockInputError(
                BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "y"}
            )
        units = sampling_units(spectra, params.group_aware)
        X, y = unit_means(spectra.X, units), unit_means(spectra.y, units)
        n_test = n_test_units(params, X.shape[0])

        # Step 1: d_x on the Kennard-Stone distance space
        z = distance_space(X, params)
        # shortcut: full n x n matrices, add an O(n) incremental mode when larger sets appear
        d_x = squareform(pdist(z))

        # Step 2: d_y = Euclidean distance between response rows
        d_y = squareform(pdist(y))

        # Step 3: Normalise each by its maximum (all y equal -> error, no fall-back to KS)
        max_x, max_y = float(d_x.max()), float(d_y.max())
        if max_y == 0:
            raise BlockInputError(BLOCK_CONSTANT_RESPONSE, {"port_id": "spectra"})
        max_x = max_x or 1.0  # identical spectra: the x term is 0 for every pair

        # Step 4: Sum
        d_xy = d_x / max_x + d_y / max_y
        to_mean = (
            np.linalg.norm(z - z.mean(axis=0), axis=1) / max_x
            + np.linalg.norm(y - y.mean(axis=0), axis=1) / max_y
        )

        # Step 5: Kennard-Stone order on d_xy; the first n_train units form the training set
        order = ks_order(d_xy, to_mean, params.start)
        test_units = np.zeros(X.shape[0], dtype=bool)
        test_units[order[X.shape[0] - n_test :]] = True
        step = f"SPXY(start={params.start}, space={params.space})"
        return holdout(spectra, test_units, units, params.group_aware, None, step)
