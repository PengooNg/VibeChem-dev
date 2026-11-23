# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/__init__.py
"""Local HTTP API of the engine (DATA_MODEL.md §1–§2). Start with ``python -m vibechem_engine.api``."""

from vibechem_engine.api.app import API_PREFIX, create_app

__all__ = ["API_PREFIX", "create_app"]
