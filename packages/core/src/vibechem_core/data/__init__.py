# SPDX-License-Identifier: GPL-3.0-or-later
# packages/core/src/vibechem_core/data/__init__.py
"""Spectral data model: ``Axis``, ``Spatial`` (DATA_MODEL.md §4.2)."""

from vibechem_core.data.axis import AXIS_UNITS, Axis, AxisUnit, Spatial

__all__ = ["AXIS_UNITS", "Axis", "AxisUnit", "Spatial"]
