#!/usr/bin/env python3
"""Fetch OT-2 app and robot release assets and render a local HTML inventory."""

from __future__ import annotations

import re
from pathlib import Path

from automation.asset_inventory import PipelineRow, ReleasePlatformConfig, run_cli
from automation.ot2_urls import OT2_CHANNELS, OT2_LEGACY_EXTERNAL_APP_HOST, OT2_ROBOT_PREFIX

OT2_CONFIG = ReleasePlatformConfig(
    display_name="OT-2",
    html_title="OT-2 release assets",
    default_output=Path(".build/ot2-assets.html"),
    default_port=8765,
    app_repo="opentrons-ot2",
    robot_repo="buildroot",
    robot_prefix=OT2_ROBOT_PREFIX,
    robot_run_pattern=re.compile(rf"/{re.escape(OT2_ROBOT_PREFIX)}/(\d+)/"),
    channels=OT2_CHANNELS,
    version_scheme="ot2",
    pipeline_intro=(
        "OT-2 assets are uploaded by GitHub Actions in <code>opentrons-ot2</code> (app) "
        "and <code>buildroot</code> (robot OS). Each successful run writes versioned artifacts "
        "under predictable S3 prefixes, then updates the channel manifests below."
    ),
    pipeline_rows=(
        PipelineRow(
            component="App (external)",
            workflow="opentrons-ot2/.github/workflows/app-test-build-deploy.yaml",
            s3_prefix="s3://ot2.builds.opentrons.com/app/",
            manifest="releases.json, alpha*.yml",
            per_build_layout="Opentrons-OT2-v<ver>-<platform>-b<build>.*",
        ),
        PipelineRow(
            component="App (internal)",
            workflow="same workflow (internal-release variant)",
            s3_prefix="s3://ot2-development.builds.opentrons.com/app/",
            manifest="releases.json, latest*.yml",
            per_build_layout="Opentrons-Internal-OT2-v<ver>-<platform>-b<build>.*",
        ),
        PipelineRow(
            component="Robot OS (external)",
            workflow="buildroot/.github/workflows/build.yml",
            s3_prefix="s3://ot2.builds.opentrons.com/ot2-br/",
            manifest="ot2-br/releases.json",
            per_build_layout="ot2-br/<github.run_id>/ot2-fullimage.zip",
        ),
        PipelineRow(
            component="Robot OS (internal)",
            workflow="same workflow (internal-release variant)",
            s3_prefix="s3://ot2-development.builds.opentrons.com/ot2-br/",
            manifest="ot2-br/releases.json",
            per_build_layout="ot2-br/<github.run_id>/ot2-system.zip",
        ),
    ),
    pipeline_footnote=(
        "See the channel section below for robot vs app manifest authority. "
        "OT-2 robots read <code>ot2-br/releases.json</code> for on-robot updates. "
        "External app URLs in <code>releases.json</code> use "
        "<code>https://ot2.builds.opentrons.com/app/</code> after "
        "<code>feat/ot2-calendar-semver-build</code> (edge still writes <code>ot2.opentrons.com</code>)."
    ),
    legacy_app_host=OT2_LEGACY_EXTERNAL_APP_HOST,
    legacy_app_host_note=(
        f"Production releases.json may still list {OT2_LEGACY_EXTERNAL_APP_HOST}; "
        "feat/ot2-calendar-semver-build in opentrons-ot2 switches that to ot2.builds.opentrons.com."
    ),
)


def main() -> None:
    """CLI entrypoint."""
    run_cli(OT2_CONFIG)


if __name__ == "__main__":
    main()
