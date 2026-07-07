"""Tests for release asset inventory sorting and parsing.

Run from repository root:

    uv run python -m unittest automation.test_asset_inventory -v
"""

from __future__ import annotations

import unittest

from automation.asset_inventory import sort_versions_desc
from automation.ot2_assets import OT2_CONFIG


class TestOt2VersionSort(unittest.TestCase):
    def test_calendar_external_sorts_above_legacy_semver(self) -> None:
        versions = [
            "8.9.9-alpha.13",
            "8.9.9-alpha.12",
            "26.6.0-alpha.4",
            "26.6.0-alpha.3",
            "26.6.0",
        ]
        sorted_versions = sort_versions_desc(versions, OT2_CONFIG)
        self.assertEqual(
            sorted_versions,
            [
                "26.6.0",
                "26.6.0-alpha.4",
                "26.6.0-alpha.3",
                "8.9.9-alpha.13",
                "8.9.9-alpha.12",
            ],
        )

    def test_calendar_dev_sorts_above_legacy_semver(self) -> None:
        versions = [
            "8.9.9-alpha.13",
            "8.8.2",
            "26.5.19",
            "26.5.18.dev1",
            "26.5.18",
        ]
        sorted_versions = sort_versions_desc(versions, OT2_CONFIG)
        self.assertEqual(
            sorted_versions[:3],
            ["26.5.19", "26.5.18.dev1", "26.5.18"],
        )
        self.assertEqual(set(sorted_versions[3:]), {"8.9.9-alpha.13", "8.8.2"})

    def test_external_calendar_sorts_above_dev_patch_builds(self) -> None:
        versions = ["26.5.19", "26.6.0-alpha.4", "26.6.0"]
        sorted_versions = sort_versions_desc(versions, OT2_CONFIG)
        self.assertEqual(sorted_versions, ["26.6.0", "26.6.0-alpha.4", "26.5.19"])

    def test_stable_sorts_above_alpha_on_same_base(self) -> None:
        versions = ["26.6.0-alpha.4", "26.6.0-alpha.0", "26.6.0"]
        sorted_versions = sort_versions_desc(versions, OT2_CONFIG)
        self.assertEqual(sorted_versions, ["26.6.0", "26.6.0-alpha.4", "26.6.0-alpha.0"])


if __name__ == "__main__":
    unittest.main()
