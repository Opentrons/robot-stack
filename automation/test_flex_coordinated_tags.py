"""Tests for Flex coordinated release tagging."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.flex_coordinated_tags import (
    coordinated_tag_for_repo,
    is_firmware_version_tag,
    stack_coordinated_tag_to_firmware_tag,
)
from automation.go import (
    ReleasePath,
    RepoSpec,
    RepoState,
    all_integer_firmware_version_numbers,
    get_flex_app_tag_suggestion,
    get_flex_coordinated_stack_tag_plan,
    get_next_ot3_firmware_version_tag,
    normalize_flex_stability,
    tags_merged_on_branch,
)


class FlexTagMappingTests(unittest.TestCase):
    def test_external_maps_to_ex(self) -> None:
        self.assertEqual(
            stack_coordinated_tag_to_firmware_tag("v9.1.0-alpha.7"),
            "ex9.1.0-alpha.7",
        )

    def test_internal_unchanged(self) -> None:
        self.assertIsNone(stack_coordinated_tag_to_firmware_tag("ot3@8.5.0-alpha.1"))

    def test_integer_version_tag_not_mapped(self) -> None:
        self.assertIsNone(stack_coordinated_tag_to_firmware_tag("v70"))
        self.assertTrue(is_firmware_version_tag("v70"))

    def test_coordinated_tag_for_firmware_external(self) -> None:
        self.assertEqual(
            coordinated_tag_for_repo("ot3-firmware", "v10.0.0-beta.1"),
            "ex10.0.0-beta.1",
        )

    def test_coordinated_tag_for_oe_core_external(self) -> None:
        self.assertEqual(
            coordinated_tag_for_repo("oe-core", "v10.0.0-beta.1"),
            "v10.0.0-beta.1",
        )


class NormalizeFlexStabilityTests(unittest.TestCase):
    def test_unstable_maps_to_alpha(self) -> None:
        self.assertEqual(normalize_flex_stability("unstable"), "alpha")

    def test_stable_unchanged(self) -> None:
        self.assertEqual(normalize_flex_stability("stable"), "stable")


class FlexAppTagTests(unittest.TestCase):
    def test_internal_beta_tag_uses_lane_counter(self) -> None:
        app_tags = ["ot3@8.5.0-beta.0", "ot3@8.5.0-alpha.1"]
        suggestion = get_flex_app_tag_suggestion(
            app_tags,
            [],
            "internal",
            "beta",
            "v8.5.0",
            branch="edge",
        )
        self.assertEqual(suggestion.tag, "ot3@8.5.0-beta.1")

    def test_internal_alpha_independent_of_beta(self) -> None:
        app_tags = ["ot3@10.0.0-beta.0", "ot3@10.0.0-alpha.2"]
        suggestion = get_flex_app_tag_suggestion(
            app_tags,
            ["ot3@10.0.0-alpha.2"],
            "internal",
            "alpha",
            "v10.0.0",
            branch="edge",
        )
        self.assertEqual(suggestion.tag, "ot3@10.0.0-alpha.3")

    def test_external_alpha_tag(self) -> None:
        app_tags = ["v10.0.0-alpha.0"]
        suggestion = get_flex_app_tag_suggestion(
            app_tags,
            [],
            "external",
            "alpha",
            "v10.0.0",
            branch="chore_release-10.0.0",
        )
        self.assertEqual(suggestion.tag, "v10.0.0-alpha.1")


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
            local_path=Path("./oe-core"),
            default_branch="main",
            external_tag_pattern="v",
            internal_tag_pattern="ot3@",
        )
        self.firmware = RepoSpec(
            name="ot3-firmware",
            repo_url="https://github.com/Opentrons/ot3-firmware.git",
            local_path=Path("./ot3-firmware"),
            default_branch="main",
            external_tag_pattern="v",
            internal_tag_pattern="ot3@",
        )

    def test_oe_core_uses_same_stack_tag(self) -> None:
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

    def test_firmware_external_uses_ex_tag(self) -> None:
        state = RepoState(branch_tags={"main": {"v": ["v69"], "ot3@": []}})
        results = {
            "opentrons": RepoState(branch_tags={"chore_release-9.1.0": {"v": []}}),
            "ot3-firmware": state,
        }
        with (
            patch(
                "automation.go.firmware_version_tag_for_release_commit",
                return_value=(None, "v70"),
            ),
        ):
            plan = get_flex_coordinated_stack_tag_plan(
                self.firmware,
                state,
                "v9.1.0",
                "external",
                "alpha",
                self.release_path,
                results,
                "v9.1.0-alpha.7",
            )
        self.assertTrue(plan.needs_tag)
        self.assertEqual(plan.next_tag, "ex9.1.0-alpha.7")
        self.assertEqual(plan.secondary_tags, ("v70",))

    def test_firmware_coordination_only_when_vn_on_commit(self) -> None:
        state = RepoState(branch_tags={"main": {"v": ["v70"], "ot3@": []}})
        results = {
            "opentrons": RepoState(branch_tags={"edge": {"ot3@": []}}),
            "ot3-firmware": state,
        }
        with patch(
            "automation.go.firmware_version_tag_for_release_commit",
            return_value=("v70", None),
        ):
            plan = get_flex_coordinated_stack_tag_plan(
                self.firmware,
                state,
                "v4.0.0",
                "internal",
                "beta",
                self.release_path,
                results,
                "ot3@4.0.0-beta.1",
            )
        self.assertTrue(plan.needs_tag)
        self.assertEqual(plan.next_tag, "ot3@4.0.0-beta.1")
        self.assertEqual(plan.secondary_tags, ())
        self.assertEqual(plan.existing_firmware_version_tag, "v70")

    @patch("automation.go.run_git_command", return_value="v69\nv70\nv71\n")
    def test_next_firmware_version_uses_whole_repo(self, _mock_git: object) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_path = Path(tmp)
            (repo_path / ".git").mkdir()
            repo = RepoSpec(
                name="ot3-firmware",
                repo_url="https://github.com/Opentrons/ot3-firmware.git",
                local_path=repo_path,
                default_branch="main",
                external_tag_pattern="v",
                internal_tag_pattern="ot3@",
            )
            numbers = all_integer_firmware_version_numbers(repo)
            self.assertEqual(numbers, [69, 70, 71])
            self.assertEqual(get_next_ot3_firmware_version_tag(repo), "v72")

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
