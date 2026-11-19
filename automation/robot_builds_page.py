#!/usr/bin/env python3
"""Render the public Flex and OT-2 download page.

Spec: docs/robot-builds-page.md. The page links to the external release
manifests. It does not read electron-updater YAMLs and it does not include
internal hosts. Stable builds are on the main page. Alpha builds are
on a separate QA page that the main page does not link to. Beta builds are
not shown.

Usage:
    uv run ./automation/robot_builds_page.py
    uv run ./automation/robot_builds_page.py --serve
    uv run ./automation/robot_builds_page.py --previous-state /tmp/prev.json
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Literal

import httpx
import semver

from automation.asset_inventory import ot2_version_sort_key, sort_semver_versions_desc
from automation.asset_urls import app_manifest_url, robot_manifest_url
from automation.flex_urls import FLEX_EXTERNAL, FLEX_ROBOT_PREFIX
from automation.ot2_calendar_semver import decode_ot2_external_version
from automation.ot2_urls import OT2_EXTERNAL, OT2_ROBOT_PREFIX
from automation.release import robot_manifest_production_entries
from automation.site_nav import robot_display_font_css, robot_name_html

Channel = Literal["stable", "alpha"]

QA_ALPHA_HREF = "qa/alpha/"
DEFAULT_OUTPUT_DIR = Path(".build/robot-builds")
DEFAULT_PORT = 8767
STATE_FILENAME = "manifest-state.json"
SKIP_PUBLISH = "SKIP_PUBLISH"
DO_PUBLISH = "PUBLISH"

INSTALLER_SUFFIXES: tuple[tuple[str, str], ...] = (
    (".dmg", "macOS app"),
    (".exe", "Windows app"),
    (".appimage", "Linux app"),
)


@dataclass(frozen=True)
class ManifestSources:
    """The four external manifests this page is allowed to read."""

    flex_robot: str
    flex_app: str
    ot2_robot: str
    ot2_app: str

    @classmethod
    def external(cls) -> ManifestSources:
        """Live external hosts. Internal development hosts are not included."""
        return cls(
            flex_robot=robot_manifest_url(FLEX_EXTERNAL, FLEX_ROBOT_PREFIX),
            flex_app=app_manifest_url(FLEX_EXTERNAL),
            ot2_robot=robot_manifest_url(OT2_EXTERNAL, OT2_ROBOT_PREFIX),
            ot2_app=app_manifest_url(OT2_EXTERNAL),
        )

    def as_tuple(self) -> tuple[str, str, str, str]:
        return (self.flex_robot, self.flex_app, self.ot2_robot, self.ot2_app)


@dataclass(frozen=True)
class Installer:
    label: str
    url: str


@dataclass(frozen=True)
class BuildRow:
    version: str
    channel: Channel
    system_url: str
    full_image_url: str
    release_notes_url: str
    installers: tuple[Installer, ...]


@dataclass(frozen=True)
class ProductBuilds:
    name: str
    stable: BuildRow | None
    history: tuple[BuildRow, ...]
    alphas: tuple[BuildRow, ...]


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def _production_map(manifest: dict[str, Any]) -> dict[str, Any]:
    production = manifest.get("production", {})
    return production if isinstance(production, dict) else {}


def _installers(entry: dict[str, Any]) -> tuple[Installer, ...] | None:
    """Installer links for one app version. None means the version is revoked."""
    if bool(entry.get("revoked", False)):
        return None
    found: list[Installer] = []
    for key, value in entry.items():
        if not isinstance(value, str) or key.lower().endswith(".yml"):
            continue
        lowered = key.lower()
        for suffix, label in INSTALLER_SUFFIXES:
            if lowered.endswith(suffix):
                found.append(Installer(label, value))
                break
    order = {label: index for index, (_suffix, label) in enumerate(INSTALLER_SUFFIXES)}
    return tuple(sorted(found, key=lambda item: order[item.label]))


def _text_field(entry: dict[str, Any], key: str) -> str:
    value = entry.get(key, "")
    return value if isinstance(value, str) else ""


def _flex_channel(version: str) -> Channel | None:
    try:
        parsed = semver.VersionInfo.parse(version.lstrip("v"))
    except ValueError:
        return None
    if not parsed.prerelease:
        return "stable"
    tag = parsed.prerelease.split(".", 1)[0]
    if tag == "alpha":
        return "alpha"
    # Beta is intentionally omitted from the public page.
    return None


def _ot2_channel(version: str) -> Channel | None:
    """External calendar versions only. Drops .dev, legacy semver, and internal-style keys."""
    try:
        _year, _month, _release_num, prerelease, _prerelease_num = decode_ot2_external_version(version)
    except ValueError:
        return None
    if prerelease is None:
        return "stable"
    if prerelease == "alpha":
        return "alpha"
    # Beta is intentionally omitted from the public page.
    return None


def _rows_for_product(
    robot_manifest: dict[str, Any],
    app_manifest: dict[str, Any],
    channel_of: Callable[[str], Channel | None],
    sort_key: Callable[[str], Any],
) -> list[BuildRow]:
    robot = robot_manifest_production_entries(robot_manifest)
    app = _production_map(app_manifest)
    rows: list[BuildRow] = []
    for version in set(robot) | set(app):
        channel = channel_of(version)
        if channel is None:
            continue
        app_entry = app.get(version)
        installers: tuple[Installer, ...] = ()
        if isinstance(app_entry, dict):
            parsed = _installers(app_entry)
            if parsed is None:
                continue
            installers = parsed
        robot_entry = robot.get(version, {})
        if not isinstance(robot_entry, dict):
            robot_entry = {}
        row = BuildRow(
            version=version,
            channel=channel,
            system_url=_text_field(robot_entry, "system"),
            full_image_url=_text_field(robot_entry, "fullImage"),
            release_notes_url=_text_field(robot_entry, "releaseNotes"),
            installers=installers,
        )
        if row.system_url or row.full_image_url or row.release_notes_url or row.installers:
            rows.append(row)
    return sorted(rows, key=lambda row: sort_key(row.version), reverse=True)


def _flex_sort_key(version: str) -> semver.VersionInfo:
    return semver.VersionInfo.parse(version.lstrip("v"))


def assemble_products(
    flex_robot: dict[str, Any],
    flex_app: dict[str, Any],
    ot2_robot: dict[str, Any],
    ot2_app: dict[str, Any],
) -> tuple[ProductBuilds, ProductBuilds]:
    """Join each product's app and robot manifests and split out the banners."""
    flex_rows = _rows_for_product(flex_robot, flex_app, _flex_channel, _flex_sort_key)
    # sort_semver_versions_desc is the spec's Flex ordering. Re-apply it so a
    # future change to that helper changes this page too.
    flex_order = {version: index for index, version in enumerate(sort_semver_versions_desc([row.version for row in flex_rows]))}
    flex_rows = sorted(flex_rows, key=lambda row: flex_order[row.version])

    ot2_rows = _rows_for_product(ot2_robot, ot2_app, _ot2_channel, ot2_version_sort_key)
    return _split_product("Flex", flex_rows), _split_product("OT-2", ot2_rows)


