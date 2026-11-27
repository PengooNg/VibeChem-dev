# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/executor/__init__.py
"""Task executor: warm loky process pool, BLAS = 1 per worker, per-task seeds (ADR-004)."""

from __future__ import annotations

from vibechem_engine.executor.freeze import loky_freeze_support

__all__ = ["loky_freeze_support"]
