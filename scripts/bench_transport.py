# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/bench_transport.py
"""Transport spike (TASKS.md T0.12, ARCHITECTURE.md ADR-003): preview round-trip timing.

    uv run python scripts/bench_transport.py [--n 2000] [--points 2000] [--repeats 20]
        [--node] [--json PATH]

Starts the real engine app (``create_app``: token + Origin checks) with uvicorn on
127.0.0.1, adds a spike-only route ``GET /api/v1/spike/preview?mode=lines|density``
that builds a ``view=spectra`` preview (DATA_MODEL.md §2.8) from an in-memory
``n x points`` matrix, and times the round-trip from a Python client (urllib +
pyarrow) and, with ``--node``, from Node (fetch + apache-arrow, the renderer's
decoder; ``app/scripts/bench-transport-client.mjs``).

Round-trip = request → preview built (decimate or density raster) → Arrow IPC
encoded → sent over loopback → received → decoded. The server's build + encode time
comes back in a ``Server-Timing`` header, so transport = total - server.

The density layout (one row per pixel column: ``x``, ``mean``, ``sd_lo``, ``sd_hi``,
``density`` as fixed-size list of 256 uint16, selected rows ``y_{i}``) is a spike
proposal, not a DATA_MODEL.md format.
"""
# pyarrow ships no type information (see vibechem_engine/api/arrow.py).
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import argparse
import json
import platform
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pyarrow as pa
import uvicorn
from fastapi import APIRouter, Response
from numpy.typing import NDArray

from vibechem_core.reference_datasets import find_testdata_dir
from vibechem_engine.api.app import API_PREFIX, create_app
from vibechem_engine.api.arrow import ARROW_STREAM, spectra_to_arrow
from vibechem_engine.api.security import APP_ORIGIN, PREVIEW_MODE_HEADER, new_session_token
from vibechem_engine.api.skeleton import decimate_minmax

REPO = Path(__file__).resolve().parents[1]
NODE_CLIENT = REPO / "app" / "scripts" / "bench-transport-client.mjs"
DENSITY_BINS = 256
N_SELECTED = 10
TARGET_MS = 300.0  # ADR-003 "Actions"
START_TIMEOUT_S = 30.0


def synthetic_spectra(
    n: int, points: int, rng: np.random.Generator
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """NIR-like spectra: three Gaussian bands with random heights, a sloped baseline and noise."""
    x = np.linspace(4000.0, 10000.0, points)
    centres = np.array([5200.0, 6900.0, 8300.0])
    bands = np.exp(-(((x[None, :] - centres[:, None]) / 180.0) ** 2))  # (3, points)
    heights = rng.uniform(0.2, 1.0, size=(n, 3))
    slope = rng.uniform(-1e-5, 1e-5, size=(n, 1))
    y = heights @ bands + slope * (x - x[0]) + rng.normal(0.0, 0.005, size=(n, points))
    return x, y


def density_raster(y: NDArray[np.float64], width: int) -> tuple[NDArray[np.uint16], float, float]:
    """Count every point into a ``width x 256`` grid (pixel column x y bin).

    Point ``j`` of ``points`` goes to column ``j * width // points``; y bins span the
    global min..max. Returns the counts (uint16, saturating) and the y range.
    """
    n, points = y.shape
    y_min, y_max = float(y.min()), float(y.max())
    # Step 1: pixel column of each point index (same for every spectrum).
    col = (np.arange(points) * width) // points
    # Step 2: y bin of every value; the maximum goes into the top bin.
    scale = DENSITY_BINS / (y_max - y_min) if y_max > y_min else 0.0
    row = np.minimum(((y - y_min) * scale).astype(np.intp), DENSITY_BINS - 1)
    # Step 3: count (column, bin) pairs over all spectra.
    flat = (np.broadcast_to(col, (n, points)) * DENSITY_BINS + row).ravel()
    counts = np.bincount(flat, minlength=width * DENSITY_BINS)
    return np.minimum(counts, 65535).astype(np.uint16).reshape(width, DENSITY_BINS), y_min, y_max


def density_to_arrow(x: NDArray[np.float64], y: NDArray[np.float64], width: int) -> bytes:
    """Density-mode preview as an Arrow IPC stream (spike layout, see module docstring)."""
    counts, y_min, y_max = density_raster(y, width)
    # Step 1: curves (mean, ±1 SD, selected rows) averaged per pixel column, like the raster.
    cols = (np.arange(x.size) * width) // x.size
    per_col = np.bincount(cols, minlength=width)
    mean = y.mean(axis=0)
    sd = y.std(axis=0, ddof=1)
    curves = {"x": x, "mean": mean, "sd_lo": mean - sd, "sd_hi": mean + sd}
    curves |= {f"y_{i}": row for i, row in enumerate(y[:N_SELECTED])}
    columns: dict[str, Any] = {
        name: pa.array(np.bincount(cols, weights=c, minlength=width) / per_col, type=pa.float32())
        for name, c in curves.items()
    }
    # Step 2: the raster as one fixed-size list (256 uint16 counts) per pixel column.
    columns["density"] = pa.FixedSizeListArray.from_arrays(pa.array(counts.ravel()), DENSITY_BINS)
    table = pa.table(columns).replace_schema_metadata(
        {"y_min": repr(y_min), "y_max": repr(y_max), "n_spectra": str(y.shape[0])}
    )
    sink = pa.BufferOutputStream()
    with pa.ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    content: bytes = sink.getvalue().to_pybytes()
    return content


def make_spike_router(x: NDArray[np.float64], y: NDArray[np.float64]) -> APIRouter:
    """Router with the spike-only ``GET /spike/preview``."""
    router = APIRouter()

    @router.get("/spike/preview")
    def spike_preview(  # pyright: ignore[reportUnusedFunction]
        mode: Literal["lines", "density"], width: int = 1200
    ) -> Response:
        t0 = time.perf_counter()
        if mode == "lines":
            content = spectra_to_arrow(*decimate_minmax(x, y, width))
        else:
            content = density_to_arrow(x, y, width)
        server_ms = (time.perf_counter() - t0) * 1000
        return Response(
            content=content,
            media_type=ARROW_STREAM,
            headers={PREVIEW_MODE_HEADER: mode, "Server-Timing": f"build;dur={server_ms:.2f}"},
        )

    return router


@contextmanager
def serve(x: NDArray[np.float64], y: NDArray[np.float64]) -> Generator[tuple[int, str]]:
    """Serve the engine app + spike route on a random loopback port in a thread.

    Yields ``(port, token)``; on exit the server is stopped and its thread joined.
    """
    token = new_session_token()
    app = create_app(token, testdata_dir=find_testdata_dir())
    app.include_router(make_spike_router(x, y), prefix=API_PREFIX)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port: int = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + START_TIMEOUT_S
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("benchmark server did not start")
                time.sleep(0.01)
            yield port, token
        finally:
            server.should_exit = True
            thread.join(START_TIMEOUT_S)


def summarise(samples: list[dict[str, float]]) -> dict[str, float]:
    """Median and max of each timing key over the repeats."""
    out: dict[str, float] = {}
    for key in samples[0]:
        values = [s[key] for s in samples]
        out[f"{key}_median"] = round(statistics.median(values), 2)
        out[f"{key}_max"] = round(max(values), 2)
    return out


def python_client(port: int, token: str, mode: str, width: int, repeats: int) -> dict[str, Any]:
    """Time ``repeats`` round-trips (after one warm-up) with urllib + pyarrow."""
    url = f"http://127.0.0.1:{port}{API_PREFIX}/spike/preview?mode={mode}&width={width}"
    headers = {"Authorization": f"Bearer {token}", "Origin": APP_ORIGIN}
    samples: list[dict[str, float]] = []
    size = 0
    for i in range(repeats + 1):
        t0 = time.perf_counter()
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers)) as resp:
            body: bytes = resp.read()
            timing: str = resp.headers["Server-Timing"]
        t1 = time.perf_counter()
        table = pa.ipc.open_stream(body).read_all()
        t2 = time.perf_counter()
        if i == 0:
            size = len(body)
            continue
        samples.append(
            {
                "server_ms": float(timing.split("dur=")[1]),
                "fetch_ms": (t1 - t0) * 1000,
                "decode_ms": (t2 - t1) * 1000,
                "total_ms": (t2 - t0) * 1000,
            }
        )
        del table
    return {"client": "python", "mode": mode, "bytes": size, **summarise(samples)}