def _split_product(name: str, rows: list[BuildRow]) -> ProductBuilds:
    stable = next((row for row in rows if row.channel == "stable"), None)
    banner_versions = {stable.version} if stable is not None else set()
    history = tuple(
        row for row in rows if row.channel == "stable" and row.version not in banner_versions
    )
    alphas = tuple(row for row in rows if row.channel == "alpha")
    return ProductBuilds(name=name, stable=stable, history=history, alphas=alphas)


def _action(url: str, label: str) -> str:
    if not url:
        return ""
    return f'<li><a href="{_esc(url)}">{_esc(label)}</a></li>'


def _render_row(row: BuildRow, *, banner: str | None, include_full_image: bool = False) -> str:
    badge = ""
    if row.channel == "stable" and banner:
        badge = '<span class="badge stable">Stable</span>'
    actions = [
        _action(row.system_url, "Robot system update"),
        *[_action(item.url, item.label) for item in row.installers],
        _action(row.release_notes_url, "Release notes"),
    ]
    reflash = ""
    if include_full_image and row.full_image_url:
        reflash = (
            '<details class="reflash"><summary>Full reflash image</summary>'
            "<p>This replaces the robot's whole software image. Use it to reflash a robot, not for a normal update.</p>"
            f'<p><a href="{_esc(row.full_image_url)}">Download full image</a></p></details>'
        )
    banner_attr = f' data-banner="{banner}"' if banner else ""
    return (
        f'<article class="release"{banner_attr} data-version="{_esc(row.version)}">'
        f"<h3>{_esc(row.version)} {badge}</h3>"
        f'<ul class="actions">{"".join(actions)}</ul>{reflash}</article>'
    )


