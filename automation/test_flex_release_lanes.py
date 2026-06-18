"""Tests for independent Flex alpha/beta release flavor lanes."""

from __future__ import annotations

import unittest

from automation.go import get_flex_app_tag_suggestion
from automation.release_tag_catalog import flex_tags_in_lane


class TestFlexTagsInLane(unittest.TestCase):
    def test_alpha_lane_excludes_beta(self) -> None:
        tags = ["ot3@4.0.0-beta.0", "ot3@4.0.0-alpha.3", "ot3@4.0.0-alpha.2"]
        alpha = flex_tags_in_lane(tags, "internal", "alpha", "4.0.0")
        self.assertEqual(alpha, ["ot3@4.0.0-alpha.3", "ot3@4.0.0-alpha.2"])


class TestFlexAppTagSuggestion(unittest.TestCase):
    def test_next_alpha_ignores_beta_at_same_base(self) -> None:
        app_tags = ["ot3@4.0.0-beta.0", "ot3@4.0.0-alpha.3"]
        branch_tags = ["ot3@4.0.0-alpha.3", "ot3@4.0.0-alpha.2"]
        suggestion = get_flex_app_tag_suggestion(
            app_tags,
            branch_tags,
            "internal",
            "alpha",
            "v4.0.0",
            branch="edge",
        )
        self.assertEqual(suggestion.tag, "ot3@4.0.0-alpha.4")
        self.assertEqual(suggestion.latest_in_repo, "ot3@4.0.0-alpha.3")
        self.assertEqual(suggestion.latest_on_branch, "ot3@4.0.0-alpha.3")

    def test_next_beta_when_beta_exists_off_branch(self) -> None:
        app_tags = ["ot3@4.0.0-beta.0", "ot3@4.0.0-alpha.3"]
        branch_tags = ["ot3@4.0.0-alpha.3"]
        suggestion = get_flex_app_tag_suggestion(
            app_tags,
            branch_tags,
            "internal",
            "beta",
            "v4.0.0",
            branch="edge",
        )
        self.assertEqual(suggestion.tag, "ot3@4.0.0-beta.1")
        self.assertIsNotNone(suggestion.note)
        self.assertIsNone(suggestion.latest_on_branch)


if __name__ == "__main__":
    unittest.main()
