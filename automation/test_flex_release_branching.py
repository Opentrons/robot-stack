"""Tests for release branch selection by path, channel, and overrides."""

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
    resolve_release_branch,
)
from automation.release_branch_config import ReleaseBranchConfig

FLEX = RELEASE_PATHS["flex"]
OT2 = RELEASE_PATHS["ot2"]
OPENTRONS = repo_by_name("opentrons")
OE_CORE = repo_by_name("oe-core")
OT2_APP = repo_by_name("opentrons-ot2")
BUILDROOT = repo_by_name("buildroot")

INTERNAL_BETA_BRANCHES = ReleaseBranchConfig(
    app_branch="chore_release-10.0.0-beta",
    stack_branches={"oe-core": "main", "ot3-firmware": "main"},
)


class TestChoreReleaseBranch(unittest.TestCase):
    def test_strips_v_prefix(self) -> None:
        self.assertEqual(chore_release_branch("v9.1.0"), "chore_release-9.1.0")

    def test_is_chore_release_branch(self) -> None:
        self.assertTrue(is_chore_release_branch("chore_release-9.1.0"))
        self.assertFalse(is_chore_release_branch("edge"))


class TestFormatTagCommands(unittest.TestCase):
    def test_includes_checkout_on_non_default_branch(self) -> None:
        commands = format_tag_commands(
            "v0.10.2",
            "v9.1.0-alpha.4",
            branch="chore_release-9.1.0",
            default_branch="edge",
        )
        self.assertEqual(commands[0], ("Checkout", "git checkout chore_release-9.1.0"))
        self.assertEqual(commands[1][0], "Create")

    def test_omits_checkout_on_default_branch(self) -> None:
        commands = format_tag_commands(
            "ot3@8.5.0",
            "ot3@8.5.0",
            branch="edge",
            default_branch="edge",
        )
        self.assertEqual(commands[0][0], "Create")
        self.assertEqual(len(commands), 3)


class TestReleaseOnDefaultBranch(unittest.TestCase):
    def test_true_for_flex_internal_without_overrides(self) -> None:
        self.assertTrue(release_on_default_branch(FLEX, "internal"))

    def test_false_when_branch_overrides_present(self) -> None:
        self.assertFalse(release_on_default_branch(FLEX, "internal", INTERNAL_BETA_BRANCHES))

    def test_false_for_flex_external(self) -> None:
        self.assertFalse(release_on_default_branch(FLEX, "external"))

    def test_true_for_ot2_internal(self) -> None:
        self.assertTrue(release_on_default_branch(OT2, "internal"))

    def test_true_for_ot2_external(self) -> None:
        self.assertTrue(release_on_default_branch(OT2, "external"))


class TestResolveReleaseBranch(unittest.TestCase):
    def test_flex_internal_app_override(self) -> None:
        branch = resolve_release_branch(
            OPENTRONS,
            "v10.0.0",
            FLEX,
            "internal",
            INTERNAL_BETA_BRANCHES,
        )
        self.assertEqual(branch, "chore_release-10.0.0-beta")

    def test_flex_internal_stack_override(self) -> None:
        branch = resolve_release_branch(
            OE_CORE,
            "v10.0.0",
            FLEX,
            "internal",
            INTERNAL_BETA_BRANCHES,
        )
        self.assertEqual(branch, "main")

    @patch("automation.go.branch_exists", return_value=True)
    def test_flex_external_prefers_chore_release(self, _mock: object) -> None:
        branch = resolve_release_branch(OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branch, "chore_release-9.1.0")


class TestReleaseBranchForRepo(unittest.TestCase):
    def test_flex_internal_uses_default_branch(self) -> None:
        state = RepoState(branch_tags={"edge": {}, "chore_release-9.1.0": {}})
        branch = release_branch_for_repo(state, OPENTRONS, "v9.1.0", FLEX, "internal")
        self.assertEqual(branch, "edge")

    def test_flex_internal_honors_app_branch_override(self) -> None:
        state = RepoState(
            branch_tags={
                "edge": {},
                "chore_release-10.0.0-beta": {},
            }
        )
        branch = release_branch_for_repo(
            state,
            OPENTRONS,
            "v10.0.0",
            FLEX,
            "internal",
            INTERNAL_BETA_BRANCHES,
        )
        self.assertEqual(branch, "chore_release-10.0.0-beta")

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


class TestBranchesToSync(unittest.TestCase):
    @patch("automation.go.branch_exists", return_value=True)
    def test_flex_external_syncs_chore_release_when_remote_has_it(self, _mock: object) -> None:
        branches = branches_to_sync(OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branches, ["edge", "chore_release-9.1.0"])

    @patch("automation.go.branch_exists", return_value=False)
    def test_flex_external_omits_chore_release_when_missing(self, _mock: object) -> None:
        branches = branches_to_sync(OPENTRONS, "v9.1.0", FLEX, "external")
        self.assertEqual(branches, ["edge"])

    def test_flex_internal_with_override_syncs_custom_branch(self) -> None:
        branches = branches_to_sync(
            OPENTRONS,
            "v10.0.0",
            FLEX,
            "internal",
            INTERNAL_BETA_BRANCHES,
        )
        self.assertEqual(branches, ["edge", "chore_release-10.0.0-beta"])

    @patch("automation.go.branch_exists")
    def test_flex_internal_syncs_default_only_without_override(self, mock_exists: MagicMock) -> None:
        branches = branches_to_sync(OPENTRONS, "v9.1.0", FLEX, "internal")
        self.assertEqual(branches, ["edge"])
        mock_exists.assert_not_called()


if __name__ == "__main__":
    unittest.main()