def _render_banner(row: BuildRow | None, kind: str, blurb: str) -> str:
    if row is None:
        return ""
    return (
        f'<div class="banner {kind}"><p class="blurb">{blurb}</p>'
        f"{_render_row(row, banner=kind, include_full_image=True)}</div>"
    )


def _render_product_main(product: ProductBuilds) -> str:
    history = "".join(_render_row(row, banner=None) for row in product.history)
    if not history:
        history = '<p class="empty">No older stable builds.</p>'
    return (
        f'<section data-product="{_esc(product.name.lower())}">'
        f"<h2>{robot_name_html(product.name)}</h2>"
        f"{_render_banner(product.stable, 'stable', 'Stable. This is the customer default.')}"
        f'<div data-history=""><h3>Older builds</h3>{history}</div></section>'
    )


def _render_product_alpha(product: ProductBuilds) -> str:
    rows = "".join(_render_row(row, banner=None, include_full_image=True) for row in product.alphas)
    if not rows:
        rows = '<p class="empty">No alpha builds.</p>'
    return (
        f'<section data-product="{_esc(product.name.lower())}">'
        f"<h2>{robot_name_html(product.name)}</h2>"
        f'<div data-history="">{rows}</div></section>'
    )


def _footer(generated_at: datetime, sources: ManifestSources) -> str:
    stamp = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    labels = (
        ("Flex robot", sources.flex_robot),
        ("Flex app", sources.flex_app),
        ("OT-2 robot", sources.ot2_robot),
        ("OT-2 app", sources.ot2_app),
    )
    links = " · ".join(f'<a href="{_esc(url)}">{_esc(label)}</a>' for label, url in labels)
    return (
        f'<footer class="meta">'
        f"<div>Generated {stamp}.</div>"
        f"<div>Manifests: {links}</div>"
        f"</footer>"
    )


