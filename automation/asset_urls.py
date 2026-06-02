"""Shared release asset URL types and helpers."""

from dataclasses import dataclass
from typing import Final, Tuple

APP_PREFIX: Final[str] = "app"

APP_CHANNEL_YAMLS: Final[Tuple[str, ...]] = (
    "alpha.yml",
    "alpha-mac.yml",
    "alpha-linux.yml",
    "beta.yml",
    "beta-mac.yml",
    "beta-linux.yml",
    "latest.yml",
    "latest-mac.yml",
    "latest-linux.yml",
)


@dataclass(frozen=True)
class AssetChannel:
    """One release channel (internal or external) for app and robot manifests."""

    label: str
    channel: str
    app_host: str
    robot_host: str


def app_manifest_url(channel: AssetChannel) -> str:
    """Return the app releases.json URL for a channel (edge routing and release validation)."""
    return f"https://{channel.app_host}/{APP_PREFIX}/releases.json"


def robot_manifest_url(channel: AssetChannel, robot_prefix: str) -> str:
    """Return the robot OS releases.json URL for a channel (on-robot source of truth)."""
    return f"https://{channel.robot_host}/{robot_prefix}/releases.json"


def app_yaml_url(channel: AssetChannel, filename: str) -> str:
    """Return a channel YAML URL used by electron-updater."""
    return f"https://{channel.app_host}/{APP_PREFIX}/{filename}"
