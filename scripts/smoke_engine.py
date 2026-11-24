# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/smoke_engine.py
"""Installer smoke test: start an engine, wait for ``engine.listening``, check ``/health``.

Used by ``.github/workflows/installers.yml`` on the PyInstaller engine inside the
electron-builder output (TASKS.md T0.11). Passes when ``GET /api/v1/health`` with the
session token answers ``200`` with ``"status": "ready"`` (DATA_MODEL.md §1, §2.2).

    uv run python scripts/smoke_engine.py [--bundle-dir DIR] -- ENGINE_COMMAND...

``--bundle-dir`` also requires the compiled extension ``vibechem_native/_core.*`` in DIR.
Standard library only, so it runs against any engine build.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from typing import cast

START_TIMEOUT_S = 120.0


def read_listening_line(process: subprocess.Popen[str], timeout: float) -> tuple[int, str]:
    """Return port + token from the first valid ``engine.listening`` line on stdout, or raise."""
    found: list[tuple[int, str]] = []

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                parsed: object = json.loads(line)
            except ValueError:
                continue  # a log line
            if not isinstance(parsed, dict):
                continue
            message = cast("dict[str, object]", parsed)
            port, token = message.get("port"), message.get("token")
            if (
                message.get("event") == "engine.listening"
                and isinstance(port, int)
                and isinstance(token, str)
            ):
                found.append((port, token))
                return

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(timeout)
    if not found:
        if thread.is_alive():
            raise RuntimeError(f"no engine.listening line within {timeout:.0f} s")
        # stdout closed: the engine is exiting
        raise RuntimeError(
            f"engine exited with code {process.wait(timeout=10)} before announcing its port"
        )
    return found[0]


def get_health(port: int, token: str) -> dict[str, object]:
    """``GET /api/v1/health`` with the bearer token; returns the JSON body (raises on non-200)."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/v1/health", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body: dict[str, object] = json.loads(response.read())
        return body


def native_extension_files(bundle_dir: Path) -> list[Path]:
    """Compiled ``vibechem_native._core`` files inside a bundle folder."""
    return sorted(
        path for path in bundle_dir.rglob("_core.*") if path.parent.name == "vibechem_native"
    )


def smoke(command: list[str], *, bundle_dir: Path | None, timeout: float) -> str:
    """Run the smoke test; returns a one-line summary or raises ``RuntimeError``."""
    # Step 1: the bundle must contain the native extension (the engine does not import it yet).
    if bundle_dir is not None and not native_extension_files(bundle_dir):
        raise RuntimeError(f"no vibechem_native/_core.* in {bundle_dir}")

    # Step 2: start the engine and read its port + token. Windows' CreateProcess does not
    # find a relative executable path with "/" separators, so resolve an existing file.
    if Path(command[0]).is_file():
        command = [str(Path(command[0]).resolve()), *command[1:]]
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True, encoding="utf-8") as process:
        try:
            port, token = read_listening_line(process, timeout)

            # Step 3: the health endpoint must report ready.
            health = get_health(port, token)
            if health.get("status") != "ready":
                raise RuntimeError(f"/health is not ready: {health}")
            return f"engine ready on port {port}: {health}"
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/smoke_engine.py")
    parser.add_argument("--bundle-dir", type=Path, help="engine bundle folder to check")
    parser.add_argument("--timeout", type=float, default=START_TIMEOUT_S)
    parser.add_argument("command", nargs="+", help="engine command (after --)")
    args = parser.parse_args(argv)
    try:
        print(smoke(args.command, bundle_dir=args.bundle_dir, timeout=args.timeout))
    except (RuntimeError, OSError) as exc:
        print(f"smoke test FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
