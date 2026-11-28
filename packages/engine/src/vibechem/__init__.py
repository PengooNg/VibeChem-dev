# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem/__init__.py
"""Public Python API of VibeChem: ``from vibechem import Pipeline`` (T2.11).

A thin re-export of :mod:`vibechem_engine.pipeline`; the implementation lives there.
"""

from vibechem_engine.pipeline import Pipeline, results_of

__all__ = ["Pipeline", "results_of"]
