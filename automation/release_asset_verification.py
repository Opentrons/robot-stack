"""Verify live release assets match a pushed app tag.

Alpha-tag verification checks that ``alpha.yml`` points at the tagged version. If a beta desktop
build published after that alpha tag without a follow-up alpha publish, ``alpha.yml`` may still
reference the beta build even though alpha artifacts exist in ``releases.json``. In that case
re-publish an alpha desktop build (or verify artifacts directly) before treating alpha YAML
checks as authoritative.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import httpx
import yaml
from rich.console import Console
from rich.table import Table

from automation.asset_inventory import ReleasePlatformConfig
from automation.asset_urls import AssetChannel, app_manifest_url, app_yaml_url, robot_manifest_url
from automation.cloudfront_invalidation import RobotPath, release_channel_from_tag, resolve_release_tag
from automation.flex_assets import FLEX_CONFIG
from automation.flex_urls import FLEX_CHANNELS
from automation.go import strip_tag_version
from automation.ot2_assets import OT2_CONFIG
from automation.ot2_urls import OT2_CHANNELS
from automation.release import robot_manifest_production_entries
from automation.release_tag_catalog import flex_tag_stability, ot2_tag_stability

Stability = Literal["stable", "alpha", "beta"]
CheckStatus = Literal["pass", "fail", "skip"]

STABILITY_YAML_FILES: dict[Stability, tuple[str, ...]] = {
    "stable": ("latest.yml", "latest-mac.yml", "latest-linux.yml"),
    "beta": ("beta.yml", "beta-mac.yml", "beta-linux.yml"),
    "alpha": ("alpha.yml", "alpha-mac.yml", "alpha-linux.yml"),
}


@dataclass(frozen=True)
class AssetCheck:
    """One release asset verification result."""

    name: str
    status: CheckStatus
    detail: str
    url: Optional[str] = None


@dataclass
class AssetVerificationReport:
    """Collected asset checks for one tagged release."""

    path: RobotPath
    tag: str
    release_type: str
    stability: Stability
    manifest_version: str
    channel: AssetChannel
    checks: list[AssetCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True when no checks failed."""
        return all(check.status != "fail" for check in self.checks)


def platform_config(path: RobotPath) -> ReleasePlatformConfig:
    """Return the asset inventory config for one robot path."""
    if path == "flex":
        return FLEX_CONFIG
    return OT2_CONFIG


def channel_for_release(path: RobotPath, tag: str) -> AssetChannel:
    """Return the asset channel (internal/external) for a release tag."""
    release_type = release_channel_from_tag(tag)
    channels = FLEX_CHANNELS if path == "flex" else OT2_CHANNELS
    for channel in channels:
        if channel.channel == release_type:
            return channel
    raise ValueError(f"No asset channel configured for {path} {release_type}")


def manifest_version_from_tag(path: RobotPath, tag: str) -> str:
    """Map an app release tag to the version key used in releases.json."""
    version = strip_tag_version(tag)
    if path == "flex":
        return version
    return version


def stability_from_tag(path: RobotPath, tag: str, release_type: str) -> Stability:
    """Infer the stability lane from a release tag."""
    if path == "flex":
        lane = flex_tag_stability(tag, release_type)
    else:
        lane = ot2_tag_stability(tag, release_type)
    if lane is None:
        raise ValueError(f"Could not infer stability lane from tag {tag!r}")
    return lane


def expected_yaml_files(stability: Stability) -> tuple[str, ...]:
    """Return electron-updater YAML files that should point at this release.

    Note: when verifying an alpha tag, ``alpha.yml`` fails if a later beta publish overwrote it
    without a follow-up alpha publish. Beta and stable lanes are unaffected by alpha publishes.
    """
    return STABILITY_YAML_FILES[stability]


def expects_matching_robot_version(path: RobotPath, release_type: str) -> bool:
    """Return True when the robot manifest should use the same version as the app tag."""
    if path == "flex":
        return True
    return release_type == "internal"


