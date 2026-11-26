# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/split/kennard_stone.py
"""
Block:          Kennard-Stone hold-out split
Class:          split
Ports:          in  -> spectra : Spectra
                out -> folds   : Folds
                out -> train   : Spectra
                out -> test    : Spectra
Reference:      Kennard & Stone (1969), Technometrics 11(1), 137-148;
                Daszykowski, Walczak & Massart (2002), Anal. Chim. Acta 468, 91-103
METHODS:        docs/METHODS.md#kennard-stone, #group-aware-split
Implementation: port of pengoo ``_ks_order`` (vectorised min-distance update), PCA
                scores by NumPy SVD; cross-checked against the ``kennard-stone`` package
Fitted:         No (row selection is a design step; nothing is fitted on test rows)
Reviewer:       Quan

The first n_train units of the selection order form the training set. With
``group_aware`` and ``group_ids``, each group is replaced by its mean spectrum
before Step 1 and the selected groups are expanded back to their rows.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.distance import pdist, squareform

from vibechem_core.block import Block, Param, port
from vibechem_core.blocks.split import (
    SPLIT_OUTPUTS,
    SplitOutputs,
    SplitParams,
    holdout,
    n_test_units,
    sampling_units,
    unit_means,
)
from vibechem_core.data import SpectralDataset


@dataclass(frozen=True)
class KennardStoneParams(SplitParams):
    start: str = Param("most_distant", choices=("most_distant", "nearest_mean"))
    space: str = Param("x", choices=("x", "pca"))
    variance: float = Param(0.99, min=0.01, max=1.0, visible_if=("space", ("pca",)))


def distance_space(X: NDArray[np.float64], params: KennardStoneParams) -> NDArray[np.float64]:
    """Raw rows, or PCA scores of the centred rows with the fewest components whose
    explained variance exceeds ``variance`` (scikit-learn's rule; all components at 1)."""
    if params.space == "x":
        return X
    U, s, _ = np.linalg.svd(X - X.mean(axis=0), full_matrices=False)
    ratio = np.cumsum(s**2) / max(float(np.sum(s**2)), np.finfo(float).tiny)
    k = (
        s.size
        if params.variance >= 1
        else int(np.searchsorted(ratio, params.variance, "right")) + 1
    )
    return U[:, : min(k, s.size)] * s[: min(k, s.size)]


def ks_order(D: NDArray[np.float64], to_mean: NDArray[np.float64], start: str) -> NDArray[np.intp]:
    """Kennard-Stone selection order on the distance matrix ``D`` (ties: lowest index).

    ``to_mean`` is each row's distance to the mean, used by ``start = nearest_mean``.
    """
    n = int(D.shape[0])
    if n <= 2:
        return np.arange(n, dtype=np.intp)
    if start == "most_distant":
        i, j = (int(v) for v in np.unravel_index(int(np.argmax(D)), D.shape))
        first = [i, j] if i != j else [0, 1]  # all distances 0: argmax is the diagonal (0, 0)
    else:
        first = [int(np.argmin(to_mean))]
    order = np.empty(n, dtype=np.intp)
    order[: len(first)] = first
    min_d = D[first].min(axis=0)
    min_d[first] = -np.inf
    for k in range(len(first), n):
        nxt = int(np.argmax(min_d))
        order[k] = nxt
        min_d = np.minimum(min_d, D[nxt])
        min_d[nxt] = -np.inf
    return order


class KennardStone(Block):
    block_id = "split.kennard_stone"
    version = "1.0.0"
    icon = "glyph-kennard-stone"
    references = ("kennard1969", "daszykowski2002", "esbensen2010validation")
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = SPLIT_OUTPUTS
    params_type = KennardStoneParams

    def apply(self, spectra: SpectralDataset, params: KennardStoneParams) -> SplitOutputs:
        units = sampling_units(spectra, params.group_aware)
        X = unit_means(spectra.X, units)
        n_test = n_test_units(params, X.shape[0])

        # Step 1: Distance space z (raw X or PCA scores of all split rows)
        z = distance_space(X, params)

        # Step 2: Euclidean distance matrix
        # shortcut: full n x n matrix (n = 5000 -> 200 MB), add an O(n) incremental mode when larger sets appear
        D = squareform(pdist(z))

        # Step 3 + 4: Start (most distant pair or nearest the mean), then the max-min loop
        order = ks_order(D, np.linalg.norm(z - z.mean(axis=0), axis=1), params.start)

        # Step 5: The first n_train units of the order form the training set
        test_units = np.zeros(X.shape[0], dtype=bool)
        test_units[order[X.shape[0] - n_test :]] = True
        step = f"KennardStone(start={params.start}, space={params.space})"
        return holdout(spectra, test_units, units, params.group_aware, None, step)
