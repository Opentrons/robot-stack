"""Tests for Flex release strategy documentation pages."""

from __future__ import annotations

from automation.flex_release_strategy_docs import (
    TAG_FLAVORS,
    render_flex_coordinated_tags_page,
    render_flex_release_sequencing_page,
)


def test_coordinated_tags_page_has_six_flavors() -> None:
    """Each pipeline × stability flavor appears on the tagging reference page."""
    assert len(TAG_FLAVORS) == 6
    html = render_flex_coordinated_tags_page()
    assert "flex-coordinated-tags.html" in html
    assert "ot3@8.5.0-beta.1" in html
    assert "ex10.0.0-alpha.2" in html
    assert "Flex coordinated tagging" in html
    assert "validate-release-tags" in html


def test_release_sequencing_page_covers_paired_beta_alpha() -> None:
    """Sequencing page documents updater YAML behavior and beta-then-alpha order."""
    html = render_flex_release_sequencing_page()
    assert "flex-release-sequencing.html" in html
    assert "Ship" in html and "Beta first" in html
    assert "alpha.yml" in html
    assert "Applies to both pipelines" in html
    assert "internal stack" in html
    assert "external stack" in html
    assert "Internal pattern" not in html
    assert "External pattern" not in html
    assert "oe-core/pull/329" in html