def node_client(port: int, token: str, mode: str, width: int, repeats: int) -> dict[str, Any]:
    """Run the Node client (fetch + apache-arrow) and return its JSON result."""
    cmd = ["node", str(NODE_CLIENT), str(port), token, mode, str(width), str(repeats)]
    out = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO / "app")
    if out.returncode != 0:
        raise RuntimeError(f"Node client failed ({out.returncode}): {out.stderr.strip()}")
    result: dict[str, Any] = json.loads(out.stdout)
    return result


def run(n: int, points: int, repeats: int, width: int, *, node: bool) -> dict[str, Any]:
    """Run every (client, mode) combination and return the results."""
    x, y = synthetic_spectra(n, points, np.random.default_rng(12))
    results: list[dict[str, Any]] = []
    with serve(x, y) as (port, token):
        for mode in ("lines", "density"):
            results.append(python_client(port, token, mode, width, repeats))
            if node:
                results.append(node_client(port, token, mode, width, repeats))
    return {
        "os": platform.system(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "n": n,
        "points": points,
        "width": width,
        "repeats": repeats,
        "target_ms": TARGET_MS,
        "results": results,
    }


def markdown(report: dict[str, Any]) -> str:
    """One Markdown table of the median (max) timings."""
    title = (
        f"### Transport spike — {report['os']} {report['machine']}, "
        f"{report['n']} x {report['points']}, width {report['width']}, "
        f"{report['repeats']} repeats (median, max in brackets; ms)"
    )
    lines = [
        title,
        "",
        "| client | mode | KiB | server build+encode | fetch | decode | total | < 300 ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report["results"]:

        def cell(key: str, r: dict[str, Any] = r) -> str:
            return f"{r[key + '_median']:.1f} ({r[key + '_max']:.1f})"

        ok = "yes" if r["total_ms_max"] < report["target_ms"] else "**no**"
        lines.append(
            f"| {r['client']} | {r['mode']} | {r['bytes'] / 1024:.0f} | {cell('server_ms')} "
            f"| {cell('fetch_ms')} | {cell('decode_ms')} | {cell('total_ms')} | {ok} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts/bench_transport.py")
    parser.add_argument("--n", type=int, default=2000, help="number of spectra")
    parser.add_argument("--points", type=int, default=2000, help="points per spectrum")
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument("--width", type=int, default=1200, help="plot width in pixels")
    parser.add_argument("--node", action="store_true", help="also time the Node client")
    parser.add_argument("--json", type=Path, help="write the raw results here")
    args = parser.parse_args(argv)
    if not 2 <= args.width <= args.points:
        parser.error("--width must be between 2 and --points")
    if args.n < 2 or args.repeats < 1:
        parser.error("--n must be at least 2 and --repeats at least 1")
    report = run(args.n, args.points, args.repeats, args.width, node=args.node)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    sys.stdout.write(markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
