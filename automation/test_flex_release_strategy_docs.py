"""Tests for Flex release strategy documentation pages."""

from __future__ import annotations

from automation.flex_release_strategy_docs import (
    TAG_FLAVORS,
    render_flex_coordinated_tags_page,
    render_release_channel_hierarchy_page,
)


def test_coordinated_tags_page_has_six_flavors() -> None:
    """Each pipeline × stability flavor appears on the tagging reference page."""
    assert len(TAG_FLAVORS) == 6
    html = render_flex_coordinated_tags_page()
    assert "flex-coordinated-tags.html" in html
    assert "ot3@8.5.0-beta.1" in html
    assert "ex10.0.0-alpha.2" in html
    assert "independent lanes" in html
    assert "release-channel-hierarchy.html" in html
    assert "Flex coordinated tagging" in html
    assert "validate-release-tags" in html


def test_release_channel_hierarchy_page_covers_updater_model() -> None:
    """Channel hierarchy page documents traditional model and YAML cascade for Flex and OT-2."""
    html = render_release_channel_hierarchy_page()
    assert "release-channel-hierarchy.html" in html
    assert "Release channel hierarchy" in html
    assert "traditional release model" in html.lower()
    assert "Parallel flavors" in html
    assert "alpha.yml" in html
    assert "beta.yml" in html
    assert "latest.yml" in html
    assert "Flex" in html and "OT-2" in html
    assert "beta before alpha" in html.lower()
    assert "validate-release-tags" not in html
    assert "ot3@" not in html
