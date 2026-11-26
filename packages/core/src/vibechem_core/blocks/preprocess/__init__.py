# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/blocks/preprocess/__init__.py
"""Preprocessing blocks (docs/METHODS.md §2) and their error and warning codes (DATA_MODEL.md §7)."""

# A spectrum (or the MSC reference) has zero variance, so it cannot be scaled.
BLOCK_CONSTANT_SPECTRA = "BLOCK_CONSTANT_SPECTRA"
# MSC: the fitted slope b of a spectrum on the reference is <= 0 (METHODS.md#msc).
BLOCK_MSC_SLOPE_INVALID = "BLOCK_MSC_SLOPE_INVALID"
# Warning: the axis spacing deviates by more than 1 % from its mean step, so
# Savitzky-Golay works per point (METHODS.md N4).
BLOCK_AXIS_NOT_UNIFORM = "BLOCK_AXIS_NOT_UNIFORM"
