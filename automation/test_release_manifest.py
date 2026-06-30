"""Tests for releases.json manifest parsing helpers.

Run from repository root:

    uv run python -m unittest automation.test_release_manifest -v
"""

from __future__ import annotations

import unittest

from automation.asset_inventory import RobotReleaseRow, render_robot_manifest_key_badge, render_robot_releases
from automation.release import RobotReleasesCollection, robot_manifest_production_entries, robot_manifest_release_keys


class TestRobotManifestProductionEntries(unittest.TestCase):
    def test_returns_production_when_v2_missing(self) -> None:
        manifest = {
            "production": {
                "9.1.0": {
                    "fullImage": "https://example/9.1.0/full.tar",
                    "system": "https://example/9.1.0/system.zip",
                    "version": "https://example/9.1.0/VERSION.json",
                    "releaseNotes": "https://example/9.1.0/notes.md",
                }
            }
        }
        entries = robot_manifest_production_entries(manifest)
        self.assertEqual(list(entries.keys()), ["9.1.0"])

    def test_returns_production_v2_when_production_missing(self) -> None:
        manifest = {
            "productionV2": {
                "9.1.1-alpha.0": {
                    "fullImage": "https://example/9.1.1-alpha.0/full.tar",
                    "system": "https://example/9.1.1-alpha.0/system.zip",
                    "version": "https://example/9.1.1-alpha.0/VERSION.json",
                    "releaseNotes": "https://example/9.1.1-alpha.0/notes.md",
                }
            }
        }
        entries = robot_manifest_production_entries(manifest)
        self.assertEqual(list(entries.keys()), ["9.1.1-alpha.0"])

    def test_merges_with_v2_winning_on_duplicate_keys(self) -> None:
        manifest = {
            "production": {
                "9.1.0": {
                    "fullImage": "https://example/old/full.tar",
                    "system": "https://example/old/system.zip",
                    "version": "https://example/old/VERSION.json",
                    "releaseNotes": "https://example/old/notes.md",
                }
            },
            "productionV2": {
                "9.1.1-alpha.0": {
                    "fullImage": "https://example/new/full.tar",
                    "system": "https://example/new/system.zip",
                    "version": "https://example/new/VERSION.json",
                    "releaseNotes": "https://example/new/notes.md",
                }
            },
        }
        entries = robot_manifest_production_entries(manifest)
        self.assertEqual(set(entries.keys()), {"9.1.0", "9.1.1-alpha.0"})
        self.assertEqual(entries["9.1.0"]["fullImage"], "https://example/old/full.tar")

    def test_from_production_accepts_merged_entries(self) -> None:
        manifest = {
            "production": {
                "9.1.0": {
                    "fullImage": "https://example/9.1.0/full.tar",
                    "system": "https://example/9.1.0/system.zip",
                    "version": "https://example/9.1.0/VERSION.json",
                    "releaseNotes": "https://example/9.1.0/notes.md",
                }
            },
            "productionV2": {
                "9.1.1-alpha.0": {
                    "fullImage": "https://example/9.1.1-alpha.0/full.tar",
                    "system": "https://example/9.1.1-alpha.0/system.zip",
                    "version": "https://example/9.1.1-alpha.0/VERSION.json",
                    "releaseNotes": "https://example/9.1.1-alpha.0/notes.md",
                }
            },
        }
        coll = RobotReleasesCollection.from_production(robot_manifest_production_entries(manifest))
        self.assertEqual(len(coll.stables), 1)
        self.assertEqual(len(coll.alphas), 1)
        self.assertEqual(coll.latest_alpha().version, "9.1.1-alpha.0")

    def test_release_keys_track_manifest_source(self) -> None:
        manifest = {
            "production": {"9.1.0": {}},
            "productionV2": {"9.1.1-alpha.0": {}},
        }
        keys = robot_manifest_release_keys(manifest)
        self.assertEqual(keys["9.1.0"], "production")
        self.assertEqual(keys["9.1.1-alpha.0"], "productionV2")


class TestRenderRobotManifestKey(unittest.TestCase):
    def test_renders_v2_badge(self) -> None:
        html = render_robot_manifest_key_badge("productionV2")
        self.assertIn("productionV2", html)
        self.assertIn("manifest-key-v2", html)

    def test_robot_table_includes_key_column_when_enabled(self) -> None:
        html = render_robot_releases(
            [
                RobotReleaseRow(
                    version="9.1.1-alpha.0",
                    full_image="https://example/full.tar",
                    system="https://example/system.zip",
                    version_url="https://example/VERSION.json",
                    release_notes="https://example/notes.md",
                    manifest_key="productionV2",
                )
            ],
            "oe-core",
            show_manifest_key=True,
        )
        self.assertIn("<th>Manifest key</th>", html)
        self.assertIn("manifest-key-v2", html)


if __name__ == "__main__":
    unittest.main()
