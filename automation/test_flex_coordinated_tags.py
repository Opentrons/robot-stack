"""Tests for Flex coordinated release tagging in go.py."""

from __future__ import annotations

import unittest

from automation.go import (
    ReleasePath,
    RepoSpec,
    RepoState,
    get_flex_coordinated_stack_tag_plan,
    get_next_flex_app_tag_command,
    normalize_flex_stability,
    tags_merged_on_branch,
)


class NormalizeFlexStabilityTests(unittest.TestCase):
    def test_unstable_maps_to_alpha(self) -> None:
        self.assertEqual(normalize_flex_stability("unstable"), "alpha")

    def test_stable_unchanged(self) -> None:
        self.assertEqual(normalize_flex_stability("stable"), "stable")


class FlexAppTagTests(unittest.TestCase):
    def test_internal_beta_tag(self) -> None:
        state = RepoState(
            branch_tags={
                "edge": {
                    "ot3@": ["ot3@8.5.0-beta.0"],
                }
            }
        )
        tag = get_next_flex_app_tag_command(state, "edge", "internal", "beta", "v8.5.0")
        self.assertEqual(tag, "ot3@8.5.0-beta.1")

    def test_external_alpha_tag(self) -> None:
        state = RepoState(branch_tags={"chore_release-10.0.0": {"v": ["v10.0.0-alpha.0"]}})
        tag = get_next_flex_app_tag_command(
            state,
            "chore_release-10.0.0",
            "external",
            "alpha",
            "v10.0.0",
        )
        self.assertEqual(tag, "v10.0.0-alpha.1")


class FlexCoordinatedStackTagPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.release_path = ReleasePath(
            name="flex",
            label="Flex",
            taggable_repo="opentrons",
            repo_names=frozenset({"opentrons", "oe-core", "ot3-firmware"}),
            stack_tag_repos=("ot3-firmware", "oe-core"),
        )
        self.oe_core = RepoSpec(
            name="oe-core",
            repo_url="https://github.com/Opentrons/oe-core.git",
            local_path=__import__("pathlib").Path("./oe-core"),
            default_branch="main",
            external_tag_pattern="v",
            internal_tag_pattern="ot3@",
        )

    def test_uses_same_tag_as_app(self) -> None:
        state = RepoState(branch_tags={"main": {"ot3@": []}})
        results = {
            "opentrons": RepoState(branch_tags={"edge": {"ot3@": []}}),
            "oe-core": state,
        }
        plan = get_flex_coordinated_stack_tag_plan(
            self.oe_core,
            state,
            "v8.5.0",
            "internal",
            "beta",
            self.release_path,
            results,
            "ot3@8.5.0-beta.1",
        )
        self.assertTrue(plan.needs_tag)
        self.assertEqual(plan.next_tag, "ot3@8.5.0-beta.1")

    def test_merged_tags_include_coordinated_prefix(self) -> None:
        state = RepoState(
            branch_tags={
                "main": {
                    "ot3@": ["ot3@8.5.0-beta.0"],
                    "v": [],
                }
            }
        )
        merged = tags_merged_on_branch(state, "main")
        self.assertIn("ot3@8.5.0-beta.0", merged)


if __name__ == "__main__":
    unittest.main()
