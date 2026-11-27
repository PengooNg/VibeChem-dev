# SPDX-License-Identifier: GPL-3.0-or-later
# .claude/hooks/quiet_tests.py
"""PreToolUse hook (Bash): route known test/check commands through run_quiet.py.

Reads the hook JSON from stdin. When ``tool_input.command`` is exactly one allowed
test/check command with no shell metacharacters, prints ``updatedInput`` with the
whole tool input and only ``command`` wrapped; otherwise prints nothing. Never sets
a permission decision: the permission gate judges the original command, and
run_quiet.py re-checks the same allowlist before running anything. Stdlib only.
"""

from __future__ import annotations

import json
import shlex
import sys

METACHARS = set(";&|<>$`\n\r")
WRAPPER = "uv run --no-project python .claude/hooks/run_quiet.py -- "
PREFIXES: tuple[tuple[str, ...], ...] = (
    ("uv", "run", "pytest"),
    ("uv", "run", "python", "scripts/check.py"),
    ("pnpm", "--dir", "app", "test"),
    ("pnpm", "--dir", "app", "e2e"),
    ("pnpm", "--dir", "app", "lint"),
)


def allowed(argv: list[str]) -> bool:
    """True if ``argv`` starts with one of the allowed command shapes."""
    return any(tuple(argv[: len(p)]) == p for p in PREFIXES)


def wrap(command: str) -> str | None:
    """The wrapped command, or None if ``command`` must run unchanged."""
    if not command or METACHARS & set(command):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    return WRAPPER + command.strip() if allowed(argv) else None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool_input = dict(event.get("tool_input") or {})
        command = tool_input.get("command")
    except (ValueError, AttributeError):
        return 0
    new = wrap(command) if isinstance(command, str) else None
    if new is not None:
        tool_input["command"] = new
        out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": tool_input}}
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
