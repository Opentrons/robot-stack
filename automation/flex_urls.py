"""Flex asset host and manifest URL constants."""

from typing import Final, Tuple

from automation.asset_urls import AssetChannel

FLEX_EXTERNAL_APP_HOST: Final[str] = "builds.opentrons.com"
FLEX_INTERNAL_APP_HOST: Final[str] = "ot3-development.builds.opentrons.com"
FLEX_EXTERNAL_ROBOT_HOST: Final[str] = "builds.opentrons.com"
FLEX_INTERNAL_ROBOT_HOST: Final[str] = "ot3-development.builds.opentrons.com"

FLEX_ROBOT_PREFIX: Final[str] = "ot3-oe"

FLEX_EXTERNAL: Final[AssetChannel] = AssetChannel(
    label="External",
    channel="external",
    app_host=FLEX_EXTERNAL_APP_HOST,
    robot_host=FLEX_EXTERNAL_ROBOT_HOST,
)

FLEX_INTERNAL: Final[AssetChannel] = AssetChannel(
    label="Internal",
    channel="internal",
    app_host=FLEX_INTERNAL_APP_HOST,
    robot_host=FLEX_INTERNAL_ROBOT_HOST,
)

FLEX_CHANNELS: Final[Tuple[AssetChannel, ...]] = (FLEX_EXTERNAL, FLEX_INTERNAL)
