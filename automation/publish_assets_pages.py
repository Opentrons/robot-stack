#!/usr/bin/env python3
"""Generate Flex and OT-2 asset inventory HTML for GitHub Pages."""

from __future__ import annotations

import argparse
import asyncio
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

from automation.asset_inventory import (
    ReleasePlatformConfig,
    fetch_channel_snapshot,
    render_html,
    serve_report,
    write_report,
)
from automation.asset_urls import AssetChannel
from automation.flex_assets import FLEX_CONFIG
from automation.flex_urls import FLEX_EXTERNAL, FLEX_INTERNAL
from automation.ot2_assets import OT2_CONFIG
from automation.ot2_urls import OT2_EXTERNAL, OT2_INTERNAL
from automation.release_guides import publish_release_guides
from automation.site_nav import ASSET_NAV, GUIDE_NAV, INDEX_PAGE, render_site_header, site_nav_css

DEFAULT_OUTPUT_DIR = Path("pages")
DEFAULT_LIMIT = 15
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ChannelAssetPage:
    """One per-channel asset inventory page."""

    filename: str
    config: ReleasePlatformConfig
    channel: AssetChannel


CHANNEL_ASSET_PAGES: tuple[ChannelAssetPage, ...] = (
    ChannelAssetPage("flex-external-assets.html", FLEX_CONFIG, FLEX_EXTERNAL),
    ChannelAssetPage("flex-internal-assets.html", FLEX_CONFIG, FLEX_INTERNAL),
    ChannelAssetPage("ot2-external-assets.html", OT2_CONFIG, OT2_EXTERNAL),
    ChannelAssetPage("ot2-internal-assets.html", OT2_CONFIG, OT2_INTERNAL),
)


def render_index(generated_at: str, limit: int) -> str:
    """Render a landing page linking to channel asset reports and release guides."""
    asset_items = "".join(
        f"""
      <li>
        <a href="{html.escape(item.filename)}">{html.escape(item.title)}</a>
      </li>"""
        for item in ASSET_NAV
    )
    guide_items = "".join(
        f"""
      <li>
        <a href="{html.escape(item.filename)}">{html.escape(item.title)}</a>
        <div class="meta">Tag logic and manifest URLs for <code>just go</code></div>
      </li>"""
        for item in GUIDE_NAV
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Opentrons release assets</title>
  <style>
    {site_nav_css()}
    :root {{
      color-scheme: light dark;
      --bg: #0f1419;
      --panel: #1a222d;
      --text: #e7ecf3;
      --muted: #9aa7b8;
      --accent: #60a5fa;
      --border: #2b3645;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f6f8fb;
        --panel: #ffffff;
        --text: #1f2937;
        --muted: #6b7280;
        --accent: #2563eb;
        --border: #d1d5db;
      }}
    }}
    body {{
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 2rem 1.25rem 4rem;
    }}
    h1 {{ margin-top: 0; }}
    p {{ color: var(--muted); }}
    ul {{
      list-style: none;
      padding: 0;
      display: grid;
      gap: 1rem;
    }}
    li {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem 1.25rem;
    }}
    li.section-title {{
      background: transparent;
      border: none;
      padding: 0.5rem 0 0;
      font-size: 0.85rem;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    a {{
      color: var(--accent);
      font-size: 1.1rem;
      font-weight: 600;
      text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}
    .meta {{ margin-top: 0.35rem; font-size: 0.95rem; }}
  </style>
</head>
<body>
  {render_site_header(INDEX_PAGE)}
  <main>
    <h1>Opentrons release assets</h1>
    <p>Live inventories of app and robot OS artifacts from S3/CloudFront.
    Each report shows the {limit} most recent versions per manifest.
    Updated {html.escape(generated_at)}.</p>
    <ul>
      <li class="section-title">Live asset inventories</li>{asset_items}
      <li class="section-title">Release guides</li>{guide_items}
    </ul>
  </main>
</body>
</html>
"""


async def generate_channel_asset_report(page: ChannelAssetPage, output: Path, limit: int) -> None:
    """Fetch one channel manifest set and write its HTML report."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        snapshot = await fetch_channel_snapshot(client, page.channel, page.config, limit)
    write_report(
        output,
        render_html([snapshot], page.config, limit, current_page=page.filename),
    )
    print(f"Wrote {output.resolve()}")


async def publish_pages(output_dir: Path, limit: int) -> None:
    """Generate index, per-channel asset inventories, and release guides under output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    await asyncio.gather(
        *[
            generate_channel_asset_report(
                page,
                output_dir / page.filename,
                limit,
            )
            for page in CHANNEL_ASSET_PAGES
        ]
    )
    publish_release_guides(output_dir)
    index_path = output_dir / INDEX_PAGE
    write_report(index_path, render_index(generated_at, limit))
    print(f"Wrote {index_path.resolve()}")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(description="Generate GitHub Pages asset inventory HTML.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Recent versions per manifest (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument("--serve", action="store_true", help="Serve pages/ on localhost after generating.")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port for --serve (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the site index in a browser when serving.",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""
    args = build_parser().parse_args()
    asyncio.run(publish_pages(args.output_dir, args.limit))
    if args.serve:
        serve_report(args.output_dir / INDEX_PAGE, args.port, args.open_browser)


if __name__ == "__main__":
    main()