async def fetch_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    """GET JSON from a manifest URL."""
    response = await client.get(url, timeout=20.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object from {url}")
    return payload


async def fetch_yaml_version(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """GET one electron-updater YAML and return its version field."""
    response = await client.get(url, timeout=20.0)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = yaml.safe_load(response.text) or {}
    if not isinstance(data, dict):
        return None
    version = data.get("version")
    return str(version) if version else None


async def url_is_reachable(client: httpx.AsyncClient, url: str) -> tuple[bool, str]:
    """Return whether an artifact URL responds with HTTP success."""
    try:
        response = await client.head(url, timeout=20.0, follow_redirects=True)
        if response.status_code >= 400:
            response = await client.get(url, timeout=20.0, follow_redirects=True)
        if response.status_code >= 400:
            return False, f"HTTP {response.status_code}"
        return True, f"HTTP {response.status_code}"
    except Exception as exc:  # noqa: BLE001 - report fetch failures in the check table
        return False, str(exc)


def add_check(
    report: AssetVerificationReport,
    name: str,
    *,
    ok: bool,
    detail: str,
    url: Optional[str] = None,
    skipped: bool = False,
) -> None:
    """Append one pass/fail/skip check to a report."""
    if skipped:
        status: CheckStatus = "skip"
    elif ok:
        status = "pass"
    else:
        status = "fail"
    report.checks.append(AssetCheck(name=name, status=status, detail=detail, url=url))


async def verify_release_assets(
    path: RobotPath,
    tag: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> AssetVerificationReport:
    """Verify live manifests and artifacts for one release tag."""
    release_type = release_channel_from_tag(tag)
    channel = channel_for_release(path, tag)
    manifest_version = manifest_version_from_tag(path, tag)
    stability = stability_from_tag(path, tag, release_type)
    report = AssetVerificationReport(
        path=path,
        tag=tag,
        release_type=release_type,
        stability=stability,
        manifest_version=manifest_version,
        channel=channel,
    )

    owns_client = client is None
    active_client = client or httpx.AsyncClient(follow_redirects=True)
    try:
        app_url = app_manifest_url(channel)
        robot_url = robot_manifest_url(channel, platform_config(path).robot_prefix)

        try:
            app_manifest = await fetch_json(active_client, app_url)
            production = app_manifest.get("production", {})
            if not isinstance(production, dict):
                raise ValueError("app releases.json missing production object")
            app_entry = production.get(manifest_version)
            add_check(
                report,
                "app releases.json version",
                ok=isinstance(app_entry, dict),
                detail=f"expected {manifest_version} in {app_url}",
                url=app_url,
            )
        except Exception as exc:  # noqa: BLE001
            add_check(
                report,
                "app releases.json version",
                ok=False,
                detail=str(exc),
                url=app_url,
            )
            app_entry = None

        if expects_matching_robot_version(path, release_type):
            try:
                robot_manifest = await fetch_json(active_client, robot_url)
                robot_production = robot_manifest_production_entries(robot_manifest)
                robot_entry = robot_production.get(manifest_version)
                add_check(
                    report,
                    "robot releases.json version",
                    ok=isinstance(robot_entry, dict),
                    detail=f"expected {manifest_version} in {robot_url}",
                    url=robot_url,
                )
            except Exception as exc:  # noqa: BLE001
                add_check(
                    report,
                    "robot releases.json version",
                    ok=False,
                    detail=str(exc),
                    url=robot_url,
                )
                robot_entry = None
        else:
            robot_entry = None
            add_check(
                report,
                "robot releases.json version",
                ok=True,
                detail="skipped for OT-2 external (buildroot uses independent robot OS semver)",
                url=robot_url,
                skipped=True,
            )

        for filename in expected_yaml_files(stability):
            yaml_url = app_yaml_url(channel, filename)
            try:
                yaml_version = await fetch_yaml_version(active_client, yaml_url)
                if yaml_version is None:
                    add_check(
                        report,
                        f"{filename} version",
                        ok=False,
                        detail="not published",
                        url=yaml_url,
                    )
                    continue
                add_check(
                    report,
                    f"{filename} version",
                    ok=yaml_version == manifest_version,
                    detail=f"expected {manifest_version}, got {yaml_version}",
                    url=yaml_url,
                )
            except Exception as exc:  # noqa: BLE001
                add_check(
                    report,
                    f"{filename} version",
                    ok=False,
                    detail=str(exc),
                    url=yaml_url,
                )

        if isinstance(app_entry, dict):
            asset_urls = [value for key, value in app_entry.items() if isinstance(value, str) and key != "revoked"]
            for asset_url in asset_urls:
                ok, detail = await url_is_reachable(active_client, asset_url)
                add_check(
                    report,
                    "app artifact",
                    ok=ok,
                    detail=detail,
                    url=asset_url,
                )

        if isinstance(robot_entry, dict):
            for label, robot_asset_url in (
                ("robot full image", robot_entry.get("fullImage", "")),
                ("robot system", robot_entry.get("system", "")),
                ("robot VERSION.json", robot_entry.get("version", "")),
                ("robot release notes", robot_entry.get("releaseNotes", "")),
            ):
                if not isinstance(robot_asset_url, str) or not robot_asset_url:
                    continue
                ok, detail = await url_is_reachable(active_client, robot_asset_url)
                add_check(
                    report,
                    label,
                    ok=ok,
                    detail=detail,
                    url=robot_asset_url,
                )
    finally:
        if owns_client:
            await active_client.aclose()

    return report


def print_verification_report(report: AssetVerificationReport, output: Console | None = None) -> None:
    """Render a Rich table of asset verification checks."""
    out = output or Console(log_time=False)
    out.print()
    out.print("[bold green]Release asset verification[/]")
    out.print(
        f"tag={report.tag} path={report.path} channel={report.release_type} "
        f"stability={report.stability} manifest_version={report.manifest_version}"
    )
    out.print(f"app host={report.channel.app_host} robot host={report.channel.robot_host}")
    out.print()

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("URL")
    for check in report.checks:
        if check.status == "pass":
            status_text = "[green]pass[/]"
        elif check.status == "skip":
            status_text = "[yellow]skip[/]"
        else:
            status_text = "[red]fail[/]"
        table.add_row(check.name, status_text, check.detail, check.url or "")
    out.print(table)

    if report.passed:
        out.print("[green]All checks passed.[/]")
    else:
        failed = sum(1 for check in report.checks if check.status == "fail")
        out.print(f"[red]{failed} check(s) failed.[/]")


async def verify_release_assets_cli(
    *,
    tag: Optional[str],
    path: Optional[RobotPath],
    release_type: Optional[str],
    non_interactive: bool,
    output: Console | None = None,
) -> AssetVerificationReport:
    """Resolve CLI args and verify assets for one release tag."""
    path_name, resolved_tag = resolve_release_tag(
        tag,
        path=path,
        release_type=release_type,
        non_interactive=non_interactive,
    )
    report = await verify_release_assets(path_name, resolved_tag)
    print_verification_report(report, output=output)
    return report


def run_verify_release_assets_cli(
    *,
    tag: Optional[str],
    path: Optional[RobotPath],
    release_type: Optional[str],
    non_interactive: bool,
    output: Console | None = None,
) -> AssetVerificationReport:
    """Sync wrapper for verify_release_assets_cli."""
    return asyncio.run(
        verify_release_assets_cli(
            tag=tag,
            path=path,
            release_type=release_type,
            non_interactive=non_interactive,
            output=output,
        )
    )
