"""Generate HTML release asset inventories for robot platforms."""

from __future__ import annotations

import argparse
import asyncio
import html
import re
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

import httpx
import semver
import yaml

from automation.asset_urls import APP_CHANNEL_YAMLS, AssetChannel, app_manifest_url, app_yaml_url, robot_manifest_url
from automation.go import decode_ot2_external_version, decode_ot2_internal_version
from automation.release import robot_manifest_production_entries, robot_manifest_release_keys
from automation.site_nav import render_site_header, robot_name_html, site_nav_css

DEFAULT_LIMIT = 10

APP_BUILD_RE = re.compile(r"-b(\d+)\.")
ASSET_URL_HOST_RE = re.compile(r"^https?://([^/]+)")

OT2_DEV_VERSION_RE = re.compile(r"^(\d{2})\.(\d{1,2})\.(\d+)(?:\.dev(\d+)|-(\d+))?$")
OT2_DASH_BUILD_RE = re.compile(r"^(\d{2})\.(\d{1,2})\.(\d+)-(\d+)$")
OT2_DOT_BUILD_RE = re.compile(r"^(\d{2})\.(\d{1,2})\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class PipelineRow:
    """One row in the build-job-to-URL documentation table."""

    component: str
    workflow: str
    s3_prefix: str
    manifest: str
    per_build_layout: str


@dataclass(frozen=True)
class ReleasePlatformConfig:
    """Platform-specific settings for a release asset inventory report."""

    display_name: str
    html_title: str
    default_output: Path
    default_port: int
    app_repo: str
    robot_repo: str
    robot_prefix: str
    robot_run_pattern: re.Pattern[str]
    channels: Tuple[AssetChannel, ...]
    version_scheme: Literal["semver", "ot2"]
    pipeline_intro: str
    pipeline_rows: Tuple[PipelineRow, ...]
    pipeline_footnote: str
    legacy_app_host: Optional[str] = None
    legacy_app_host_note: Optional[str] = None
    show_robot_manifest_key: bool = False


@dataclass(frozen=True)
class FetchError:
    """A failed HTTP fetch with context."""

    label: str
    url: str
    message: str


@dataclass
class AppYamlChannel:
    """Current electron-updater channel pointer."""

    name: str
    url: str
    version: Optional[str] = None
    release_date: Optional[str] = None
    artifact: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AppReleaseRow:
    """One app version from releases.json."""

    version: str
    assets: Dict[str, str]
    revoked: bool = False
    build_ids: List[str] = field(default_factory=list)


@dataclass
class RobotReleaseRow:
    """One robot OS version from releases.json."""

    version: str
    full_image: str
    system: str
    version_url: str
    release_notes: str
    workflow_run_id: Optional[str] = None
    manifest_key: Optional[str] = None


@dataclass
class ChannelSnapshot:
    """Fetched app + robot data for one release channel."""

    channel: AssetChannel
    robot_prefix: str
    app_manifest_url: str
    robot_manifest_url: str
    app_releases: List[AppReleaseRow] = field(default_factory=list)
    robot_releases: List[RobotReleaseRow] = field(default_factory=list)
    yaml_channels: List[AppYamlChannel] = field(default_factory=list)
    errors: List[FetchError] = field(default_factory=list)


def ot2_version_sort_key(version: str) -> Tuple[Any, ...]:
    """Sort OT-2 versions newest-first, covering calendar, legacy, and dev builds."""
    clean = version.lstrip("v")
    try:
        year, month, day, build_num, prerelease = decode_ot2_internal_version(clean)
        pre_rank = {"alpha": 1, "beta": 2}.get(prerelease or "", 0)
        return (1, year, month, day, build_num, pre_rank, 0, "")
    except ValueError:
        pass
    try:
        year, month, release_num, prerelease, pre_num = decode_ot2_external_version(clean)
        pre_rank = {"alpha": 1, "beta": 2}.get(prerelease or "", 0)
        return (2, year, month, release_num, pre_rank, pre_num or 0, 0, "")
    except ValueError:
        pass
    dev_match = OT2_DEV_VERSION_RE.match(clean)
    if dev_match:
        yy, month, patch, dev_num, dash_num = dev_match.groups()
        return (3, int(yy), int(month), int(patch), int(dev_num or 0), int(dash_num or 0), 0, "")
    dash_match = OT2_DASH_BUILD_RE.match(clean)
    if dash_match:
        yy, month, patch, sub_build = dash_match.groups()
        return (3, int(yy), int(month), int(patch), 0, int(sub_build), 0, "")
    dot_match = OT2_DOT_BUILD_RE.match(clean)
    if dot_match:
        yy, month, patch, sub_build = dot_match.groups()
        return (3, int(yy), int(month), int(patch), 0, int(sub_build), 0, "")
    try:
        parsed = semver.VersionInfo.parse(clean)
        return (4, parsed)
    except ValueError:
        return (9, clean)


def sort_semver_versions_desc(versions: Sequence[str]) -> List[str]:
    """Return semver versions sorted newest first using semver precedence rules."""
    parsed: List[Tuple[bool, semver.VersionInfo | str, str]] = []
    for version in versions:
        clean = version.lstrip("v")
        try:
            parsed.append((True, semver.VersionInfo.parse(clean), version))
        except ValueError:
            parsed.append((False, clean, version))

    def sort_key(item: Tuple[bool, semver.VersionInfo | str, str]) -> Tuple[bool, Any]:
        is_semver, value, _raw = item
        return (is_semver, value)

    return [raw for _is_semver, _value, raw in sorted(parsed, key=sort_key, reverse=True)]


def sort_versions_desc(versions: Sequence[str], config: ReleasePlatformConfig) -> List[str]:
    """Return versions sorted newest first for the given platform."""
    if config.version_scheme == "semver":
        return sort_semver_versions_desc(versions)
    return sorted(versions, key=ot2_version_sort_key, reverse=True)


def extract_app_build_ids(assets: Dict[str, str]) -> List[str]:
    """Pull CI build numbers from app installer filenames."""
    build_ids: List[str] = []
    for url in assets.values():
        match = APP_BUILD_RE.search(url)
        if match:
            build_ids.append(match.group(1))
    return sorted(set(build_ids))


def asset_url_host(url: str) -> str:
    """Return the hostname from an asset URL."""
    match = ASSET_URL_HOST_RE.match(url)
    return match.group(1) if match else ""


def extract_robot_run_id(url: str, run_pattern: re.Pattern[str]) -> Optional[str]:
    """Pull the GitHub Actions run id from a robot artifact URL."""
    match = run_pattern.search(url)
    return match.group(1) if match else None


def github_workflow_url(run_id: str, repo: str) -> str:
    """Link to the workflow run that uploaded artifacts."""
    return f"https://github.com/Opentrons/{repo}/actions/runs/{run_id}"


async def fetch_json(
    client: httpx.AsyncClient,
    label: str,
    url: str,
) -> Tuple[Optional[Any], Optional[FetchError]]:
    """GET JSON from url, returning parsed data or a FetchError."""
    try:
        response = await client.get(url, timeout=20.0)
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:  # noqa: BLE001 - surface all fetch failures in the report
        return None, FetchError(label=label, url=url, message=str(exc))


async def fetch_yaml_channel(
    client: httpx.AsyncClient,
    channel: AssetChannel,
    filename: str,
) -> AppYamlChannel:
    """Fetch one electron-updater channel YAML if it exists."""
    url = app_yaml_url(channel, filename)
    try:
        response = await client.get(url, timeout=20.0)
        if response.status_code == 404:
            return AppYamlChannel(name=filename, url=url, error="not published")
        response.raise_for_status()
        data = yaml.safe_load(response.text) or {}
        return AppYamlChannel(
            name=filename,
            url=url,
            version=str(data.get("version", "")) or None,
            release_date=data.get("releaseDate"),
            artifact=str(data.get("path", "")) or None,
        )
    except Exception as exc:  # noqa: BLE001
        return AppYamlChannel(name=filename, url=url, error=str(exc))


def parse_app_releases(
    production: Dict[str, Dict[str, Any]],
    limit: int,
    config: ReleasePlatformConfig,
) -> List[AppReleaseRow]:
    """Parse app releases.json production entries."""
    rows: List[AppReleaseRow] = []
    for version in sort_versions_desc(list(production.keys()), config)[:limit]:
        entry = production[version]
        assets = {key: value for key, value in entry.items() if isinstance(value, str) and key != "revoked"}
        rows.append(
            AppReleaseRow(
                version=version,
                assets=assets,
                revoked=bool(entry.get("revoked", False)),
                build_ids=extract_app_build_ids(assets),
            )
        )
    return rows


def parse_robot_releases(
    production: Dict[str, Dict[str, str]],
    limit: int,
    config: ReleasePlatformConfig,
    run_pattern: re.Pattern[str],
    release_keys: Optional[Dict[str, str]] = None,
) -> List[RobotReleaseRow]:
    """Parse robot releases.json production entries."""
    rows: List[RobotReleaseRow] = []
    for version in sort_versions_desc(list(production.keys()), config)[:limit]:
        entry = production[version]
        full_image = entry.get("fullImage", "")
        rows.append(
            RobotReleaseRow(
                version=version,
                full_image=full_image,
                system=entry.get("system", ""),
                version_url=entry.get("version", ""),
                release_notes=entry.get("releaseNotes", ""),
                workflow_run_id=extract_robot_run_id(full_image, run_pattern),
                manifest_key=release_keys.get(version) if release_keys else None,
            )
        )
    return rows


async def fetch_channel_snapshot(
    client: httpx.AsyncClient,
    channel: AssetChannel,
    config: ReleasePlatformConfig,
    limit: int,
) -> ChannelSnapshot:
    """Fetch app manifest, robot manifest, and channel YAMLs for one channel."""
    snapshot = ChannelSnapshot(
        channel=channel,
        robot_prefix=config.robot_prefix,
        app_manifest_url=app_manifest_url(channel),
        robot_manifest_url=robot_manifest_url(channel, config.robot_prefix),
    )

    app_data, app_err = await fetch_json(client, f"{channel.label} app releases.json", snapshot.app_manifest_url)
    if app_err:
        snapshot.errors.append(app_err)
    elif isinstance(app_data, dict):
        production = app_data.get("production", {})
        if isinstance(production, dict):
            snapshot.app_releases = parse_app_releases(production, limit, config)

    robot_data, robot_err = await fetch_json(client, f"{channel.label} robot releases.json", snapshot.robot_manifest_url)
    if robot_err:
        snapshot.errors.append(robot_err)
    elif isinstance(robot_data, dict):
        production = robot_manifest_production_entries(robot_data)
        if production:
            release_keys = robot_manifest_release_keys(robot_data) if config.show_robot_manifest_key else None
            snapshot.robot_releases = parse_robot_releases(
                production,
                limit,
                config,
                config.robot_run_pattern,
                release_keys=release_keys,
            )

    yaml_results = await asyncio.gather(*[fetch_yaml_channel(client, channel, filename) for filename in APP_CHANNEL_YAMLS])
    snapshot.yaml_channels = [item for item in yaml_results if item.error != "not published"]
    return snapshot


def esc(value: Optional[str]) -> str:
    """HTML-escape a string."""
    return html.escape(value or "")


def link(url: str, label: Optional[str] = None) -> str:
    """Render an external link."""
    text = esc(label or url)
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{text}</a>'


def render_asset_list(assets: Dict[str, str]) -> str:
    """Render key/value asset links."""
    if not assets:
        return "<em>no assets</em>"
    items = "".join(f"<li><code>{esc(key)}</code> {link(url)}</li>" for key, url in sorted(assets.items()))
    return f"<ul class='compact'>{items}</ul>"


def legacy_app_host_warning(snapshot: ChannelSnapshot, config: ReleasePlatformConfig) -> str:
    """Warn when releases.json still points at a legacy external app host."""
    if config.legacy_app_host is None or snapshot.channel.channel != "external":
        return ""
    legacy_hosts = {
        asset_url_host(url)
        for release in snapshot.app_releases
        for url in release.assets.values()
        if asset_url_host(url) == config.legacy_app_host
    }
    if not legacy_hosts:
        return ""
    note = config.legacy_app_host_note or ""
    return (
        f"<p class='note warn'>Legacy app asset host in releases.json: "
        f"<code>{esc(config.legacy_app_host)}</code>. {esc(note)}</p>"
    )


def render_errors(errors: Sequence[FetchError]) -> str:
    """Render fetch errors."""
    if not errors:
        return ""
    rows = "".join(f"<tr><td>{esc(err.label)}</td><td>{link(err.url)}</td><td>{esc(err.message)}</td></tr>" for err in errors)
    return f"""
    <section class="errors">
      <h2>Fetch errors</h2>
      <table>
        <thead><tr><th>Source</th><th>URL</th><th>Error</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>
    """


def filter_pipeline_rows(config: ReleasePlatformConfig, channel: AssetChannel) -> Tuple[PipelineRow, ...]:
    """Return pipeline rows relevant to one release channel."""
    needle = channel.channel
    return tuple(row for row in config.pipeline_rows if needle in row.component.lower())


def render_pipeline_map(config: ReleasePlatformConfig, channel: Optional[AssetChannel] = None) -> str:
    """Document how CI maps build jobs to published URLs."""
    rows_source = filter_pipeline_rows(config, channel) if channel is not None else config.pipeline_rows
    rows = "".join(
        f"<tr><td>{esc(row.component)}</td><td><code>{esc(row.workflow)}</code></td>"
        f"<td><code>{esc(row.s3_prefix)}</code></td><td><code>{esc(row.manifest)}</code></td>"
        f"<td><code>{esc(row.per_build_layout)}</code></td></tr>"
        for row in rows_source
    )
    return f"""
    <section>
      <h2>Build job to URL map</h2>
      <p>{config.pipeline_intro}</p>
      <table>
        <thead>
          <tr>
            <th>Component</th>
            <th>Workflow</th>
            <th>S3 prefix</th>
            <th>Manifest</th>
            <th>Per-build layout</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p class="note">{config.pipeline_footnote}</p>
    </section>
    """


def render_yaml_channels(yaml_channels: Sequence[AppYamlChannel]) -> str:
    """Render electron-updater channel YAML pointers."""
    if not yaml_channels:
        return "<p><em>No channel YAML files found.</em></p>"
    rows = []
    for item in yaml_channels:
        if item.error:
            rows.append(
                f"<tr><td>{esc(item.name)}</td><td>{link(item.url)}</td><td colspan='3' class='warn'>{esc(item.error)}</td></tr>"
            )
            continue
        rows.append(
            f"<tr><td>{esc(item.name)}</td><td>{link(item.url)}</td>"
            f"<td><code>{esc(item.version)}</code></td>"
            f"<td>{esc(item.release_date or 'n/a')}</td>"
            f"<td><code>{esc(item.artifact)}</code></td></tr>"
        )
    body = "".join(rows)
    return f"""
    <table>
      <thead>
        <tr><th>Channel YAML</th><th>URL</th><th>Version</th><th>Release date</th><th>Artifact</th></tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
    """


def render_app_releases(releases: Sequence[AppReleaseRow]) -> str:
    """Render recent app releases."""
    if not releases:
        return "<p><em>No app releases found.</em></p>"
    rows = []
    for item in releases:
        builds = ", ".join(f"b{bid}" for bid in item.build_ids) or "n/a"
        revoked = "yes" if item.revoked else "no"
        rows.append(
            f"<tr><td><code>{esc(item.version)}</code></td>"
            f"<td>{builds}</td><td>{revoked}</td>"
            f"<td>{render_asset_list(item.assets)}</td></tr>"
        )
    body = "".join(rows)
    return f"""
    <table>
      <thead><tr><th>Version</th><th>Build id(s)</th><th>Revoked</th><th>Assets</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
    """


def render_robot_manifest_key_badge(manifest_key: Optional[str]) -> str:
    """Render a manifest key indicator for one robot release row."""
    if manifest_key == "productionV2":
        return (
            '<span class="manifest-key manifest-key-v2" '
            'title="Robots on 9.1.1+ download updates from productionV2">'
            "<code>productionV2</code></span>"
        )
    if manifest_key == "production":
        return (
            '<span class="manifest-key manifest-key-legacy" '
            'title="Legacy key; robots on 9.0.0 and earlier read production">'
            "<code>production</code></span>"
        )
    return "n/a"


def render_robot_releases(
    releases: Sequence[RobotReleaseRow],
    robot_repo: str,
    *,
    show_manifest_key: bool = False,
) -> str:
    """Render recent robot OS releases."""
    if not releases:
        return "<p><em>No robot releases found.</em></p>"
    rows = []
    for item in releases:
        run_link = (
            link(github_workflow_url(item.workflow_run_id, robot_repo), f"run {item.workflow_run_id}")
            if item.workflow_run_id
            else "n/a"
        )
        key_cell = f"<td>{render_robot_manifest_key_badge(item.manifest_key)}</td>" if show_manifest_key else ""
        rows.append(
            f"<tr><td><code>{esc(item.version)}</code></td>"
            f"{key_cell}"
            f"<td>{run_link}</td>"
            f"<td>{link(item.full_image, 'full image')}</td>"
            f"<td>{link(item.system, 'system')}</td>"
            f"<td>{link(item.version_url, 'VERSION.json')}</td>"
            f"<td>{link(item.release_notes, 'notes')}</td></tr>"
        )
    body = "".join(rows)
    key_header = "<th>Manifest key</th>" if show_manifest_key else ""
    return f"""
    <table>
      <thead>
        <tr>
          <th>Version</th>{key_header}<th>Build job</th><th>Full image</th><th>System</th><th>Version file</th><th>Notes</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
    """


def render_manifest_authority_note() -> str:
    """Explain authoritative manifests vs electron-updater YAML and edge routing."""
    return """
      <p class="note manifest-note">
        <strong>Robot OS:</strong> <code>releases.json</code> is the source of truth for on-robot updates.
        Flex robots on 9.1.1+ read the <code>productionV2</code> key; older entries remain under
        <code>production</code>.
        <strong>Desktop app:</strong> channel YAML files (<code>latest.yml</code>, <code>latest-mac.yml</code>,
        <code>latest-linux.yml</code>, and prerelease YAMLs) are authoritative; electron-updater reads those
        directly. App <code>releases.json</code> is not the app updater source of truth: a CloudFront edge
        function parses the latest stable semver from production and routes <code>latest*</code> requests to
        matching stable build artifacts. The tables below are still useful for humans and release validation.
      </p>
    """


def render_channel_section(snapshot: ChannelSnapshot, config: ReleasePlatformConfig) -> str:
    """Render one internal/external channel block."""
    return f"""
    <section class="channel">
      <h2>{esc(snapshot.channel.label)} channel</h2>
      <div class="meta">
        <div><strong>App host:</strong> <code>{esc(snapshot.channel.app_host)}</code></div>
        <div><strong>App manifest:</strong> {link(snapshot.app_manifest_url)}</div>
        <div><strong>Robot manifest:</strong> {link(snapshot.robot_manifest_url)}</div>
      </div>
      {legacy_app_host_warning(snapshot, config)}
      {render_manifest_authority_note()}

      <h3>Electron-updater channel YAMLs</h3>
      {render_yaml_channels(snapshot.yaml_channels)}

      <h3>Recent app releases (releases.json)</h3>
      {render_app_releases(snapshot.app_releases)}

      <h3>Recent robot OS releases (releases.json)</h3>
      {render_robot_releases(snapshot.robot_releases, config.robot_repo, show_manifest_key=config.show_robot_manifest_key)}
    </section>
    """


def report_page_title(config: ReleasePlatformConfig, snapshots: Sequence[ChannelSnapshot]) -> str:
    """Build the HTML document title for one or all channels."""
    if len(snapshots) == 1:
        return f"{config.display_name} {snapshots[0].channel.label} release assets"
    return config.html_title


def render_page_h1(config: ReleasePlatformConfig, snapshots: Sequence[ChannelSnapshot]) -> str:
    """Build the main page heading with robot name in display font."""
    if len(snapshots) == 1:
        snap = snapshots[0]
        suffix = f"{snap.channel.label} release assets"
        return f"<h1>{robot_name_html(config.display_name)} {esc(suffix)}</h1>"
    return f"<h1>{esc(config.html_title)}</h1>"


def render_html(
    snapshots: Sequence[ChannelSnapshot],
    config: ReleasePlatformConfig,
    limit: int,
    *,
    current_page: str = "",
) -> str:
    """Render the full HTML report."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    all_errors = [err for snap in snapshots for err in snap.errors]
    single_channel = snapshots[0].channel if len(snapshots) == 1 else None
    page_title = report_page_title(config, snapshots)
    page_h1 = render_page_h1(config, snapshots)
    channel_html = "".join(render_channel_section(snap, config) for snap in snapshots)
    header = render_site_header(current_page) if current_page else ""
    nav_css = site_nav_css() if current_page else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(page_title)}</title>
  <style>
    {nav_css}
    :root {{
      color-scheme: light dark;
      --bg: #0f1419;
      --panel: #1a222d;
      --text: #e7ecf3;
      --muted: #9aa7b8;
      --accent: #60a5fa;
      --warn: #fbbf24;
      --border: #2b3645;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --bg: #f6f8fb;
        --panel: #ffffff;
        --text: #1f2937;
        --muted: #6b7280;
        --accent: #2563eb;
        --warn: #b45309;
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
      max-width: 1200px;
      margin: 0 auto;
      padding: 2rem 1.25rem 4rem;
    }}
    h1, h2, h3 {{ line-height: 1.2; }}
    h1 {{ margin-top: 0; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      margin: 1.25rem 0;
    }}
    .lede {{ color: var(--muted); max-width: 80ch; }}
    .meta {{
      display: grid;
      gap: 0.35rem;
      margin-bottom: 1rem;
      font-size: 0.95rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.92rem;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 0.55rem 0.65rem;
      vertical-align: top;
      text-align: left;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    a {{ color: var(--accent); }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.88em;
    }}
    ul.compact {{
      margin: 0;
      padding-left: 1.1rem;
    }}
    .note, .warn {{ color: var(--muted); }}
    .manifest-key {{
      display: inline-block;
      padding: 0.1rem 0.45rem;
      border-radius: 999px;
      font-size: 0.82rem;
      border: 1px solid var(--border);
      white-space: nowrap;
    }}
    .manifest-key code {{
      background: transparent;
      padding: 0;
    }}
    .manifest-key-v2 {{
      color: var(--accent);
      border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
      background: color-mix(in srgb, var(--accent) 12%, transparent);
    }}
    .manifest-key-legacy {{
      color: var(--muted);
      background: color-mix(in srgb, var(--muted) 10%, transparent);
    }}
    .errors td:last-child {{ color: var(--warn); }}
  </style>
</head>
<body>
  {header}
  <main>
    {page_h1}
    <p class="lede">Live inventory of {esc(config.display_name)} app and robot OS artifacts published to S3/CloudFront.
    Showing the {limit} most recent versions per manifest. Generated {esc(generated_at)}.</p>
    {render_pipeline_map(config, single_channel)}
    {channel_html}
    {render_errors(all_errors)}
  </main>
</body>
</html>
"""


async def collect_snapshots(config: ReleasePlatformConfig, limit: int) -> List[ChannelSnapshot]:
    """Fetch all channel snapshots concurrently."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        return list(
            await asyncio.gather(*[fetch_channel_snapshot(client, channel, config, limit) for channel in config.channels])
        )


def write_report(output: Path, html_text: str) -> None:
    """Write HTML report to disk."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_text, encoding="utf-8")


def serve_report(output: Path, port: int, open_browser: bool) -> None:
    """Serve the report directory over HTTP until interrupted."""
    directory = output.parent.resolve()
    url = f"http://127.0.0.1:{port}/{output.name}"

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


async def generate_report(config: ReleasePlatformConfig, args: argparse.Namespace) -> None:
    """Generate (and optionally serve) a release assets report."""
    snapshots = await collect_snapshots(config, args.limit)
    html_text = render_html(snapshots, config, args.limit)
    write_report(args.output, html_text)
    print(f"Wrote {args.output.resolve()}")
    if args.serve:
        serve_report(args.output, args.port, args.open_browser)


def build_parser(config: ReleasePlatformConfig) -> argparse.ArgumentParser:
    """Build CLI argument parser for a platform report."""
    parser = argparse.ArgumentParser(description=f"Generate a {config.display_name} release assets HTML report.")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Number of recent versions to include per manifest (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=config.default_output,
        help=f"Output HTML path (default: {config.default_output})",
    )
    parser.add_argument("--serve", action="store_true", help="Serve the report on localhost after generating.")
    parser.add_argument(
        "--port",
        type=int,
        default=config.default_port,
        help=f"Port for --serve (default: {config.default_port})",
    )
    parser.add_argument("--open-browser", action="store_true", help="Open the report in a browser when serving.")
    return parser


def run_cli(config: ReleasePlatformConfig) -> None:
    """Parse args and run the report generator."""
    parser = build_parser(config)
    args = parser.parse_args()
    asyncio.run(generate_report(config, args))
