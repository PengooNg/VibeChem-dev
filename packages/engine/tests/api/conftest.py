# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/api/conftest.py
"""Fixtures for the engine API tests: an app with a known token and its test client."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from vibechem_core.reference_datasets import find_testdata_dir
from vibechem_engine.api import create_app

_TOKEN = "test-token"


def _client(*, dev: bool) -> TestClient:
    return TestClient(create_app(_TOKEN, testdata_dir=find_testdata_dir(), dev=dev))


@pytest.fixture
def token() -> str:
    """The session token of the ``client`` and ``dev_client`` apps."""
    return _TOKEN


@pytest.fixture
def auth() -> dict[str, str]:
    """Headers carrying the correct session token."""
    return {"Authorization": f"Bearer {_TOKEN}"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Production-mode app (no dev origin)."""
    with _client(dev=False) as c:
        yield c


@pytest.fixture
def dev_client() -> Iterator[TestClient]:
    """Dev-mode app (``VIBECHEM_DEV=1``: Vite dev server origin allowed)."""
    with _client(dev=True) as c:
        yield c
