# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/test_init.py
"""Smoke test: the package imports and reports its installed version."""

from importlib.metadata import version

import vibechem_engine


def test_version_matches_installed_metadata() -> None:
    assert vibechem_engine.__version__ == version("vibechem-engine")