_PAGE_CSS = """
:root {
  color-scheme: light dark;
  --bg: #0f1419;
  --panel: #1a222d;
  --text: #e7ecf3;
  --muted: #9aa7b8;
  --accent: #60a5fa;
  --warn: #fbbf24;
  --border: #2b3645;
  --ok: #34d399;
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #f6f8fb;
    --panel: #ffffff;
    --text: #1f2937;
    --muted: #6b7280;
    --accent: #2563eb;
    --warn: #b45309;
    --border: #d1d5db;
    --ok: #047857;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
main {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem 1.25rem 4rem;
}
h1, h2, h3 { line-height: 1.2; }
h1 { margin: 0 0 0.4rem; font-size: 1.75rem; }
h2 { margin: 0 0 0.85rem; font-size: 1.35rem; }
h3 { margin: 0; font-size: 1.05rem; }
p { margin: 0; }
a { color: var(--accent); }
.lede, .blurb, .empty, .note, footer.meta { color: var(--muted); }
.lede { max-width: 80ch; margin-bottom: 0.75rem; }
.note { margin: 0.6rem 0 1rem; }
input[type="search"] {
  width: 100%;
  font: inherit;
  color: var(--text);
  background: var(--panel);
  margin: 0.75rem 0 0.25rem;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
}
input[type="search"]::placeholder { color: var(--muted); }
section {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin: 1.25rem 0;
}
.banner {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.85rem 1rem 0.35rem;
  margin: 0 0 0.9rem;
  background: color-mix(in srgb, var(--ok) 10%, transparent);
  border-color: color-mix(in srgb, var(--ok) 45%, var(--border));
}
.blurb { font-size: 0.92rem; margin-bottom: 0.45rem; }
.release { padding: 0.75rem 0 0.15rem; }
.banner .release { padding-top: 0.15rem; }
[data-history] .release {
  border-top: 1px solid var(--border);
  padding: 0.85rem 0 0.2rem;
}
[data-history] h3 {
  color: var(--muted);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin: 0.35rem 0 0.15rem;
}
.actions {
  list-style: none;
  margin: 0.4rem 0 0.55rem;
  padding: 0;
}
.actions li { padding: 0.12rem 0; }
.badge {
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  border-radius: 999px;
  padding: 0.08rem 0.5rem;
  border: 1px solid color-mix(in srgb, var(--ok) 45%, var(--border));
  color: var(--ok);
  background: color-mix(in srgb, var(--ok) 12%, transparent);
  vertical-align: middle;
}
.reflash {
  margin: 0 0 0.55rem;
  font-size: 0.92rem;
  color: var(--muted);
}
.reflash summary {
  cursor: pointer;
  color: var(--text);
}
.reflash p { margin: 0.4rem 0; }
footer.meta {
  display: grid;
  gap: 0.35rem;
  margin-top: 1.5rem;
  font-size: 0.92rem;
}
"""

def _page_css() -> str:
    """Match the engineering asset inventory look (tokens + Orbitron names)."""
    return robot_display_font_css() + _PAGE_CSS

_SEARCH_SCRIPT = """
const input = document.getElementById("search");
input.addEventListener("input", () => {
  const query = input.value.trim().toLowerCase();
  document.querySelectorAll("[data-history] [data-version]").forEach((row) => {
    const version = (row.getAttribute("data-version") || "").toLowerCase();
    row.hidden = query.length > 0 && !version.includes(query);
  });
});
"""


def _document(title: str, body: str, *, noindex: bool) -> str:
    robots = '\n  <meta name="robots" content="noindex">' if noindex else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">{robots}
  <title>{_esc(title)}</title>
  <style>{_page_css()}</style>
</head>
<body>
  <main>
    {body}
  </main>
  <script>{_SEARCH_SCRIPT}</script>
