# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/tests/api/test_app.py
"""``GET /health`` and ``GET /blocks`` (DATA_MODEL.md §2.2, §2.3)."""

from __future__ import annotations

from fastapi.testclient import TestClient

import vibechem_engine


def test_health_reports_ready(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get("/api/v1/health", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["engine_version"] == vibechem_engine.__version__
    assert body["api_version"] == "v1"
    assert isinstance(body["uptime_s"], int)
    assert body["uptime_s"] >= 0


def test_blocks_lists_only_snv(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get("/api/v1/blocks", headers=auth)
    assert response.status_code == 200
    (block,) = response.json()["blocks"]
    assert block == {  # DATA_MODEL.md §2.3 example
        "block_id": "preprocess.snv",
        "version": "1.0.0",
        "block_class": "preprocess",
        "title_key": "blocks.preprocess.snv.title",
        "tooltip_key": "blocks.preprocess.snv.tip",
        "icon": "glyph-snv",
        "fitted": False,
        "tier": "P0",
        "inputs": [
            {"port_id": "spectra", "port_type": "Spectra", "required": True, "multiple": False}
        ],
        "outputs": [{"port_id": "spectra", "port_type": "Spectra"}],
    }


def test_endpoints_live_under_api_v1(client: TestClient, auth: dict[str, str]) -> None:
    assert client.get("/health", headers=auth).status_code == 404
