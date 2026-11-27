# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_check_doc_refs.py
"""Unit tests for scripts/check_doc_refs.py on a tiny fake repo."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_doc_refs


def test_slug_follows_github_rules() -> None:
    assert check_doc_refs.slug("9.1 Phase gate") == "91-phase-gate"
    assert check_doc_refs.slug("Stop safely, never mid-section") == "stop-safely-never-mid-section"


def test_reports_missing_file_heading_old_citation_and_length(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "A.md").write_text("# A\n## Good part\n", encoding="utf-8")
    old = "CLAUDE" + ".md §3"
    claude = tmp_path / "CLAUDE.md"
    claude.write_text(
        "docs/A.md#good-part ok\ndocs/A.md#bad-part\ndocs/B.md\n" + old + "\n" + "x\n" * 100,
        encoding="utf-8",
    )
    problems = check_doc_refs.check(tmp_path, [claude])
    assert problems == [
        "CLAUDE.md:2: missing heading docs/A.md#bad-part",
        "CLAUDE.md:3: missing file docs/B.md",
        "CLAUDE.md:4: old CLAUDE.md section citation",
        "CLAUDE.md: 104 lines (max 100)",
    ]
