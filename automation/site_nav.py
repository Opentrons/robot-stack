"""Shared site header and navigation for GitHub Pages HTML."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Final, Tuple

INDEX_PAGE: Final[str] = "index.html"
FLEX_EXTERNAL_ASSETS_PAGE: Final[str] = "flex-external-assets.html"


@dataclass(frozen=True)
class SiteLink:
    """One page in the site navigation."""

    filename: str
    title: str


@dataclass(frozen=True)
class ProductNavGroup:
    """Asset and guide links for one robot product (Flex or OT-2)."""

    label: str
    external_assets: SiteLink
    internal_assets: SiteLink
    external_guide: SiteLink
    internal_guide: SiteLink

    @property
    def asset_links(self) -> Tuple[SiteLink, ...]:
        """Asset inventory pages for this product."""
        return (self.external_assets, self.internal_assets)

    @property
    def guide_links(self) -> Tuple[SiteLink, ...]:
        """Release guide pages for this product."""
        return (self.external_guide, self.internal_guide)

    @property
    def all_links(self) -> Tuple[SiteLink, ...]:
        """All pages in this product group."""
        return self.asset_links + self.guide_links


PRODUCT_NAV: Final[Tuple[ProductNavGroup, ...]] = (
    ProductNavGroup(
        "Flex",
        SiteLink(INDEX_PAGE, "External assets"),
        SiteLink("flex-internal-assets.html", "Internal assets"),
        SiteLink("flex-external.html", "External guide"),
        SiteLink("flex-internal.html", "Internal guide"),
    ),
    ProductNavGroup(
        "OT-2",
        SiteLink("ot2-external-assets.html", "External assets"),
        SiteLink("ot2-internal-assets.html", "Internal assets"),
        SiteLink("ot2-external.html", "External guide"),
        SiteLink("ot2-internal.html", "Internal guide"),
    ),
)

ASSET_NAV: Final[Tuple[SiteLink, ...]] = tuple(link for group in PRODUCT_NAV for link in group.asset_links)

GUIDE_NAV: Final[Tuple[SiteLink, ...]] = tuple(link for group in PRODUCT_NAV for link in group.guide_links)

FLEX_STRATEGY_NAV: Final[Tuple[SiteLink, ...]] = (
    SiteLink("flex-coordinated-tags.html", "Coordinated tags"),
    SiteLink("release-channel-hierarchy.html", "Channel hierarchy"),
)


def robot_display_font_css() -> str:
    """Orbitron styling for robot product names (nav, index, asset pages)."""
    return """
    @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@600;700&display=swap");
    .robot-name,
    header.site-header .robot-name,
    .nav-group > .robot-name {
      font-family: "Orbitron", "Eurostile", "Bank Gothic", "Arial Narrow", sans-serif;
      font-weight: 700;
      letter-spacing: 0.06em;
      color: var(--text);
    }
    main h1 .robot-name {
      font-size: 1.65rem;
    }
    li.robot-name.section-title {
      font-size: 1.4rem;
      line-height: 1.2;
    }
    """


def robot_name_html(name: str) -> str:
    """Return escaped robot product name wrapped for display font styling."""
    return f'<span class="robot-name">{html.escape(name)}</span>'


def site_nav_css() -> str:
    """Return shared stylesheet for the site header and navigation."""
    return (
        robot_display_font_css()
        + """
    header.site-header {
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .site-header-inner {
      max-width: 720px;
      margin: 0 auto;
      padding: 0.65rem 1.25rem 0.85rem;
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    nav.site-nav {
      font-size: 0.92rem;
      width: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 0.65rem;
    }
    .nav-columns {
      display: grid;
      grid-template-columns: 10.5rem 10.5rem;
      column-gap: 3rem;
      justify-content: center;
      margin: 0 auto;
    }
    .nav-strategy-row {
      display: flex;
      justify-content: center;
      width: 100%;
    }
    .nav-group {
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      align-items: center;
      text-align: center;
    }
    .nav-group > .robot-name {
      font-size: 1.5rem;
      line-height: 1.2;
      margin: 0 0 0.15rem;
    }
    .site-header-inner {
      padding: 0.65rem 1.25rem 0.85rem;
    }
    .nav-block {
      display: flex;
      flex-direction: column;
      gap: 0.25rem;
      align-items: center;
      width: 100%;
    }
    .nav-block + .nav-block {
      margin-top: 0.35rem;
    }
    .nav-kind {
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .nav-block a {
      display: block;
      color: var(--accent);
      text-decoration: none;
      line-height: 1.35;
      text-align: center;
    }
    .nav-block a:hover { text-decoration: underline; }
    .nav-block a.nav-current,
    .nav-block a[aria-current="page"] {
      font-weight: 700;
      color: var(--text);
      text-decoration: none;
      cursor: default;
    }
    .nav-block a.nav-current:hover,
    .nav-block a[aria-current="page"]:hover {
      text-decoration: none;
      color: var(--text);
    }
    @media (max-width: 520px) {
      .nav-columns {
        grid-template-columns: 1fr 1fr;
        column-gap: 1.25rem;
        width: 100%;
        max-width: 20rem;
      }
      .nav-group > .robot-name {
        font-size: 1.2rem;
      }
    }
    """
    )


def nav_link_is_current(item: SiteLink, current_page: str) -> bool:
    """Return True when this nav item matches the active page (including index alias)."""
    if item.filename == current_page:
        return True
    return item.filename == INDEX_PAGE and current_page == FLEX_EXTERNAL_ASSETS_PAGE


def _render_nav_link(item: SiteLink, current_page: str) -> str:
    is_current = nav_link_is_current(item, current_page)
    current_attr = ' aria-current="page"' if is_current else ""
    current_class = ' class="nav-current"' if is_current else ""
    return f'<a href="{html.escape(item.filename)}"{current_class}{current_attr}>{html.escape(item.title)}</a>'


def _render_nav_block(kind: str, links: Tuple[SiteLink, ...], current_page: str) -> str:
    """Render a vertical block of links under a section label."""
    link_html = "".join(_render_nav_link(item, current_page) for item in links)
    return f'<div class="nav-block"><span class="nav-kind">{html.escape(kind)}</span>{link_html}</div>'


def render_site_header(current_page: str) -> str:
    """Render the sticky site header with Flex / OT-2 navigation on every page."""
    groups: list[str] = []
    for group in PRODUCT_NAV:
        groups.append(
            f'<div class="nav-group">'
            f"{robot_name_html(group.label)}"
            f"{_render_nav_block('Assets', group.asset_links, current_page)}"
            f"{_render_nav_block('Guides', group.guide_links, current_page)}"
            f"</div>"
        )

    columns = f'<div class="nav-columns">{"".join(groups)}</div>'
    strategy_row = f'<div class="nav-strategy-row">{_render_nav_block("Strategy", FLEX_STRATEGY_NAV, current_page)}</div>'

    return (
        f'<header class="site-header"><div class="site-header-inner">'
        f'<nav class="site-nav" aria-label="Site">{columns}{strategy_row}</nav>'
        f"</div></header>"
    )
