# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/split/__init__.py
"""Hold-out split blocks (docs/METHODS.md §4) and what they share.

Every split block selects whole sampling units: with ``group_aware`` and
``group_ids`` a unit is one group (METHODS.md#group-aware-split), otherwise one row.
``apply`` returns a dict keyed by output port: ``folds`` (one ``holdout`` fold),
``train`` and ``test`` spectra.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import TypedDict

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import BLOCK_PARAM_INVALID, Param, port
from vibechem_core.data import Fold, FoldSet, SpectralDataset
from vibechem_core.errors import ParamError

# SPXY: all responses are equal, so the y term of the distance is undefined (METHODS.md N13).
BLOCK_CONSTANT_RESPONSE = "BLOCK_CONSTANT_RESPONSE"
# Warning: stratified random split found strata with fewer than 2 units; they go to
# training (METHODS.md#random-split).
BLOCK_SPLIT_STRATUM_TOO_SMALL = "BLOCK_SPLIT_STRATUM_TOO_SMALL"

SPLIT_OUTPUTS = (port("folds", "Folds"), port("train", "Spectra"), port("test", "Spectra"))


class SplitOutputs(TypedDict):
    """What ``apply`` returns, keyed by output ``port_id``."""

    folds: FoldSet
    train: SpectralDataset
    test: SpectralDataset


@dataclass(frozen=True)
class SplitParams:
    size_by: str = Param("fraction", choices=("fraction", "count"))
    test_fraction: float = Param(0.25, min=0.0, max=1.0, visible_if=("size_by", ("fraction",)))
    n_test: int = Param(1, min=1, visible_if=("size_by", ("count",)))
    group_aware: bool = Param(True)


def n_test_units(
    params: SplitParams, n_units: int, n_pool: int | None = None, n_strata: int = 1
) -> int:
    """Number of test units (``ceil(f * n_units)`` or ``n_test``).

    ``BLOCK_PARAM_INVALID`` unless both sets get at least ``n_strata`` units of the
    ``n_pool`` units that can be drawn (default: all ``n_units``).
    """
    if params.size_by == "count":
        param_id, n_test = "n_test", params.n_test
    else:
        # round first: 0.3 * 10 is 3.0000000000000004 and must not become 4
        param_id, n_test = "test_fraction", math.ceil(round(params.test_fraction * n_units, 9))
    high = (n_units if n_pool is None else n_pool) - n_strata
    if not n_strata <= n_test <= high:
        raise ParamError(
            BLOCK_PARAM_INVALID,
            {
                "param_id": param_id,
                "reason": "constraint",
                "constraint": f"{n_strata} <= n_test <= {high}",
            },
        )
    return n_test


def sampling_units(spectra: SpectralDataset, group_aware: bool) -> NDArray[np.intp]:
    """Unit number of each row: groups numbered by first appearance, or one unit per row."""
    if spectra.group_ids is None or not group_aware:
        return np.arange(spectra.n_samples)
    _, first, inverse = np.unique(spectra.group_ids, return_index=True, return_inverse=True)
    return np.argsort(np.argsort(first))[inverse]


def unit_means(values: NDArray[np.float64], units: NDArray[np.intp]) -> NDArray[np.float64]:
    """Mean of ``values`` rows per unit (rows of the result in unit order)."""
    n_units = int(units.max()) + 1
    sums = np.zeros((n_units, values.shape[1]))
    np.add.at(sums, units, values)
    return sums / np.bincount(units, minlength=n_units)[:, None]


def holdout(
    spectra: SpectralDataset,
    test_units: NDArray[np.bool_],
    units: NDArray[np.intp],
    group_aware: bool,
    seed: int | None,
    step: str,
) -> SplitOutputs:
    """Expand selected units to rows and build the three outputs."""
    is_test = test_units[units]
    train_pos, test_pos = np.flatnonzero(~is_test), np.flatnonzero(is_test)
    fold = Fold(0, 0, spectra.row_index[train_pos], spectra.row_index[test_pos])
    folds = FoldSet(
        "holdout",
        spectra.source_id,
        spectra.n_samples,
        (fold,),
        groups_respected=spectra.group_ids is None or group_aware,
        seed=seed,
    )

    def part(positions: NDArray[np.intp], name: str) -> SpectralDataset:
        sub = spectra.subset(positions)
        return replace(sub, history=(*sub.history, f"{step}[{name}]"))

    return {"folds": folds, "train": part(train_pos, "train"), "test": part(test_pos, "test")}
