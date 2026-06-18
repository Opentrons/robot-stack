"""Tests for release branch override parsing."""

from __future__ import annotations

import unittest

from automation.release_branch_config import (
    ReleaseBranchConfig,
    build_release_branch_config,
    parse_stack_branch_override,
)


class TestParseStackBranchOverride(unittest.TestCase):
    def test_parses_repo_and_branch(self) -> None:
        self.assertEqual(parse_stack_branch_override("oe-core=main"), ("oe-core", "main"))

    def test_rejects_missing_equals(self) -> None:
        with self.assertRaises(ValueError):
            parse_stack_branch_override("oe-core-main")


class TestBuildReleaseBranchConfig(unittest.TestCase):
    def test_builds_from_cli_values(self) -> None:
        config = build_release_branch_config(
            app_branch="chore_release-10.0.0-beta",
            stack_branch=["oe-core=main", "ot3-firmware=main"],
        )
        self.assertEqual(
            config,
            ReleaseBranchConfig(
                app_branch="chore_release-10.0.0-beta",
                stack_branches={"oe-core": "main", "ot3-firmware": "main"},
            ),
        )


if __name__ == "__main__":
    unittest.main()
