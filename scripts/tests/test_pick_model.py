# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_pick_model.py
"""Unit tests for scripts/pick_model.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pick_model

TASKS = """## Phase 2
### T2.11 · Python API and CLI · Size S
- **Files:** `vibechem_engine/cli/`, public `vibechem.Pipeline`
- **Done when:** works.

### T2.10 · CV runners · Size L → split into T2.10a and T2.10b
- **Files:** `vibechem_engine/runners/`

### T2.20 · Scheduler tweak · Size S
- **Files:** `vibechem_engine/scheduler/`

### T2.14 · Phase 2 gate 👤 · Size S
- **Read:** PROGRESS.md
"""


def pick(step: str, after: str | None = None) -> str:
    block = pick_model.step_block(TASKS, step)
    assert block is not None
    return pick_model.pick(*block, after)


def test_rules() -> None:
    assert pick("T2.11") == "sonnet"
    assert pick("T2.10") == "opus (rule 1)"
    assert pick("T2.20") == "opus (rule 2)"
    assert pick("T2.14") == "opus (rule 3)"
    assert pick("T2.11", after="S1_BUG") == "opus (rule 3)"
    assert pick("T2.11", after="CI_RED") == "opus (rule 4)"
    assert pick_model.step_block(TASKS, "T9.99") is None


def test_every_open_step_in_tasks_resolves() -> None:
    assert pick_model.main(["T2.11"]) == 0
