# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/pick_model.py
"""Pick the step-runner model for a TASKS.md step (docs/rules/MODELS.md#opus-rule).

Usage::

    uv run python scripts/pick_model.py <step-id> [--after CI_RED|ESTIMATE|REF_FAIL|S1_BUG]

Prints ``opus (rule <n>)`` or ``sonnet``. Exit code 2 if the step is not in TASKS.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TASKS = Path(__file__).resolve().parents[1] / "docs" / "TASKS.md"
ESCALATE = ("CI_RED", "ESTIMATE", "REF_FAIL")
# Rule 2: hard areas. TASKS.md "Files" lines use short paths (`vibechem_engine/scheduler/`).
HARD_PATHS = re.compile(
    r"packages/native/|vibechem_native/"
    r"|vibechem_engine/(?:scheduler|executor|compiler|cache)/"
    r"|vibechem_core/blocks/(?:validate|split|select|transfer)/"
    r"|vibechem_core/metrics\.py|METHODS\.md"
)


def step_block(tasks: str, step_id: str) -> tuple[str, str] | None:
    """(heading, Files line) of the step, or None if it is not in TASKS.md."""
    m = re.search(rf"^### {re.escape(step_id)} ·.*$", tasks, re.MULTILINE)
    if m is None:
        return None
    rest = tasks[m.end() :]
    end = re.search(r"^#{2,3} ", rest, re.MULTILINE)
    body = rest[: end.start()] if end else rest
    files = re.search(r"^- \*\*Files:\*\*(.*)$", body, re.MULTILINE)
    return m.group(0), files.group(1) if files else ""


def pick(heading: str, files: str, after: str | None = None) -> str:
    if re.search(r"Size [ML]\b", heading) or "⚑opus" in heading:
        return "opus (rule 1)"
    if HARD_PATHS.search(files):
        return "opus (rule 2)"
    if re.search(r"\bgate\b", heading, re.IGNORECASE) or after == "S1_BUG":
        return "opus (rule 3)"
    if after in ESCALATE:
        return "opus (rule 4)"
    return "sonnet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="pick the step-runner model")
    parser.add_argument("step_id")
    parser.add_argument("--after", choices=(*ESCALATE, "S1_BUG"))
    args = parser.parse_args(argv)
    block = step_block(TASKS.read_text(encoding="utf-8"), args.step_id)
    if block is None:
        print(f"step {args.step_id} not found in docs/TASKS.md", file=sys.stderr)
        return 2
    print(pick(*block, args.after))
    return 0


if __name__ == "__main__":
    sys.exit(main())
