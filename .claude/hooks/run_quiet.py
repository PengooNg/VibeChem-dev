# SPDX-License-Identifier: GPL-3.0-or-later
# .claude/hooks/run_quiet.py
"""Run one allowed test/check command and print only what matters.

Usage::

    uv run --no-project python .claude/hooks/run_quiet.py -- <command> [args...]

Refuses anything quiet_tests.py would not wrap. Saves the full output to
``.cache/test-logs/<timestamp>.log`` and ``.cache/test-logs/latest.log``, then prints
failure blocks (5 lines of context, at most 150 lines), the check.py health summary
verbatim, the last output line, and ``exit=<code> · full log: …``. Exits with the
command's own exit code. Stdlib only.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quiet_tests import allowed  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / ".cache" / "test-logs"
FAILURE = re.compile(r"FAILED|ERROR|Traceback|FAIL|✗")
CONTEXT = 5
MAX_FAILURE_LINES = 150
SUMMARY_START, SUMMARY_END = "=== HEALTH SUMMARY ===", "=== END HEALTH SUMMARY ==="


def shorten(lines: list[str]) -> list[str]:
    """Failure blocks with context, then the health summary block, then the last line."""
    keep: set[int] = set()
    for i, line in enumerate(lines):
        if FAILURE.search(line):
            keep.update(range(max(0, i - CONTEXT), min(len(lines), i + CONTEXT + 1)))
    out: list[str] = []
    last = -2
    for i in sorted(keep):
        if i != last + 1 and out:
            out.append("...")
        out.append(lines[i])
        last = i
    if len(out) > MAX_FAILURE_LINES:
        out = [*out[:MAX_FAILURE_LINES], f"... ({len(out) - MAX_FAILURE_LINES} more failure lines in the log)"]
    if SUMMARY_START in lines:
        start = lines.index(SUMMARY_START)
        end = lines.index(SUMMARY_END, start) if SUMMARY_END in lines[start:] else len(lines) - 1
        out += lines[start : end + 1]
    tail = next((ln for ln in reversed(lines) if ln.strip()), "")
    if tail and (not out or tail != out[-1]):
        out.append(tail)
    return out


def main(argv: list[str]) -> int:
    if argv[:1] == ["--"]:
        argv = argv[1:]
    if not allowed(argv):
        print(f"run_quiet: refused (not an allowed test/check command): {argv}", file=sys.stderr)
        return 2
    exe = shutil.which(argv[0]) or argv[0]  # pnpm is pnpm.cmd on Windows
    proc = subprocess.run(  # allowlisted command, no shell
        [exe, *argv[1:]], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", check=False,
    )
    text = proc.stdout
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (LOG_DIR / f"{stamp}.log").write_text(text, encoding="utf-8")
    (LOG_DIR / "latest.log").write_text(text, encoding="utf-8")
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="replace")
    for line in shorten(text.splitlines()):
        print(line)
    print(f"exit={proc.returncode} · full log: .cache/test-logs/latest.log")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
