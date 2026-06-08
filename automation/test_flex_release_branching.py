"""Tests for release branch selection by path and channel.

Flex external uses chore_release when present. Flex internal and all OT-2
releases tag default-branch HEAD.

Run from repository root:

    uv run python -m unittest automation.test_flex_release_branching -v
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from automation.go import (
    RELEASE_PATHS,
    RepoState,
    branches_to_sync,
    chore_release_branch,
    format_tag_commands,
    is_chore_release_branch,
    release_branch_for_repo,
    release_on_default_branch,
    repo_by_name,
)

FLEX = RELEASE_PATHS["flex"]
OT2 = RELEASE_PATHS["ot2"]
OPENTRONS = repo_by_name("opentrons")
OT2_APP = repo_by_name("opentrons-ot2")
BUILDROOT = repo_by_name("buildroot")


class TestChoreReleaseBranch(unittest.TestCase):
    def test_strips_v_prefix(self) -> None:
        self.assertEqual(chore_release_branch("v9.1.0"), "chore_release-9.1.0")

    def test_is_chore_release_branch(self) -> None:
        self.assertTrue(is_chore_release_branch("chore_release-9.1.0"))
        self.assertFalse(is_chore_release_branch("edge"))


class TestFormatTagCommands(unittest.TestCase):
    def test_includes_checkout_on_chore_release_branch(self) -> None:
        commands = format_tag_commands(
            "v0.10.2",
            "v9.1.0-alpha.4",
            branch="chore_release-9.1.0",
        )
        self.assertEqual(commands[0], ("Checkout", "git checkout chore_release-9.1.0"))
        self.assertEqual(commands[1][0], "Create")

    def test_omits_checkout_on_default_branch(self) -> None:
        commands = format_tag_commands("ot3@8.5.0", "ot3@8.5.0", branch="edge")
        self.assertEqual(commands[0][0], "Create")
        self.assertEqual(len(commands), 3)


class TestReleaseOnDefaultBranch(unittest.TestCase):
    def test_true_for_flex_internal(self) -> None:
        self.assertTrue(release_on_default_branch(FLEX, "internal"))

    def test_false_for_flex_external(self) -> None:
        self.assertFalse(release_on_default_branch(FLEX, "external"))

    def test_true_for_ot2_internal(self) -> None:
        self.assertTrue(release_on_default_branch(OT2, "internal"))

    def test_true_for_ot2_external(self) -> None:
        self.assertTrue(release_on_default_branch(OT2, "external"))


class TestReleaseBranchForRepo(unittest.TestCase):
    def test_flex_internal_uses_default_branch(self) -> None:
        state = RepoState(branch_tags={"edge": {}, "chore_release-9.1.0": {}})
        branch = release_branch_for_repo(state, OPENTRONS, "v9.1.0", FLEX, "internal")
        self.assertEqual(branch, "edge")

    def test_flex_external_prefers_chore_release(self) -> None:
        state = RepoState(branch_tags={"edge": {}, "chore_release-9.1.0": {}})
        branch = release_branch_for_repo(state, OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branch, "chore_release-9.1.0")

    def test_flex_external_falls_back_to_default(self) -> None:
        state = RepoState(branch_tags={"edge": {}})
        branch = release_branch_for_repo(state, OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branch, "edge")

    def test_ot2_internal_uses_default_branch(self) -> None:
        state = RepoState(branch_tags={"edge": {}, "chore_release-26.5.2601": {}})
        branch = release_branch_for_repo(state, OT2_APP, "26.5.2601", OT2, "internal")
        self.assertEqual(branch, "edge")

    def test_ot2_external_uses_default_branch(self) -> None:
        state = RepoState(branch_tags={"edge": {}, "chore_release-26.6.0": {}})
        branch = release_branch_for_repo(state, OT2_APP, "26.6.0", OT2, "external")
        self.assertEqual(branch, "edge")


class TestBranchesToSync(unittest.TestCase):
    @patch("automation.go.branch_exists", return_value=True)
    def test_flex_external_syncs_chore_release_when_remote_has_it(self, _mock: object) -> None:
        branches = branches_to_sync(OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branches, ["edge", "chore_release-9.1.0"])

    @patch("automation.go.branch_exists", return_value=False)
    def test_flex_external_omits_chore_release_when_missing(self, _mock: object) -> None:
        branches = branches_to_sync(OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branches, ["edge"])

    @patch("automation.go.branch_exists")
    def test_flex_internal_syncs_default_only(self, mock_exists: MagicMock) -> None:
        branches = branches_to_sync(OPENTRONS, "v9.1.0", FLEX, "internal")
        self.assertEqual(branches, ["edge"])
        mock_exists.assert_not_called()

    @patch("automation.go.branch_exists")
    def test_ot2_internal_syncs_default_only(self, mock_exists: MagicMock) -> None:
        branches = branches_to_sync(BUILDROOT, "26.5.2601", OT2, "internal")
        self.assertEqual(branches, ["opentrons-develop"])
        mock_exists.assert_not_called()

    @patch("automation.go.branch_exists")
    def test_ot2_external_syncs_default_only(self, mock_exists: MagicMock) -> None:
        branches = branches_to_sync(OT2_APP, "26.6.0", OT2, "external")
        self.assertEqual(branches, ["edge"])
        mock_exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
