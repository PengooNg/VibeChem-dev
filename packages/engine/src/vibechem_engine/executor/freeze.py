# SPDX-License-Identifier: GPL-3.0-or-later
# packages/engine/src/vibechem_engine/executor/freeze.py
"""Let loky start its helper processes inside a frozen (PyInstaller) app.

Moved from the T0.13 spike (``scripts/bench_parallel.py``, ``docs/spikes/parallel.md``
finding 1). It depends on loky 3.7 command lines, so loky is pinned to ``>=3.7,<3.8``.
"""
# loky ships no type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

import os
import re
import runpy
import sys

import loky.backend.resource_tracker

if sys.platform == "win32":
    import loky.backend.popen_loky_win32
else:
    import loky.backend.popen_loky_posix  # imported here so PyInstaller collects it

__all__ = ["loky_freeze_support"]

_RESOURCE_TRACKER_CMD = re.compile(
    r"from loky\.backend\.resource_tracker import main; main\((\d+), (True|False)\)"
)


def loky_freeze_support() -> None:
    """Start loky's helper processes in a frozen app; call first in ``__main__``.

    In a PyInstaller bundle ``sys.executable`` is the bundle itself, so loky re-runs it with:
    ``-c "from loky.backend.resource_tracker import main; main(<fd>, <verbose>)"`` (resource
    tracker), ``--multiprocessing-fork <handle>`` (Windows worker; the standard
    ``freeze_support()`` expects ``name=value`` arguments there and fails), or
    ``-m loky.backend.popen_loky_posix …`` (macOS/Linux worker; the bootloader has no ``-m``).
    Each is routed to loky's own entry point here; the process exits when it is done.
    Call it before ``multiprocessing.freeze_support()``. Not frozen: does nothing.
    """
    if not getattr(sys, "frozen", False):
        return
    argv = sys.argv
    # Step 1: resource tracker (all OS); the command is matched exactly, never executed.
    if "-c" in argv:
        command_index = argv.index("-c") + 1
        match = (
            _RESOURCE_TRACKER_CMD.fullmatch(argv[command_index])
            if command_index < len(argv)
            else None
        )
        if match:
            loky.backend.resource_tracker.main(int(match[1]), match[2] == "True")
            sys.exit(0)
    # Step 2: worker process.
    if sys.platform == "win32":
        if len(argv) == 3 and argv[1] == "--multiprocessing-fork" and "=" not in argv[2]:
            # The frozen command line has no parent pid; the pipe handle lives in the parent.
            loky.backend.popen_loky_win32.main(int(argv[2]), parent_pid=os.getppid())
    elif argv[1:3] == ["-m", "loky.backend.popen_loky_posix"]:
        sys.argv = [argv[0], *argv[3:]]
        # Run it as __main__ like ``python -m``; drop the copy imported above so runpy
        # does not warn about running a module that is already imported.
        name = loky.backend.popen_loky_posix.__name__
        del sys.modules[name]
        runpy.run_module(name, run_name="__main__")
        sys.exit(0)
