"""Tests for OT-2 release tag allocation (robot-stack release planning only).

Run from repository root:

    uv run python -m unittest automation.test_ot2_tag_allocation -v
"""

from __future__ import annotations

import unittest
from datetime import date

from automation.ot2_tag_allocation import (
    allocate_next_external_tag,
    allocate_next_internal_tag,
)


class TestAllocateNextInternalTag(unittest.TestCase):
    def test_next_alpha_after_same_day_tags(self) -> None:
        existing = {
            "internal@26.5.2601-alpha",
            "internal@26.5.2601",
        }
        tag = allocate_next_internal_tag(
            existing,
            "alpha",
            release_date=date(2026, 5, 26),
        )
        self.assertEqual(tag, "internal@26.5.2602-alpha")


class TestAllocateNextExternalTag(unittest.TestCase):
    def test_next_stable_in_month(self) -> None:
        existing = {"v26.6.0", "v26.6.1"}
        tag = allocate_next_external_tag(
            existing,
            "stable",
            release_date=date(2026, 6, 15),
        )
        self.assertEqual(tag, "v26.6.2")

    def test_next_alpha_on_base(self) -> None:
        existing = {"v26.6.0-alpha.0", "v26.6.0"}
        tag = allocate_next_external_tag(
            existing,
            "alpha",
            base_version="26.6.0",
            release_date=date(2026, 6, 15),
        )
        self.assertEqual(tag, "v26.6.0-alpha.1")


if __name__ == "__main__":
    unittest.main()
