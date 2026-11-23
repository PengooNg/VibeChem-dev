# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/merge_step.py
"""Merge a green step PR into its phase branch (CLAUDE.md §14.2).

Usage: ``uv run python scripts/merge_step.py <pr-number>``

The script refuses (exit code 1) unless all of these hold:

1. the PR is open and not a draft;
2. its base branch is ``phase-<N>``;
3. its title starts with ``[T<step>]``, ``[BUG`` or ``[SYNC]``;
4. for a ``[T<step>]`` title, the step exists in ``docs/TASKS.md`` **on the base
   branch** and is not marked 👤 (human step) in its heading, its body or its
   status-overview cell;
5. CI reported at least one check, and every check passed (or was skipped).

Then it squash-merges with ``gh pr merge --squash``, using the PR title as the
commit subject and pinning the head commit that was checked, and deletes the
remote step branch. It deletes only the remote branch, never a local one, because
local branches may be checked out in other worktrees (``gh pr merge
--delete-branch`` would fail there after the merge).

Standard library only; all GitHub access goes through the ``gh`` CLI.
Exit codes: 0 merged · 1 refused · 2 ``gh`` failed.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from typing import Any

HUMAN_MARK = "\N{BUST IN SILHOUETTE}"  # 👤
TITLE_PREFIXES = ("[T", "[BUG", "[SYNC]")
STEP_TITLE = re.compile(r"^\[(T\d+\.\d+[a-z]?)\]")
PHASE_BRANCH = re.compile(r"^phase-\d+$")
OK_CHECK_BUCKETS = frozenset({"pass", "skipping"})
PR_FIELDS = "number,title,baseRefName,headRefName,headRefOid,isDraft,state"

Runner = Callable[[Sequence[str]], str]


class GhError(RuntimeError):
    """A ``gh`` command could not run or exited with a non-zero status."""


def run_gh(args: Sequence[str]) -> str:
    """Run ``gh`` with ``args`` and return its standard output."""
    try:
        proc = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8", check=False
        )
    except OSError as err:
        raise GhError(f"cannot run gh (is the GitHub CLI installed and on PATH?): {err}") from err
    if proc.returncode != 0:
        raise GhError(f"gh {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def find_step(tasks_md: str, step_id: str) -> bool | None:
    """Look up ``step_id`` in TASKS.md.

    Returns ``None`` if the step is not listed, otherwise whether it is marked 👤
    in its ``### <id> ·`` heading, the body below that heading (up to the next
    heading), or its status-overview cell.
    """
    sid = re.escape(step_id)
    heading = re.compile(rf"^###\s+{sid}\s+·")
    status_cell = re.compile(rf"\[[ xX]\]\s+{sid}\s([^|]*)")
    found = False
    human = False
    in_step = False
    for line in tasks_md.splitlines():
        if line.startswith("#"):
            in_step = heading.match(line) is not None
            found = found or in_step
        if in_step:
            human = human or HUMAN_MARK in line
        for match in status_cell.finditer(line):
            found = True
            human = human or HUMAN_MARK in match.group(1)
    return human if found else None


def refusal_reasons(pr_number: int, pr: dict[str, Any], run: Runner) -> list[str]:
    """Return every reason not to merge the PR (empty list = OK to merge)."""
    reasons: list[str] = []
    title = str(pr["title"])
    base = str(pr["baseRefName"])

    # Check 1: open and ready for review
    if pr["state"] != "OPEN":
        reasons.append(f"PR is {pr['state']}, not OPEN")
    if pr["isDraft"]:
        reasons.append("PR is a draft; mark it ready for review first")

    # Check 2: base is a phase branch
    if not PHASE_BRANCH.match(base):
        reasons.append(f"base branch is '{base}', expected 'phase-<N>'")

    # Check 3: title prefix
    if not title.startswith(TITLE_PREFIXES):
        reasons.append(f"title must start with [T, [BUG or [SYNC]: {title!r}")

    # Check 4: step exists in TASKS.md on the base branch and is not 👤
    elif title.startswith("[T"):
        step_match = STEP_TITLE.match(title)
        if step_match is None:
            reasons.append(f"cannot read a step ID like [T1.07] from the title: {title!r}")
        else:
            step_id = step_match.group(1)
            try:
                tasks_md = run(
                    [
                        "api",
                        "-H",
                        "Accept: application/vnd.github.raw+json",
                        f"repos/{{owner}}/{{repo}}/contents/docs/TASKS.md?ref={base}",
                    ]
                )
            except GhError as err:
                reasons.append(f"could not read docs/TASKS.md on '{base}': {err}")
            else:
                human = find_step(tasks_md, step_id)
                if human is None:
                    reasons.append(f"step {step_id} is not in docs/TASKS.md on '{base}'")
                elif human:
                    reasons.append(f"step {step_id} is a {HUMAN_MARK} step; Quan merges it")

    # Check 5: CI checks all green
    try:
        checks: list[dict[str, Any]] = json.loads(
            run(["pr", "checks", str(pr_number), "--json", "name,bucket"])
        )
    except GhError as err:
        reasons.append(f"could not read CI checks: {err}")
    else:
        if not checks:
            reasons.append("no CI checks reported")
        for check in checks:
            if check["bucket"] not in OK_CHECK_BUCKETS:
                reasons.append(f"check '{check['name']}' is {check['bucket']}")

    return reasons


def main(argv: Sequence[str] | None = None, run: Runner = run_gh) -> int:
    # Titles and messages contain non-ASCII (👤, →); a piped Windows console is not UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Merge a green step PR into its phase branch.")
    parser.add_argument("pr", type=int, help="pull request number")
    args = parser.parse_args(argv)
    pr_number: int = args.pr

    try:
        pr: dict[str, Any] = json.loads(run(["pr", "view", str(pr_number), "--json", PR_FIELDS]))
        reasons = refusal_reasons(pr_number, pr, run)
        if reasons:
            print(f"merge_step: refusing to merge PR #{pr_number}:", file=sys.stderr)
            for reason in reasons:
                print(f"  - {reason}", file=sys.stderr)
            return 1

        subject = str(pr["title"])
        run(
            [
                "pr",
                "merge",
                str(pr_number),
                "--squash",
                "--subject",
                subject,
                "--match-head-commit",
                str(pr["headRefOid"]),
            ]
        )
    except GhError as err:
        print(f"merge_step: {err}", file=sys.stderr)
        return 2

    print(f"merge_step: merged PR #{pr_number} into {pr['baseRefName']}: {subject}")

    # The merge is done; failing to delete the branch only warrants a warning.
    head = str(pr["headRefName"])
    try:
        run(["api", "-X", "DELETE", f"repos/{{owner}}/{{repo}}/git/refs/heads/{head}"])
    except GhError as err:
        print(f"merge_step: warning: remote branch '{head}' not deleted: {err}", file=sys.stderr)
    else:
        print(f"merge_step: deleted remote branch '{head}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
