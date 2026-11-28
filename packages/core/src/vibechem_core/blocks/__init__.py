# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/__init__.py
"""Built-in blocks, one sub-package per block class (TECH_STACK.md §2), and the group
helper the split and fold blocks share."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from vibechem_core.block import BLOCK_INPUT_REQUIREMENT_MISSING
from vibechem_core.data import SpectralDataset
from vibechem_core.errors import BlockInputError
from vibechem_core.registry import Registry


def group_codes(spectra: SpectralDataset) -> NDArray[np.intp]:
    """Group number of each row (groups in sorted label order).

    Absent groups or an empty group label raise ``BLOCK_INPUT_REQUIREMENT_MISSING``
    (METHODS.md: a missing group label is a node error).
    """
    labels = spectra.group_ids
    if labels is None or "" in labels:
        raise BlockInputError(
            BLOCK_INPUT_REQUIREMENT_MISSING, {"port_id": "spectra", "requirement": "groups"}
        )
    return np.unique(np.asarray(labels), return_inverse=True)[1]


def default_registry() -> Registry:
    """A new registry holding every built-in block."""
    # Imported here: the block modules import this package for ``group_codes``.
    from vibechem_core.blocks.data.dataset import Dataset
    from vibechem_core.blocks.model.pls import PLS
    from vibechem_core.blocks.model.plsda import PLSDA
    from vibechem_core.blocks.preprocess.cut import Cut
    from vibechem_core.blocks.preprocess.detrend import Detrend
    from vibechem_core.blocks.preprocess.msc import MSC
    from vibechem_core.blocks.preprocess.savgol import SavitzkyGolay
    from vibechem_core.blocks.preprocess.scaling import Autoscale, MeanCentre, Pareto
    from vibechem_core.blocks.preprocess.snv import SNV
    from vibechem_core.blocks.split.kennard_stone import KennardStone
    from vibechem_core.blocks.split.random_split import RandomSplit
    from vibechem_core.blocks.split.spxy import SPXY
    from vibechem_core.blocks.validate.cv import CrossValidation
    from vibechem_core.blocks.validate.folds import (
        ContiguousBlocks,
        GroupKFold,
        KFold,
        LeaveOneOut,
        RepeatedKFold,
        VenetianBlinds,
    )
    from vibechem_core.blocks.validate.grid_search import GridSearch
    from vibechem_core.blocks.validate.nested_cv import NestedCV

    registry = Registry()
    for block in (
        Dataset, PLS, PLSDA, Cut, Detrend, MSC, SavitzkyGolay, Autoscale, MeanCentre, Pareto,
        SNV, KennardStone, RandomSplit, SPXY, CrossValidation, ContiguousBlocks, GroupKFold,
        KFold, LeaveOneOut, RepeatedKFold, VenetianBlinds, GridSearch, NestedCV,
    ):  # fmt: skip
        registry.register(block)
    return registry
