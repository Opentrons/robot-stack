"""Tests for release tag stability classification."""

from __future__ import annotations

import unittest

from automation.release_tag_catalog import (
    filter_flex_tags_for_base,
    latest_merged_flex_tag_for_stability,
    latest_tags_by_stability_flex,
    latest_tags_by_stability_ot2,
)


class TestFlexTagCatalog(unittest.TestCase):
    def test_latest_tags_by_stability_internal(self) -> None:
        tags = [
            "ot3@10.0.0-beta.1",
            "ot3@10.0.0-beta.0",
            "ot3@10.0.0-alpha.2",
            "ot3@10.0.0",
            "ot3@9.1.0-beta.0",
        ]
        latest = latest_tags_by_stability_flex(tags, "internal", base="10.0.0")
        self.assertEqual(latest.stable, "ot3@10.0.0")
        self.assertEqual(latest.alpha, "ot3@10.0.0-alpha.2")
        self.assertEqual(latest.beta, "ot3@10.0.0-beta.1")

    def test_filter_tags_for_base(self) -> None:
        tags = ["ot3@10.0.0-beta.0", "ot3@9.1.0-beta.0", "v10.0.0-beta.0"]
        filtered = filter_flex_tags_for_base(tags, "internal", "10.0.0")
        self.assertEqual(filtered, ["ot3@10.0.0-beta.0"])

    def test_latest_merged_flex_tag_for_stability(self) -> None:
        tags = ["ot3@10.0.0-beta.0", "ot3@10.0.0-alpha.1"]
        self.assertEqual(
            latest_merged_flex_tag_for_stability(tags, "internal", "beta", "10.0.0"),
            "ot3@10.0.0-beta.0",
        )


class TestOt2TagCatalog(unittest.TestCase):
    def test_latest_tags_by_stability_internal(self) -> None:
        tags = [
            "internal@26.6.1201-beta",
            "internal@26.6.1201-alpha",
            "internal@26.6.1201",
        ]
        latest = latest_tags_by_stability_ot2(tags, "internal")
        self.assertEqual(latest.stable, "internal@26.6.1201")
        self.assertEqual(latest.alpha, "internal@26.6.1201-alpha")
        self.assertEqual(latest.beta, "internal@26.6.1201-beta")


if __name__ == "__main__":
    unittest.main()
