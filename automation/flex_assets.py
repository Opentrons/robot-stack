#!/usr/bin/env python3
"""Fetch Flex app and robot release assets and render a local HTML inventory."""

from __future__ import annotations

import re
from pathlib import Path

from automation.asset_inventory import PipelineRow, ReleasePlatformConfig, run_cli
from automation.flex_urls import FLEX_CHANNELS, FLEX_ROBOT_PREFIX

FLEX_CONFIG = ReleasePlatformConfig(
    display_name="Flex",
    html_title="Flex release assets",
    default_output=Path(".build/flex-assets.html"),
    default_port=8766,
    app_repo="opentrons",
    robot_repo="oe-core",
    robot_prefix=FLEX_ROBOT_PREFIX,
    robot_run_pattern=re.compile(rf"/{re.escape(FLEX_ROBOT_PREFIX)}/(\d+)/"),
    channels=FLEX_CHANNELS,
    version_scheme="semver",
    pipeline_intro=(
        "Flex assets are uploaded by GitHub Actions in <code>opentrons</code> (app) "
        "and <code>oe-core</code> (robot OS). Each successful run writes versioned artifacts "
        "under predictable S3 prefixes, then updates the channel manifests below."
    ),
    pipeline_rows=(
        PipelineRow(
            component="App (external)",
            workflow="opentrons/.github/workflows/app-test-build-deploy.yaml",
            s3_prefix="s3://builds.opentrons.com/app/",
            manifest="releases.json, alpha*.yml, beta*.yml, latest*.yml",
            per_build_layout="Opentrons-v<ver>-<platform>-b<build>.*",
        ),
        PipelineRow(
            component="App (internal)",
            workflow="same workflow (internal-release variant)",
            s3_prefix="s3://ot3-development.builds.opentrons.com/app/",
            manifest="releases.json, alpha*.yml, beta*.yml, latest*.yml",
            per_build_layout="Opentrons-Internal-v<ver>-<platform>-b<build>.*",
        ),
        PipelineRow(
            component="Robot OS (external)",
            workflow="oe-core/.github/workflows/build-ot3-actions.yml",
            s3_prefix="s3://builds.opentrons.com/ot3-oe/",
            manifest="ot3-oe/releases.json",
            per_build_layout="ot3-oe/<github.run_id>/ot3-fullimage.tar",
        ),
        PipelineRow(
            component="Robot OS (internal)",
            workflow="same workflow (internal-release variant)",
            s3_prefix="s3://ot3-development.builds.opentrons.com/ot3-oe/",
            manifest="ot3-oe/releases.json",
            per_build_layout="ot3-oe/<github.run_id>/ot3-system.zip",
        ),
    ),
    pipeline_footnote=(
        "Electron-updater reads the channel YAML files directly. The JSON manifests are informational "
        "for humans and release validation; Flex robots read <code>ot3-oe/releases.json</code>. "
        "External app deploy also invalidates the CloudFront distribution for <code>builds.opentrons.com</code>."
    ),
)


def main() -> None:
    """CLI entrypoint."""
    run_cli(FLEX_CONFIG)


if __name__ == "__main__":
    main()
