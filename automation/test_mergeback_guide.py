"""Tests for the mergeback guide page.

Run with:
    uv run python -m unittest automation.test_mergeback_guide -v
"""

from __future__ import annotations

import unittest

from automation.mergeback_guide import (
    CONFLUENCE_MERGEBACK_FF,
    CONFLUENCE_MERGE_MAGIC,
    MERGEBACK_PAGE,
    render_mergeback_guide_page,
)


class MergebackGuideTests(unittest.TestCase):
    """Guide covers CLI mergeback, no-squash rule, and redo when default moves."""

    def test_mergeback_guide_content(self) -> None:
        html = render_mergeback_guide_page()
        self.assertIn(MERGEBACK_PAGE, html)
        self.assertIn("Mergeback guide", html)
        self.assertIn("Never squash", html)
        self.assertIn("git merge origin/release", html)
        self.assertIn("git push origin HEAD:edge", html)
        self.assertIn("merge-release-into-edge-take2", html)
        self.assertIn("git checkout merge-release-into-edge -- '**'", html)
        self.assertIn("when that repo used isolation", html)
        self.assertIn("do not necessarily", html)
        self.assertIn("isolate every release", html)
        self.assertIn("git merge --ff-only", html)
        self.assertIn("oe-core", html)
        self.assertIn("buildroot", html)
        self.assertIn("opentrons-develop", html)
        self.assertIn(CONFLUENCE_MERGE_MAGIC, html)
        self.assertIn(CONFLUENCE_MERGEBACK_FF, html)
        self.assertIn("flex-stable-checklist.html", html)
        self.assertIn("ot2-stable-checklist.html", html)
        self.assertIn('href="mergeback-guide.html" class="nav-current"', html)


if __name__ == "__main__":
    unittest.main()
