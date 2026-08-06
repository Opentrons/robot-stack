"""Tests for Flex and OT-2 stable release checklist pages.

Run with:
    uv run python -m unittest automation.test_stable_release_checklist -v
"""

from __future__ import annotations

import unittest

from automation.stable_release_checklist import (
    CONFLUENCE_CHECKLIST,
    CONFLUENCE_MERGEBACK,
    FLEX_STABLE,
    MERGEBACK_GUIDE_PAGE,
    OT2_STABLE,
    render_flex_stable_checklist_page,
    render_ot2_stable_checklist_page,
)


class FlexStableChecklistTests(unittest.TestCase):
    """Flex checklist lists Flex repos, includes PyPI, and keeps its own storage key."""

    def test_flex_repos_and_pypi(self) -> None:
        html = render_flex_stable_checklist_page()
        self.assertIn("flex-stable-checklist.html", html)
        self.assertIn("Flex stable release checklist", html)
        self.assertIn("git merge --ff-only", html)
        self.assertIn(FLEX_STABLE.storage_key, html)
        self.assertIn("pypi.org/project/opentrons", html)
        self.assertIn("opentrons/releases", html)
        self.assertIn("oe-core", html)
        self.assertIn("ot3-firmware", html)
        self.assertIn("opentrons", html)
        self.assertNotIn("buildroot", html)
        self.assertNotIn("opentrons-ot2", html)
        self.assertIn("Isolation caveat", html)
        self.assertIn("do <strong>not</strong> necessarily isolate every release", html)
        self.assertIn("Only if isolated this cycle", html)
        self.assertIn("Always (monorepo)", html)
        self.assertIn(CONFLUENCE_CHECKLIST, html)
        self.assertIn(CONFLUENCE_MERGEBACK, html)
        self.assertIn(MERGEBACK_GUIDE_PAGE, html)
        self.assertIn("ot2-stable-checklist.html", html)

    def test_flex_nav_current(self) -> None:
        html = render_flex_stable_checklist_page()
        self.assertIn('href="flex-stable-checklist.html" class="nav-current"', html)


class Ot2StableChecklistTests(unittest.TestCase):
    """OT-2 checklist lists OT-2 repos, omits PyPI, and keeps its own storage key."""

    def test_ot2_repos_without_pypi(self) -> None:
        html = render_ot2_stable_checklist_page()
        self.assertIn("ot2-stable-checklist.html", html)
        self.assertIn("OT-2 stable release checklist", html)
        self.assertIn(OT2_STABLE.storage_key, html)
        self.assertNotIn("pypi.org", html)
        self.assertNotIn("Validate PyPI", html)
        self.assertIn("opentrons-ot2/releases", html)
        self.assertIn("buildroot", html)
        self.assertIn("opentrons-ot2", html)
        self.assertNotIn("oe-core", html)
        self.assertNotIn("ot3-firmware", html)
        self.assertIn("flex-stable-checklist.html", html)
        self.assertIn("GitHub Release and downloads", html)

    def test_ot2_nav_current(self) -> None:
        html = render_ot2_stable_checklist_page()
        self.assertIn('href="ot2-stable-checklist.html" class="nav-current"', html)

    def test_storage_keys_differ(self) -> None:
        self.assertNotEqual(FLEX_STABLE.storage_key, OT2_STABLE.storage_key)


if __name__ == "__main__":
    unittest.main()
