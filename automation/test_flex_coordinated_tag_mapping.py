"""Unit tests for flex_coordinated_tags mapping helpers."""

from __future__ import annotations

import unittest

from automation.flex_coordinated_tags import (
    coordinated_tag_for_repo,
    is_external_stack_coordination_tag,
    is_firmware_version_tag,
    stack_coordinated_tag_to_firmware_tag,
)


class FlexCoordinatedTagMappingTests(unittest.TestCase):
    def test_external_semver_is_stack_tag(self) -> None:
        self.assertTrue(is_external_stack_coordination_tag("v9.1.0-alpha.7"))

    def test_integer_v70_is_not_stack_tag(self) -> None:
        self.assertFalse(is_external_stack_coordination_tag("v70"))
        self.assertTrue(is_firmware_version_tag("v70"))

    def test_firmware_external_mapping(self) -> None:
        self.assertEqual(
            coordinated_tag_for_repo("ot3-firmware", "v9.1.0-alpha.7"),
            "ex9.1.0-alpha.7",
        )

    def test_firmware_internal_passthrough(self) -> None:
        self.assertEqual(
            coordinated_tag_for_repo("ot3-firmware", "ot3@8.5.0-alpha.1"),
            "ot3@8.5.0-alpha.1",
        )

    def test_existing_ex_tag_not_remapped(self) -> None:
        self.assertIsNone(stack_coordinated_tag_to_firmware_tag("ex9.1.0-alpha.7"))


if __name__ == "__main__":
    unittest.main()
