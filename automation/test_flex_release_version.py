"""Tests for Flex default release version inference.

Run from repository root:

    uv run python -m unittest automation.test_flex_release_version -v
"""

from __future__ import annotations

import unittest

from automation.flex_release_version import (
    flex_base_from_app_tags,
    flex_base_from_internal_app_tags,
    flex_default_release_version,
    flex_external_default_release_version,
    flex_internal_default_release_version,
    highest_chore_release_version,
    parse_chore_release_version,
)


class TestParseChoreReleaseVersion(unittest.TestCase):
    def test_accepts_standard_branch(self) -> None:
        self.assertEqual(parse_chore_release_version("chore_release-9.1.0"), "9.1.0")

    def test_rejects_prefixed_variants(self) -> None:
        self.assertIsNone(parse_chore_release_version("candidate-chore_release-8.5.0"))
        self.assertIsNone(parse_chore_release_version("e2e-app-start-chore_release-9.0.0"))


class TestHighestChoreReleaseVersion(unittest.TestCase):
    def test_picks_highest_semver(self) -> None:
        branches = [
            "chore_release-8.5.0",
            "chore_release-9.1.0",
            "chore_release-9.0.0",
            "candidate-chore_release-8.5.0",
        ]
        self.assertEqual(highest_chore_release_version(branches), "9.1.0")


class TestFlexBaseFromAppTags(unittest.TestCase):
    def test_picks_highest_alpha_base(self) -> None:
        tags = ["v8.5.0", "v9.0.0-alpha.20", "v9.1.0-alpha.1"]
        self.assertEqual(flex_base_from_app_tags(tags), "9.1.0")


class TestFlexBaseFromInternalAppTags(unittest.TestCase):
    def test_picks_highest_ot3_base(self) -> None:
        tags = ["ot3@2.8.0-alpha.3", "ot3@3.1.0-alpha.5", "ot3@3.0.0-alpha.0"]
        self.assertEqual(flex_base_from_internal_app_tags(tags), "3.1.0")


class TestFlexExternalDefaultReleaseVersion(unittest.TestCase):
    def test_prefers_branches_over_tags(self) -> None:
        version = flex_external_default_release_version(
            ["chore_release-9.1.0", "chore_release-8.5.0"],
            app_tags=["v8.5.0"],
        )
        self.assertEqual(version, "v9.1.0")

    def test_falls_back_to_tags(self) -> None:
        version = flex_external_default_release_version([], app_tags=["v9.1.0-alpha.1"])
        self.assertEqual(version, "v9.1.0")


class TestFlexInternalDefaultReleaseVersion(unittest.TestCase):
    def test_uses_ot3_tags(self) -> None:
        version = flex_internal_default_release_version(["ot3@3.1.0-alpha.5"])
        self.assertEqual(version, "v3.1.0")

    def test_returns_none_without_tags(self) -> None:
        self.assertIsNone(flex_internal_default_release_version([]))


class TestFlexDefaultReleaseVersion(unittest.TestCase):
    def test_alias_for_external(self) -> None:
        version = flex_default_release_version(
            ["chore_release-9.1.0"],
            app_tags=["v8.5.0"],
        )
        self.assertEqual(version, "v9.1.0")


if __name__ == "__main__":
    unittest.main()
