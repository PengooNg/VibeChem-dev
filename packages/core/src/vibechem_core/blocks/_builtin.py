# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/_builtin.py
"""The list of built-in blocks behind :func:`vibechem_core.blocks.default_registry`."""

from __future__ import annotations

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
from vibechem_core.registry import Registry


def build_registry() -> Registry:
    registry = Registry()
    for block in (
        Dataset, PLS, PLSDA, Cut, Detrend, MSC, SavitzkyGolay, Autoscale, MeanCentre, Pareto,
        SNV, KennardStone, RandomSplit, SPXY, CrossValidation, ContiguousBlocks, GroupKFold,
        KFold, LeaveOneOut, RepeatedKFold, VenetianBlinds, GridSearch, NestedCV,
    ):  # fmt: skip
        registry.register(block)
    return registry
