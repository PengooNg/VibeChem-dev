# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/split/random_split.py
"""
Block:          Random and stratified hold-out split
Class:          split
Ports:          in  -> spectra : Spectra
                out -> folds   : Folds
                out -> train   : Spectra
                out -> test    : Spectra
Reference:      Pedregosa et al. (2011), JMLR 12, 2825-2830 (scikit-learn);
                Esbensen & Geladi (2010), J. Chemometrics 24, 168-187
METHODS:        docs/METHODS.md#random-split, #group-aware-split
Implementation: wraps sklearn.model_selection.train_test_split (seed drawn from the Generator)
Fitted:         No (row selection is a design step; nothing is fitted on test rows)
Reviewer:       Quan

The Generator is ``rng`` when given, else ``numpy.random.default_rng(seed)``. With
groups, a unit's stratum is its majority class (ties: first class in sorted order) or
the quantile bin of its mean y (bins merged by tied y are renumbered from 0).
``FoldSet.seed`` is the ``seed`` parameter, or with an explicit ``rng`` the integer
drawn from it and passed to scikit-learn, so the split can always be reproduced.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import cast

import numpy as np
from numpy.typing import NDArray
from sklearn.model_selection import train_test_split  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

from vibechem_core.block import (
    BLOCK_INPUT_REQUIREMENT_MISSING,
    BLOCK_PARAM_INVALID,
    Block,
    Param,
    port,
)
from vibechem_core.blocks.split import (
    BLOCK_SPLIT_STRATUM_TOO_SMALL,
    SPLIT_OUTPUTS,
    SplitOutputs,
    SplitParams,
    holdout,
    n_test_units,
    sampling_units,
    unit_means,
)
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError, ErrorParam, ParamError, VibeChemWarning


@dataclass(frozen=True)
class RandomSplitParams(SplitParams):
    stratify: str = Param("none", choices=("none", "classes", "y"))
    n_bins: int = Param(5, min=2, visible_if=("stratify", ("y",)))
    seed: int = Param(0, min=0)


def _strata(
    spectra: SpectralDataset, units: NDArray[np.intp], params: RandomSplitParams
) -> NDArray[np.str_] | None:
    """Stratum label of each unit, or ``None`` without stratification."""
    if params.stratify == "none":
        return None
    if params.stratify == "classes":
        if spectra.classes is None:
            raise BlockInputError(
                BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "classes"}
            )
        names, codes = np.unique(np.asarray(spectra.classes), return_inverse=True)
        counts = np.zeros((int(units.max()) + 1, names.size))
        np.add.at(counts, (units, codes), 1)
        return names[np.argmax(counts, axis=1)]
    if spectra.y is None:
        raise BlockInputError(
            BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "y"}
        )
    if spectra.y.shape[1] != 1:
        raise ParamError(
            BLOCK_PARAM_INVALID, {"param_id": "stratify", "reason": "constraint", "value": "y"}
        )
    y = unit_means(spectra.y, units)[:, 0]
    edges = np.quantile(y, np.linspace(0.0, 1.0, params.n_bins + 1))
    bins = np.searchsorted(edges[1:-1], y, side="right")
    return np.unique(bins, return_inverse=True)[1].astype(
        str
    )  # tied y merges bins: renumber from 0


class RandomSplit(Block):
    block_id = "split.random"
    version = "1.0.0"
    icon = "glyph-random-split"
    references = ("pedregosa2011sklearn", "esbensen2010validation")
    fitted = False
    inputs = (port("spectra", "Spectra"),)
    outputs = SPLIT_OUTPUTS
    params_type = RandomSplitParams
    implementation = ("scikit-learn", "sklearn.model_selection.train_test_split")

    def apply(
        self,
        spectra: SpectralDataset,
        params: RandomSplitParams,
        rng: np.random.Generator | None = None,
    ) -> SplitOutputs:
        units = sampling_units(spectra, params.group_aware)
        n_units = int(units.max()) + 1
        pool = np.arange(n_units)

        # Step 1: Strata = classes, y quantile bins, or none; strata with < 2 units go to training
        labels = _strata(spectra, units, params)
        n_strata = 1
        if labels is not None:
            names, counts = np.unique(labels, return_counts=True)
            small = names[counts < 2]
            if small.size:
                strata: list[ErrorParam] = [str(s) for s in small]
                warnings.warn(
                    VibeChemWarning(BLOCK_SPLIT_STRATUM_TOO_SMALL, {"strata": strata}),
                    stacklevel=2,
                )
            pool = pool[~np.isin(labels, small)]
            n_strata = int((counts >= 2).sum())
            if n_strata == 0:
                raise ParamError(
                    BLOCK_PARAM_INVALID,
                    {
                        "param_id": "stratify",
                        "reason": "constraint",
                        "constraint": "at least one stratum with 2 or more sampling units",
                    },
                )
        n_test = n_test_units(params, n_units, n_pool=pool.size, n_strata=n_strata)

        # Step 2: Within each stratum draw the test share with the Generator (one
        # scikit-learn call; its stratified draw keeps every stratum's share)
        generator = np.random.default_rng(params.seed) if rng is None else rng
        seed = int(generator.integers(2**32))
        stratify = None if labels is None else labels[pool]
        _, test_pos = cast(
            "list[NDArray[np.intp]]",
            train_test_split(pool, test_size=n_test, random_state=seed, stratify=stratify),
        )

        # Step 3: Union of the per-stratum test draws -> test units
        test_units = np.zeros(n_units, dtype=bool)
        test_units[test_pos] = True
        recorded = params.seed if rng is None else seed
        step = f"RandomSplit(stratify={params.stratify}, seed={recorded})"
        return holdout(spectra, test_units, units, params.group_aware, recorded, step)
