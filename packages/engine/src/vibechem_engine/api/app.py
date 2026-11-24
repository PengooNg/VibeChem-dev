# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/app.py
"""FastAPI application factory for the engine API (DATA_MODEL.md §2).

Walking-skeleton scope (TASKS.md T0.09): ``GET /health``, ``GET /blocks`` (SNV only)
and the temporary ``POST /skeleton/run`` (§2.12), all under ``/api/v1``.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI

from vibechem_engine import __version__
from vibechem_engine.api.security import install_security
from vibechem_engine.api.skeleton import make_skeleton_router

__all__ = ["API_PREFIX", "create_app"]

API_PREFIX = "/api/v1"

# Static registry entry until the block contract and registry exist (Phase 1).
_SNV_BLOCK: dict[str, Any] = {
    "block_id": "preprocess.snv",
    "version": "1.0.0",
    "block_class": "preprocess",
    "title_key": "blocks.preprocess.snv.title",
    "tooltip_key": "blocks.preprocess.snv.tip",
    "icon": "glyph-snv",
    "fitted": False,
    "tier": "P0",
    "inputs": [{"port_id": "spectra", "port_type": "Spectra", "required": True, "multiple": False}],
    "outputs": [{"port_id": "spectra", "port_type": "Spectra"}],
}


def create_app(token: str, *, testdata_dir: Path, dev: bool = False) -> FastAPI:
    """Build the engine API.

    Parameters
    ----------
    token : str
        Session token; every request needs ``Authorization: Bearer <token>``.
    testdata_dir : Path
        The repository's ``testdata/`` directory (reference datasets for ``/skeleton/run``).
    dev : bool
        Dev mode (``VIBECHEM_DEV=1``): also allow the Vite dev server origin.
    """
    started = time.monotonic()
    # No Swagger/ReDoc pages: they load assets from a CDN (no network calls, CLAUDE.md §4).
    # /openapi.json stays (token-protected) for the generated UI client (T0.10).
    app = FastAPI(title="VibeChem engine", version=__version__, docs_url=None, redoc_url=None)
    install_security(app, token, dev=dev)

    router = APIRouter()

    @router.get("/health")
    def health() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return {
            "status": "ready",
            "engine_version": __version__,
            "api_version": "v1",
            "uptime_s": int(time.monotonic() - started),
        }

    @router.get("/blocks")
    def blocks() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return {"blocks": [_SNV_BLOCK]}

    app.include_router(router, prefix=API_PREFIX)
    app.include_router(make_skeleton_router(testdata_dir), prefix=API_PREFIX)
    return app
