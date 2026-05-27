"""OT-2 asset host and manifest URL constants."""

from typing import Final, Tuple

from automation.asset_urls import APP_CHANNEL_YAMLS, AssetChannel, app_manifest_url, app_yaml_url, robot_manifest_url

# S3 / CloudFront hosts written by CI (see opentrons-ot2 and buildroot workflows).
OT2_EXTERNAL_APP_HOST: Final[str] = "ot2.builds.opentrons.com"
OT2_INTERNAL_APP_HOST: Final[str] = "ot2-development.builds.opentrons.com"
OT2_EXTERNAL_ROBOT_HOST: Final[str] = "ot2.builds.opentrons.com"
OT2_INTERNAL_ROBOT_HOST: Final[str] = "ot2-development.builds.opentrons.com"

# Legacy host still present in production releases.json until calendar-semver deploy lands.
OT2_LEGACY_EXTERNAL_APP_HOST: Final[str] = "ot2.opentrons.com"

OT2_ROBOT_PREFIX: Final[str] = "ot2-br"

OT2_EXTERNAL: Final[AssetChannel] = AssetChannel(
    label="External",
    channel="external",
    app_host=OT2_EXTERNAL_APP_HOST,
    robot_host=OT2_EXTERNAL_ROBOT_HOST,
)

OT2_INTERNAL: Final[AssetChannel] = AssetChannel(
    label="Internal",
    channel="internal",
    app_host=OT2_INTERNAL_APP_HOST,
    robot_host=OT2_INTERNAL_ROBOT_HOST,
)

OT2_CHANNELS: Final[Tuple[AssetChannel, ...]] = (OT2_EXTERNAL, OT2_INTERNAL)

__all__ = [
    "APP_CHANNEL_YAMLS",
    "AssetChannel",
    "OT2_CHANNELS",
    "OT2_EXTERNAL",
    "OT2_INTERNAL",
    "OT2_LEGACY_EXTERNAL_APP_HOST",
    "OT2_ROBOT_PREFIX",
    "app_manifest_url",
    "app_yaml_url",
    "robot_manifest_url",
]
