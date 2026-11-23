# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/skeleton.py
"""Temporary walking-skeleton endpoint ``POST /skeleton/run`` (DATA_MODEL.md §2.12).

Loads a reference dataset, optionally applies SNV, and returns the spectra as an
Arrow IPC stream in the ``view=spectra`` lines format of §2.8. Removed in T4.01 when
the real run and preview endpoints exist.

The SNV here is a stand-in for the walking skeleton only; the real block (T1.07)
follows METHODS.md and the block contract.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import APIRouter, Response
from numpy.typing import NDArray
from pydantic import BaseModel, Field

from vibechem_core.reference_datasets import load_reference_dataset
from vibechem_engine.api.arrow import ARROW_STREAM, spectra_to_arrow
from vibechem_engine.api.security import PREVIEW_MODE_HEADER

__all__ = ["SkeletonRunRequest", "decimate_minmax", "make_skeleton_router", "snv"]


class SkeletonRunRequest(BaseModel):
    """Body of ``POST /skeleton/run``."""

    dataset: Literal["gasoline_nir", "olive_oil_ftir"]
    apply_snv: bool
    width: int = Field(default=1200, ge=64, le=4096)


def snv(spectra: NDArray[np.float64]) -> NDArray[np.float64]:
    """Standard normal variate: centre and scale each spectrum (row) by its own statistics.

    Barnes, Dhanoa & Lister (1989), Appl. Spectrosc. 43, 772; sample standard
    deviation (``ddof=1``).
    """
    # Step 1: subtract each spectrum's mean.
    centred = spectra - spectra.mean(axis=1, keepdims=True)
    # Step 2: divide by each spectrum's standard deviation.
    return centred / spectra.std(axis=1, ddof=1, keepdims=True)


def decimate_minmax(
    x: NDArray[np.float64], y: NDArray[np.float64], width: int
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Reduce ``n_points`` to about ``width`` while keeping each spectrum's peaks.

    Points are split into ``width // 2`` buckets; each bucket becomes two points at
    its first and last ``x``, holding the spectrum's minimum and maximum in the order
    they occur. All spectra share one ``x`` column. No change when
    ``n_points <= width``.
    """
    n_points = x.size
    if n_points <= width:
        return x, y
    # Step 1: bucket edges; every bucket has at least two points since n_points > width.
    edges: list[int] = np.linspace(0, n_points, width // 2 + 1).astype(np.intp).tolist()
    x_out = np.empty(2 * (len(edges) - 1))
    y_out = np.empty((y.shape[0], x_out.size))
    rows = np.arange(y.shape[0], dtype=np.intp)
    for k, (a, b) in enumerate(pairwise(edges)):
        # Step 2: per spectrum, min and max of the bucket, in order of occurrence.
        segment = y[:, a:b]
        i_min = segment.argmin(axis=1)
        i_max = segment.argmax(axis=1)
        x_out[2 * k : 2 * k + 2] = x[a], x[b - 1]
        y_out[:, 2 * k] = segment[rows, np.minimum(i_min, i_max)]
        y_out[:, 2 * k + 1] = segment[rows, np.maximum(i_min, i_max)]
    return x_out, y_out


def make_skeleton_router(testdata_dir: Path) -> APIRouter:
    """Router with ``POST /skeleton/run`` reading datasets from ``testdata_dir``."""
    router = APIRouter()

    @router.post("/skeleton/run")
    def skeleton_run(request: SkeletonRunRequest) -> Response:  # pyright: ignore[reportUnusedFunction]
        data = load_reference_dataset(request.dataset, testdata_dir=testdata_dir)
        spectra = snv(data.spectra) if request.apply_snv else data.spectra
        x, y = decimate_minmax(data.axis, spectra, request.width)
        # Both reference datasets have ≤ 120 spectra, below max_lines (500): lines mode.
        return Response(
            content=spectra_to_arrow(x, y),
            media_type=ARROW_STREAM,
            headers={PREVIEW_MODE_HEADER: "lines"},
        )

    return router
