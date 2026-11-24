# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/build_engine.py
"""Freeze the engine with PyInstaller into a one-folder bundle for the desktop app.

electron-builder copies the bundle into the installer's resources (``app/electron-builder.yml``
``extraResources``); Electron main starts it like ``python -m vibechem_engine.api``
(TASKS.md T0.11, TECH_STACK.md §12).

    uv run python scripts/build_engine.py      # → build/engine/vibechem-engine/

``--entry SCRIPT --name NAME`` freezes another script with the same options (the parallel
spike, T0.13, measures loky workers inside such a bundle).

The C++ extension ``vibechem_native._core`` is not imported by the engine yet, and in the
uv workspace it is an editable install whose import hook PyInstaller cannot follow, so the
compiled file is added explicitly; ``scripts/smoke_engine.py --bundle-dir`` checks it is there.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

import PyInstaller.__main__

REPO = Path(__file__).resolve().parents[1]
ENTRY = REPO / "packages" / "engine" / "src" / "vibechem_engine" / "api" / "__main__.py"
BUILD = REPO / "build"
NAME = "vibechem-engine"
DIST = BUILD / "engine"


def native_extension() -> Path:
    """Path of the compiled ``vibechem_native._core`` in the current environment."""
    spec = importlib.util.find_spec("vibechem_native._core")
    if spec is None or spec.origin is None:
        raise SystemExit("vibechem_native._core is not built; run `uv sync` with a C++ compiler")
    return Path(spec.origin)


def pyinstaller_args(entry: Path = ENTRY, name: str = NAME) -> list[str]:
    """Command-line arguments for PyInstaller (one-folder, console, no prompts)."""
    return [
        str(entry),
        "--name",
        name,
        "--onedir",
        "--console",  # Electron main reads the engine.listening line from stdout
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST),
        "--workpath",
        str(BUILD / "pyinstaller"),
        "--specpath",
        str(BUILD / "pyinstaller"),
        # uvicorn picks its event loop and HTTP protocol modules by name at run time.
        "--collect-submodules",
        "uvicorn",
        "--hidden-import",
        "vibechem_native",
        "--add-binary",
        f"{native_extension()}{os.pathsep}vibechem_native",
        # Not used at run time (pulled in by optional imports of numpy/pyarrow).
        *("--exclude-module", "tkinter"),
        *("--exclude-module", "pytest"),
        *("--exclude-module", "_pytest"),
        *("--exclude-module", "hypothesis"),
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/build_engine.py")
    parser.add_argument("--entry", type=Path, default=ENTRY, help="entry script to freeze")
    parser.add_argument("--name", default=NAME, help="bundle and executable name")
    args = parser.parse_args(argv)
    if not args.entry.is_file():
        parser.error(f"{args.entry} is not a file")
    PyInstaller.__main__.run(pyinstaller_args(args.entry.resolve(), args.name))
    print(f"bundle: {DIST / args.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
