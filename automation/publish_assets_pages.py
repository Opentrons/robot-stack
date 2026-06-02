#!/usr/bin/env python3
"""Generate Flex and OT-2 asset inventory HTML for GitHub Pages."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
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
from automation.site_nav import FLEX_EXTERNAL_ASSETS_PAGE, INDEX_PAGE

DEFAULT_OUTPUT_DIR = Path("pages")
DEFAULT_LIMIT = 5
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ChannelAssetPage:
    """One per-channel asset inventory page."""

    filename: str
    config: ReleasePlatformConfig
    channel: AssetChannel


CHANNEL_ASSET_PAGES: tuple[ChannelAssetPage, ...] = (
    ChannelAssetPage(FLEX_EXTERNAL_ASSETS_PAGE, FLEX_CONFIG, FLEX_EXTERNAL),
    ChannelAssetPage("flex-internal-assets.html", FLEX_CONFIG, FLEX_INTERNAL),
    ChannelAssetPage("ot2-external-assets.html", OT2_CONFIG, OT2_EXTERNAL),
    ChannelAssetPage("ot2-internal-assets.html", OT2_CONFIG, OT2_INTERNAL),
)


async def generate_channel_asset_report(
    page: ChannelAssetPage,
    output: Path,
    limit: int,
    *,
    nav_page: str,
) -> None:
    """Fetch one channel manifest set and write its HTML report."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        snapshot = await fetch_channel_snapshot(client, page.channel, page.config, limit)
    write_report(
        output,
        render_html([snapshot], page.config, limit, current_page=nav_page),
    )
    print(f"Wrote {output.resolve()}")


async def publish_pages(output_dir: Path, limit: int) -> None:
    """Generate per-channel asset inventories, release guides, and index (Flex external)."""
    output_dir.mkdir(parents=True, exist_ok=True)

    async def write_page(page: ChannelAssetPage) -> None:
        await generate_channel_asset_report(
            page,
            output_dir / page.filename,
            limit,
            nav_page=page.filename,
        )

    await asyncio.gather(*[write_page(page) for page in CHANNEL_ASSET_PAGES])

    # Site root is Flex external assets; highlight "External assets" in the nav.
    await generate_channel_asset_report(
        CHANNEL_ASSET_PAGES[0],
        output_dir / INDEX_PAGE,
        limit,
        nav_page=INDEX_PAGE,
    )

    publish_release_guides(output_dir)


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
