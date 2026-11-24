# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/api/__main__.py
"""Start the engine API: ``python -m vibechem_engine.api [--testdata-dir PATH]``.

Binds 127.0.0.1 on a random free port, then writes one JSON line to stdout for the
Electron main process (DATA_MODEL.md §1 "Start-up"):

    {"event": "engine.listening", "port": 52114, "token": "…"}

The token is generated per launch and never written to disk. ``VIBECHEM_DEV=1``
enables dev mode (Vite dev server origin allowed).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path

import uvicorn

from vibechem_core.reference_datasets import find_testdata_dir
from vibechem_engine.api.app import create_app
from vibechem_engine.api.security import new_session_token

HOST = "127.0.0.1"


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, bind the socket, announce port + token, serve until stopped."""
    parser = argparse.ArgumentParser(prog="python -m vibechem_engine.api")
    parser.add_argument(
        "--testdata-dir",
        type=Path,
        help="repository testdata/ folder (default: found above the installed package)",
    )
    args = parser.parse_args(argv)

    # Step 1: locate the reference datasets (not shipped in the wheel).
    testdata_dir: Path | None = args.testdata_dir
    if testdata_dir is None:
        try:
            testdata_dir = find_testdata_dir()
        except FileNotFoundError as exc:
            parser.error(str(exc))
    elif not (testdata_dir / "datasets" / "PROVENANCE.md").is_file():
        parser.error(f"{testdata_dir} has no datasets/PROVENANCE.md")

    # Step 2: build the app with a fresh session token.
    token = new_session_token()
    dev = os.environ.get("VIBECHEM_DEV") == "1"
    app = create_app(token, testdata_dir=testdata_dir, dev=dev)

    # Step 3: bind a random free port on loopback and start listening, so requests
    # sent right after the announcement wait in the backlog instead of failing.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, 0))
    sock.listen()
    port: int = sock.getsockname()[1]

    # Step 4: announce port + token on stdout (one JSON line), then serve.
    sys.stdout.write(json.dumps({"event": "engine.listening", "port": port, "token": token}) + "\n")
    sys.stdout.flush()
    server = uvicorn.Server(uvicorn.Config(app, access_log=False))
    server.run(sockets=[sock])
    return 0


if __name__ == "__main__":
    sys.exit(main())
