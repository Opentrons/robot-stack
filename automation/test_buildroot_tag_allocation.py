"""Tests for buildroot external tag suggestion (robot-stack release planning only).

Run from repository root:

    uv run python -m unittest automation.test_buildroot_tag_allocation -v
"""

from __future__ import annotations

import unittest

from automation.go import (
    RepoState,
    get_next_buildroot_tag_command,
    is_buildroot_traditional_external_tag,
    latest_buildroot_external_tag,
)


class TestBuildrootTraditionalExternalTag(unittest.TestCase):
    def test_accepts_traditional_stable(self) -> None:
        self.assertTrue(is_buildroot_traditional_external_tag("v1.19.9"))

    def test_rejects_calendar_external(self) -> None:
        self.assertFalse(is_buildroot_traditional_external_tag("v26.5.0"))

    def test_accepts_traditional_prerelease(self) -> None:
        self.assertTrue(is_buildroot_traditional_external_tag("v1.19.9-alpha.0"))


class TestLatestBuildrootExternalTag(unittest.TestCase):
    def test_ignores_calendar_tags(self) -> None:
        state = RepoState(
            branch_tags={
                "opentrons-develop": {
                    "v": ["v26.5.0", "v1.19.9", "v1.19.8"],
                    "internal@": [],
                }
            }
        )
        self.assertEqual(latest_buildroot_external_tag(state, "opentrons-develop"), "v1.19.9")


class TestGetNextBuildrootExternalTag(unittest.TestCase):
    def test_patch_bumps_latest_traditional_tag(self) -> None:
        state = RepoState(
            branch_tags={
                "opentrons-develop": {
                    "v": ["v1.19.9", "v1.19.8"],
                    "internal@": [],
                }
            }
        )
        tag = get_next_buildroot_tag_command(state, "opentrons-develop", "external", "26.5.0")
        self.assertEqual(tag, "v1.19.10")

    def test_raises_when_no_traditional_tags(self) -> None:
        state = RepoState(branch_tags={"opentrons-develop": {"v": ["v26.5.0"], "internal@": []}})
        with self.assertRaises(ValueError):
            get_next_buildroot_tag_command(state, "opentrons-develop", "external", "26.5.0")


if __name__ == "__main__":
    unittest.main()