</body>
</html>
"""


def render_pages(
    flex_robot: dict[str, Any],
    flex_app: dict[str, Any],
    ot2_robot: dict[str, Any],
    ot2_app: dict[str, Any],
    sources: ManifestSources,
    generated_at: datetime,
) -> tuple[str, str]:
    """Return (main page HTML, QA alpha page HTML)."""
    flex, ot2 = assemble_products(flex_robot, flex_app, ot2_robot, ot2_app)
    footer = _footer(generated_at, sources)
    main_body = (
        "<h1>Opentrons robot builds</h1>"
        '<p class="lede">Stable downloads for Flex and OT-2. Stable is the file to send a customer.</p>'
        '<input id="search" type="search" placeholder="Filter older builds by version" '
        'aria-label="Filter older builds by version">'
        f"{_render_product_main(flex)}{_render_product_main(ot2)}{footer}"
    )
    alpha_body = (
        "<h1>Opentrons robot builds — QA alphas</h1>"
        '<p class="lede">QA only. These are not the files to send a customer.</p>'
        '<p class="note"><a href="/">Robot builds</a></p>'
        '<input id="search" type="search" placeholder="Filter by version" aria-label="Filter by version">'
        f"{_render_product_alpha(flex)}{_render_product_alpha(ot2)}{footer}"
    )
    main = _document("Opentrons robot builds", main_body, noindex=False)
    alpha = _document("Opentrons robot builds — QA alphas", alpha_body, noindex=True)
    return main, alpha


def write_pages(output_dir: Path, main_html: str, alpha_html: str) -> tuple[Path, Path]:
    """Write index.html and the unlinked QA alpha page."""
    main_path = output_dir / "index.html"
    alpha_path = output_dir / QA_ALPHA_HREF / "index.html"
    main_path.parent.mkdir(parents=True, exist_ok=True)
    alpha_path.parent.mkdir(parents=True, exist_ok=True)
    main_path.write_text(main_html, encoding="utf-8")
    alpha_path.write_text(alpha_html, encoding="utf-8")
    return main_path, alpha_path


def build_manifest_state(
    sources: ManifestSources,
    body_by_url: dict[str, bytes],
    *,
    source_sha: str = "",
) -> dict[str, Any]:
    """Hashes for the four manifests, plus the publishing commit when known."""
    manifests = {
        url: hashlib.sha256(body_by_url[url]).hexdigest() for url in sources.as_tuple()
    }
    return {
        "version": 1,
        "source_sha": source_sha,
        "manifests": manifests,
    }


def load_manifest_state(path: Path) -> dict[str, Any]:
    """Load a previously published state file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def publish_is_unchanged(previous: dict[str, Any] | None, current: dict[str, Any]) -> bool:
    """True when manifests and source commit both match the last publish."""
    if previous is None:
        return False
    return (
        previous.get("manifests") == current.get("manifests")
        and previous.get("source_sha") == current.get("source_sha")
        and bool(previous.get("manifests"))
    )


def fetch_manifests(
    sources: ManifestSources,
) -> tuple[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, bytes]]:
    """Fetch the four manifests. Raise if any request fails, so a bad run writes nothing."""
    loaded: list[dict[str, Any]] = []
    bodies: dict[str, bytes] = {}
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        for url in sources.as_tuple():
            response = client.get(url)
            response.raise_for_status()
            bodies[url] = response.content
            data = response.json()
            if not isinstance(data, dict):
                raise RuntimeError(f"{url} did not return a JSON object")
            loaded.append(data)
    flex_robot, flex_app, ot2_robot, ot2_app = loaded
    return (flex_robot, flex_app, ot2_robot, ot2_app), bodies


def _serve(directory: Path, port: int) -> None:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving {directory.resolve()} at http://127.0.0.1:{port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--serve", action="store_true", help="Serve the generated pages on 127.0.0.1.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--previous-state",
        type=Path,
        default=None,
        help="Published manifest-state.json from the site bucket. Skip writing when unchanged.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Publish even when manifests and source commit match the previous state.",
    )
    args = parser.parse_args()

    sources = ManifestSources.external()
    source_sha = os.environ.get("GITHUB_SHA", "").strip()
    try:
        manifests, bodies = fetch_manifests(sources)
    except Exception as error:  # noqa: BLE001 - one message, and do not write a partial page
        raise SystemExit(f"Not writing the page; a manifest fetch failed: {error}") from error

    state = build_manifest_state(sources, bodies, source_sha=source_sha)
    previous: dict[str, Any] | None = None
    if args.previous_state is not None and args.previous_state.is_file():
        previous = load_manifest_state(args.previous_state)

    if not args.force and publish_is_unchanged(previous, state):
        print(SKIP_PUBLISH)
        return

    main_html, alpha_html = render_pages(*manifests, sources, datetime.now(timezone.utc))
    main_path, alpha_path = write_pages(args.output_dir, main_html, alpha_html)
    state_path = args.output_dir / STATE_FILENAME
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {main_path.resolve()}")
    print(f"Wrote {alpha_path.resolve()}")
    print(f"Wrote {state_path.resolve()}")
    print(DO_PUBLISH)
    if args.serve:
        _serve(args.output_dir, args.port)


if __name__ == "__main__":
    main()
