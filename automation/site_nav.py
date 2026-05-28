"""Shared site header and navigation for GitHub Pages HTML."""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Final, Tuple

INDEX_PAGE: Final[str] = "index.html"


@dataclass(frozen=True)
class SiteLink:
    """One page in the site navigation."""

    filename: str
    title: str


ASSET_NAV: Final[Tuple[SiteLink, ...]] = (
    SiteLink("flex-external-assets.html", "Flex external assets"),
    SiteLink("flex-internal-assets.html", "Flex internal assets"),
    SiteLink("ot2-external-assets.html", "OT-2 external assets"),
    SiteLink("ot2-internal-assets.html", "OT-2 internal assets"),
)

GUIDE_NAV: Final[Tuple[SiteLink, ...]] = (
    SiteLink("flex-external.html", "Flex external guide"),
    SiteLink("flex-internal.html", "Flex internal guide"),
    SiteLink("ot2-external.html", "OT-2 external guide"),
    SiteLink("ot2-internal.html", "OT-2 internal guide"),
)


def site_nav_css() -> str:
    """Return shared stylesheet for the site header and navigation."""
    return """
    header.site-header {
      border-bottom: 1px solid var(--border);
      background: var(--panel);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .site-header-inner {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0.85rem 1.25rem 1rem;
    }
    .site-brand {
      font-size: 1rem;
      font-weight: 700;
      margin: 0 0 0.65rem;
      letter-spacing: 0.01em;
    }
    .site-brand a {
      color: var(--text);
      text-decoration: none;
    }
    .site-brand a:hover { color: var(--accent); }
    nav.site-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem 0.85rem;
      align-items: center;
      font-size: 0.92rem;
    }
    nav.site-nav .nav-label {
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-right: 0.15rem;
    }
    nav.site-nav a {
      color: var(--accent);
      text-decoration: none;
      white-space: nowrap;
    }
    nav.site-nav a:hover { text-decoration: underline; }
    nav.site-nav a[aria-current="page"] {
      font-weight: 700;
      color: var(--text);
    }
    """


def render_site_header(current_page: str) -> str:
    """Render the sticky site header with home, asset, and guide links."""
    home_current = ' aria-current="page"' if current_page == INDEX_PAGE else ""
    home = f'<a href="{INDEX_PAGE}"{home_current}>Home</a>'

    def link_group(label: str, items: Tuple[SiteLink, ...]) -> str:
        parts = [f'<span class="nav-label">{html.escape(label)}</span>']
        for item in items:
            current = ' aria-current="page"' if item.filename == current_page else ""
            parts.append(f'<a href="{html.escape(item.filename)}"{current}>{html.escape(item.title)}</a>')
        return "".join(parts)

    asset_links = link_group("Assets", ASSET_NAV)
    guide_links = link_group("Guides", GUIDE_NAV)
    return (
        f'<header class="site-header"><div class="site-header-inner">'
        f'<p class="site-brand"><a href="{INDEX_PAGE}">Opentrons release tooling</a></p>'
        f'<nav class="site-nav" aria-label="Site">{home}{asset_links}{guide_links}</nav>'
        f"</div></header>"
    )
