# SPDX-License-Identifier: GPL-3.0-or-later
# scripts/tests/test_merge_step.py
"""Unit tests for scripts/merge_step.py with a fake ``gh`` (no network)."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import merge_step

TASKS_MD = """\
## Status overview
| Phase 0 | Phase 1 |
|---|---|
| [x] T0.01 CI smoke 👤 | [ ] T1.07 SNV, MSC, detrend, cut |
| [ ] T0.03 Python workspace + check.py | [ ] T1.07a Split part a |
| [ ] T0.06 Full CI + rulesets 👤 | [ ] T1.08 Savitzky–Golay |

### T0.03 · Python workspace and `scripts/check.py` · K · Size M
### T0.06 · Full CI and rulesets 👤 · K · Size M
### T1.07 · SNV, MSC, detrend, cut · Q · Size M
### T1.09 · Scaling blocks 👤 · Q · Size S
### T1.10 · KS, SPXY, random split · Q · Size S
- **Done when:** tests pass. 👤 Quan merges.

### T1.11 · CV fold generators · Q · Size S
- **Done when:** tests pass.
"""

GREEN = [{"name": "ci (ubuntu)", "bucket": "pass"}, {"name": "ci (windows)", "bucket": "pass"}]


class FakeGh:
    """Records ``gh`` calls and answers them from canned data."""

    def __init__(
        self,
        pr: dict[str, Any] | None = None,
        checks: list[dict[str, str]] | None = None,
        tasks_md: str = TASKS_MD,
        fail_on: str | None = None,
    ) -> None:
        self.pr: dict[str, Any] = {
            "number": 12,
            "title": "[T0.03] Python workspace and check.py",
            "baseRefName": "phase-0",
            "headRefName": "t0-03-workspace",
            "headRefOid": "abc123",
            "isDraft": False,
            "state": "OPEN",
            **(pr or {}),
        }
        self.checks = GREEN if checks is None else checks
        self.tasks_md = tasks_md
        self.fail_on = fail_on
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        args = list(args)
        self.calls.append(args)
        command = " ".join(args[:2])
        if self.fail_on is not None and command == self.fail_on:
            raise merge_step.GhError(f"gh {command} failed (1): boom")
        if command == "pr view":
            return json.dumps(self.pr)
        if command == "pr checks":
            return json.dumps(self.checks)
        if args[:3] == ["api", "-X", "DELETE"]:
            if self.fail_on == "api DELETE":
                raise merge_step.GhError("gh api DELETE failed (1): boom")
            return ""
        if args[0] == "api":
            if self.fail_on == "api TASKS":
                raise merge_step.GhError("gh api failed (1): Not Found")
            return self.tasks_md
        if command == "pr merge":
            return ""
        raise AssertionError(f"unexpected gh call: {args}")

    def merge_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[:2] == ["pr", "merge"]]

    def tasks_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[0] == "api" and c[-1].startswith("repos/{owner}/{repo}/contents/")]

    def delete_calls(self) -> list[list[str]]:
        return [c for c in self.calls if c[:3] == ["api", "-X", "DELETE"]]


def run_main(fake: FakeGh, pr_number: str = "12") -> tuple[int, str]:
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        code = merge_step.main([pr_number], run=fake)
    return code, err.getvalue()


class MergeTests(unittest.TestCase):
    def test_green_step_pr_is_squash_merged_with_title_and_pinned_head(self) -> None:
        fake = FakeGh()
        code, _ = run_main(fake)
        self.assertEqual(code, 0)
        self.assertEqual(
            fake.merge_calls(),
            [
                [
                    "pr", "merge", "12", "--squash",
                    "--subject", "[T0.03] Python workspace and check.py",
                    "--match-head-commit", "abc123",
                ]
            ],
        )

    def test_remote_step_branch_is_deleted_after_the_merge(self) -> None:
        fake = FakeGh()
        run_main(fake)
        self.assertEqual(
            fake.delete_calls(),
            [["api", "-X", "DELETE", "repos/{owner}/{repo}/git/refs/heads/t0-03-workspace"]],
        )
        self.assertLess(fake.calls.index(fake.merge_calls()[0]), fake.calls.index(fake.delete_calls()[0]))

    def test_failed_branch_delete_still_reports_the_merge(self) -> None:
        code, err = run_main(FakeGh(fail_on="api DELETE"))
        self.assertEqual(code, 0)
        self.assertIn("not deleted", err)

    def test_tasks_md_is_read_from_the_base_branch(self) -> None:
        fake = FakeGh(pr={"baseRefName": "phase-1", "title": "[T1.07] SNV, MSC"})
        run_main(fake)
        api_calls = fake.tasks_calls()
        self.assertEqual(len(api_calls), 1)
        self.assertTrue(api_calls[0][-1].endswith("docs/TASKS.md?ref=phase-1"))

    def test_bug_and_sync_prs_merge_without_tasks_lookup(self) -> None:
        for title in ("[BUG #31] Fix SNV on flat rows", "[SYNC] main → phase-0"):
            with self.subTest(title=title):
                fake = FakeGh(pr={"title": title})
                code, _ = run_main(fake)
                self.assertEqual(code, 0)
                self.assertEqual(fake.tasks_calls(), [])
                self.assertEqual(len(fake.merge_calls()), 1)

    def test_skipped_checks_count_as_green(self) -> None:
        fake = FakeGh(checks=[*GREEN, {"name": "installers", "bucket": "skipping"}])
        self.assertEqual(run_main(fake)[0], 0)

    def test_sub_step_is_not_confused_with_its_parent(self) -> None:
        tasks = TASKS_MD.replace("T1.07 SNV, MSC, detrend, cut", "T1.07 SNV, MSC 👤")
        fake = FakeGh(pr={"title": "[T1.07a] Split part a", "baseRefName": "phase-1"}, tasks_md=tasks)
        self.assertEqual(run_main(fake)[0], 0)


class RefusalTests(unittest.TestCase):
    def assert_refused(self, fake: FakeGh, expected: str) -> None:
        code, err = run_main(fake)
        self.assertEqual(code, 1)
        self.assertIn(expected, err)
        self.assertEqual(fake.merge_calls(), [])

    def test_base_must_be_a_phase_branch(self) -> None:
        for base in ("main", "phase-x", "t0-03-workspace"):
            with self.subTest(base=base):
                self.assert_refused(FakeGh(pr={"baseRefName": base}), f"base branch is '{base}'")

    def test_draft_is_refused(self) -> None:
        self.assert_refused(FakeGh(pr={"isDraft": True}), "draft")

    def test_closed_or_merged_pr_is_refused(self) -> None:
        for state in ("CLOSED", "MERGED"):
            with self.subTest(state=state):
                self.assert_refused(FakeGh(pr={"state": state}), f"PR is {state}")

    def test_title_prefix_is_required(self) -> None:
        for title in ("Python workspace", "[PHASE 0] Foundations", "T0.03 workspace"):
            with self.subTest(title=title):
                self.assert_refused(FakeGh(pr={"title": title}), "title must start with")

    def test_step_title_needs_a_step_id(self) -> None:
        self.assert_refused(FakeGh(pr={"title": "[Typo] fix"}), "cannot read a step ID")

    def test_human_step_in_heading_and_status_is_refused(self) -> None:
        self.assert_refused(FakeGh(pr={"title": "[T0.06] Full CI"}), "T0.06 is a 👤 step")

    def test_human_step_marked_only_in_heading_is_refused(self) -> None:
        self.assert_refused(FakeGh(pr={"title": "[T1.09] Scaling"}), "T1.09 is a 👤 step")

    def test_human_step_marked_only_in_status_row_is_refused(self) -> None:
        self.assert_refused(FakeGh(pr={"title": "[T0.01] CI smoke"}), "T0.01 is a 👤 step")

    def test_human_step_marked_only_in_body_is_refused(self) -> None:
        self.assert_refused(FakeGh(pr={"title": "[T1.10] KS split"}), "T1.10 is a 👤 step")

    def test_body_of_next_step_is_not_mixed_in(self) -> None:
        self.assertEqual(run_main(FakeGh(pr={"title": "[T1.11] CV folds"}))[0], 0)

    def test_unreadable_tasks_md_is_a_refusal_with_all_reasons(self) -> None:
        fake = FakeGh(pr={"baseRefName": "main"}, fail_on="api TASKS")
        code, err = run_main(fake)
        self.assertEqual(code, 1)
        self.assertIn("could not read docs/TASKS.md on 'main'", err)
        self.assertIn("base branch is 'main'", err)

    def test_unknown_step_is_refused(self) -> None:
        self.assert_refused(FakeGh(pr={"title": "[T9.99] Nope"}), "T9.99 is not in docs/TASKS.md")

    def test_failing_or_pending_checks_are_refused(self) -> None:
        for bucket in ("fail", "pending", "cancel"):
            with self.subTest(bucket=bucket):
                fake = FakeGh(checks=[*GREEN, {"name": "ci (macos)", "bucket": bucket}])
                self.assert_refused(fake, f"check 'ci (macos)' is {bucket}")

    def test_no_checks_is_refused(self) -> None:
        self.assert_refused(FakeGh(checks=[]), "no CI checks reported")

    def test_unreadable_checks_are_refused(self) -> None:
        self.assert_refused(FakeGh(fail_on="pr checks"), "could not read CI checks")

    def test_all_reasons_are_reported_together(self) -> None:
        fake = FakeGh(pr={"isDraft": True, "baseRefName": "main"}, checks=[])
        code, err = run_main(fake)
        self.assertEqual(code, 1)
        for expected in ("draft", "base branch is 'main'", "no CI checks reported"):
            self.assertIn(expected, err)


class GhFailureTests(unittest.TestCase):
    def test_gh_failure_on_pr_view_exits_2(self) -> None:
        fake = FakeGh(fail_on="pr view")
        self.assertEqual(run_main(fake)[0], 2)
        self.assertEqual(fake.merge_calls(), [])

    def test_gh_failure_on_merge_exits_2(self) -> None:
        fake = FakeGh(fail_on="pr merge")
        self.assertEqual(run_main(fake)[0], 2)
        self.assertEqual(fake.delete_calls(), [])

    def test_missing_gh_executable_is_a_gh_error(self) -> None:
        with (
            mock.patch.object(merge_step.subprocess, "run", side_effect=FileNotFoundError("gh")),
            self.assertRaises(merge_step.GhError),
        ):
            merge_step.run_gh(["--version"])


class FindStepTests(unittest.TestCase):
    def test_find_step(self) -> None:
        self.assertIs(merge_step.find_step(TASKS_MD, "T0.03"), False)
        self.assertIs(merge_step.find_step(TASKS_MD, "T0.06"), True)
        self.assertIs(merge_step.find_step(TASKS_MD, "T1.07a"), False)
        self.assertIs(merge_step.find_step(TASKS_MD, "T1.10"), True)
        self.assertIs(merge_step.find_step(TASKS_MD, "T1.11"), False)
        self.assertIsNone(merge_step.find_step(TASKS_MD, "T0.02"))

    def test_real_tasks_md_marks_this_step_as_human(self) -> None:
        tasks = (Path(__file__).resolve().parents[2] / "docs" / "TASKS.md").read_text("utf-8")
        self.assertIs(merge_step.find_step(tasks, "T0.02"), True)
        self.assertIs(merge_step.find_step(tasks, "T0.03"), False)


if __name__ == "__main__":
    unittest.main()
