# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/__init__.py
"""Preprocessing blocks (docs/METHODS.md §2) and their error and warning codes (DATA_MODEL.md §7)."""

import numpy as np

from vibechem_core.block import BLOCK_INPUT_AXIS_MISMATCH
from vibechem_core.data import Axis
from vibechem_core.errors import BlockInputError

# A spectrum (or the MSC reference) has zero variance, so it cannot be scaled.
BLOCK_CONSTANT_SPECTRA = "BLOCK_CONSTANT_SPECTRA"
# MSC: the fitted slope b of a spectrum on the reference is <= 0 (METHODS.md#msc).
BLOCK_MSC_SLOPE_INVALID = "BLOCK_MSC_SLOPE_INVALID"
# Warning: the axis spacing deviates by more than 1 % from its mean step, so
# Savitzky-Golay works per point (METHODS.md N4).
BLOCK_AXIS_NOT_UNIFORM = "BLOCK_AXIS_NOT_UNIFORM"
# Warning: autoscaling/Pareto found training columns with zero variance; they are
# centred and left unscaled (METHODS.md N3).
BLOCK_CONSTANT_COLUMNS = "BLOCK_CONSTANT_COLUMNS"


def check_axis(port_id: str, found: Axis, expected: Axis) -> None:
    """``BLOCK_INPUT_AXIS_MISMATCH`` unless ``found`` equals ``expected`` (DATA_MODEL.md
    §4.5: same unit and values, relative tolerance 1e-9)."""
    same = (
        found.unit == expected.unit
        and found.p == expected.p
        and bool(np.allclose(found.values, expected.values, rtol=1e-9, atol=0))
    )
    if not same:
        raise BlockInputError(
            BLOCK_INPUT_AXIS_MISMATCH,
            {"port_id": port_id, "expected": _describe(expected), "found": _describe(found)},
        )


def _describe(axis: Axis) -> str:
    values = axis.values
    return f"{axis.p} points, {values[0]:g} to {values[-1]:g} {axis.unit}"
