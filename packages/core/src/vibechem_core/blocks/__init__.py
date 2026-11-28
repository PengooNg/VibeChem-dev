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
    from vibechem_core.blocks._builtin import build_registry  # noqa: PLC0415

    return build_registry()
