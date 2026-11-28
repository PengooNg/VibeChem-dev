# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/data/dataset.py
"""
Block:          Dataset (data source)
Class:          data
Ports:          (no inputs)
                out -> spectra : Spectra
Reference:      none
METHODS:        none (no computation; DATA_MODEL.md §2.3 "Data source block")
Implementation: own code
Fitted:         No
Reviewer:       Quan
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vibechem_core.block import Block, Param, port


@dataclass(frozen=True)
class DatasetParams:
    dataset_id: str = Param("dataset")


class Dataset(Block):
    """Source of a pipeline: the engine supplies the dataset named by ``dataset_id``."""

    block_id = "data.dataset"
    version = "1.0.0"
    icon = "glyph-dataset"
    fitted = False
    inputs = ()
    outputs = (port("spectra", "Spectra"),)
    params_type = DatasetParams

    def apply(self, **kwargs: Any) -> Any:  # noqa: ARG002
        # The runner takes a data node's output from ``sources``; reaching here is a bug.
        raise RuntimeError("data.dataset is supplied by the engine and never runs")
