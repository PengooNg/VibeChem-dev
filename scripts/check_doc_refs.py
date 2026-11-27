# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/check_doc_refs.py
"""Check that rule references resolve.

Usage::

    uv run python scripts/check_doc_refs.py

Every ``docs/….md#anchor``, ``CLAUDE.md#anchor`` and ``.claude/…`` path named in
CLAUDE.md, ``docs/`` and the project's own skills and agents must exist (file, and
heading anchor by GitHub slug rules). No tracked file may cite old CLAUDE.md
sections by number, and CLAUDE.md stays at most ``MAX_CLAUDE_LINES`` lines.
Prints one line per problem; exit code 0 when there are none, 1 otherwise.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_CLAUDE_LINES = 100
# Skills written for this project (the vendored ones keep their upstream text).
OWN_SKILLS = ("phase", "step", "resume", "status", "bug", "block-template")
REF = re.compile(r"(?<![\w/.-])((?:docs/[\w./-]+?\.md)|CLAUDE\.md|(?:\.claude/[\w./-]+))(#[\w-]+)?")
OLD_CITATION = re.compile(r"CLAUDE\.md ?§")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r'<a id="([\w-]+)"></a>')
# shortcut: Quan-only files keep old citations until Quan applies the A5 patch, which deletes this line.
PENDING_QUAN_PATCH = {"scripts/permission_gate.py", "scripts/merge_step.py"}


def slug(heading: str) -> str:
    """GitHub heading anchor: lower case, punctuation dropped, spaces to hyphens."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    """All heading anchors of a Markdown file, with GitHub's ``-1``, ``-2`` suffixes."""
    seen: dict[str, int] = {}
    out: set[str] = set()
    in_code = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            out.update(HTML_ANCHOR.findall(line))
        m = None if in_code else HEADING.match(line)
        if m:
            base = slug(m.group(1))
            n = seen.get(base, 0)
            seen[base] = n + 1
            out.add(base if n == 0 else f"{base}-{n}")
    return out


def sources(root: Path) -> list[Path]:
    """The files whose references are checked."""
    files = [root / "CLAUDE.md", *sorted((root / "docs").rglob("*.md"))]
    files += sorted((root / ".claude" / "agents").glob("*.md"))
    files += [root / ".claude" / "skills" / s / "SKILL.md" for s in OWN_SKILLS]
    return [f for f in files if f.is_file()]


def tracked_files(root: Path) -> list[Path]:
    """Files tracked by git (the instruction files that are never committed are skipped)."""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [root / p for p in out.split("\0") if p]


def check(root: Path, tracked: list[Path]) -> list[str]:
    problems: list[str] = []
    cache: dict[Path, set[str]] = {}
    for src in sources(root):
        rel = src.relative_to(root).as_posix()
        for lineno, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
            for m in REF.finditer(line):
                if line[m.end() : m.end() + 1] in ("*", "<", "{"):
                    continue  # a glob or placeholder, not a path
                target, anchor = m.group(1).rstrip("."), m.group(2)
                path = root / target
                if not path.exists():
                    problems.append(f"{rel}:{lineno}: missing file {target}")
                elif anchor:
                    if path not in cache:
                        cache[path] = anchors(path)
                    if anchor[1:] not in cache[path]:
                        problems.append(f"{rel}:{lineno}: missing heading {target}{anchor}")
    for f in tracked:
        if f.relative_to(root).as_posix() in PENDING_QUAN_PATCH:
            continue
        if (
            f.suffix not in {".md", ".py", ".yml", ".yaml", ".json", ".toml", ".ts", ".tsx", ""}
            or not f.is_file()
        ):
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if OLD_CITATION.search(line):
                problems.append(
                    f"{f.relative_to(root).as_posix()}:{lineno}: old CLAUDE.md section citation"
                )
    claude = root / "CLAUDE.md"
    if claude.is_file():
        n = len(claude.read_text(encoding="utf-8").splitlines())
        if n > MAX_CLAUDE_LINES:
            problems.append(f"CLAUDE.md: {n} lines (max {MAX_CLAUDE_LINES})")
    return problems


def main() -> int:
    problems = check(ROOT, tracked_files(ROOT))
    for p in problems:
        print(p)
    print(f"doc refs: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
