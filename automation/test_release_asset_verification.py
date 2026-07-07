"""Tests for release asset verification helpers."""

from __future__ import annotations

import unittest

import httpx

from automation.release_asset_verification import (
    AssetVerificationReport,
    channel_for_release,
    expected_yaml_files,
    manifest_version_from_tag,
    stability_from_tag,
    verify_release_assets,
)


class TagMappingTests(unittest.TestCase):
    def test_flex_internal_manifest_version(self) -> None:
        self.assertEqual(manifest_version_from_tag("flex", "ot3@8.5.0-alpha.2"), "8.5.0-alpha.2")

    def test_ot2_internal_manifest_version(self) -> None:
        self.assertEqual(manifest_version_from_tag("ot2", "internal@26.5.2601-alpha"), "26.5.2601-alpha")

    def test_ot2_external_manifest_version(self) -> None:
        self.assertEqual(manifest_version_from_tag("ot2", "v26.6.0-alpha.4"), "26.6.0-alpha.4")

    def test_stability_from_flex_beta_tag(self) -> None:
        self.assertEqual(stability_from_tag("flex", "ot3@4.0.0-beta.1", "internal"), "beta")

    def test_expected_yaml_files_for_alpha(self) -> None:
        self.assertEqual(
            expected_yaml_files("alpha"),
            ("alpha.yml", "alpha-mac.yml", "alpha-linux.yml"),
        )

    def test_channel_for_flex_internal_tag(self) -> None:
        channel = channel_for_release("flex", "ot3@8.5.0")
        self.assertEqual(channel.app_host, "ot3-development.builds.opentrons.com")


class VerifyReleaseAssetsTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_passes_when_manifest_yaml_and_urls_match(self) -> None:
        app_manifest = {
            "production": {
                "8.5.0": {
                    "mac": "https://ot3-development.builds.opentrons.com/app/mac-b1.dmg",
                    "linux": "https://ot3-development.builds.opentrons.com/app/linux-b1.AppImage",
                }
            }
        }
        robot_manifest = {
            "productionV2": {
                "8.5.0": {
                    "fullImage": "https://ot3-development.builds.opentrons.com/ot3-oe/123/full.tar",
                    "system": "https://ot3-development.builds.opentrons.com/ot3-oe/123/system.zip",
                    "version": "https://ot3-development.builds.opentrons.com/ot3-oe/123/VERSION.json",
                    "releaseNotes": "https://ot3-development.builds.opentrons.com/ot3-oe/123/notes.md",
                }
            }
        }

        async def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if url.endswith("/app/releases.json"):
                return httpx.Response(200, json=app_manifest)
            if url.endswith("/ot3-oe/releases.json"):
                return httpx.Response(200, json=robot_manifest)
            if url.endswith("latest.yml"):
                return httpx.Response(200, text="version: 8.5.0\npath: mac-b1.dmg\n")
            if url.endswith("latest-mac.yml"):
                return httpx.Response(200, text="version: 8.5.0\npath: mac-b1.dmg\n")
            if url.endswith("latest-linux.yml"):
                return httpx.Response(200, text="version: 8.5.0\npath: linux-b1.AppImage\n")
            return httpx.Response(200)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            report = await verify_release_assets("flex", "ot3@8.5.0", client=client)

        self.assertIsInstance(report, AssetVerificationReport)
        self.assertTrue(report.passed)
        self.assertTrue(any(check.name == "app releases.json version" and check.status == "pass" for check in report.checks))
        self.assertTrue(any(check.name == "robot releases.json version" and check.status == "pass" for check in report.checks))

    async def test_verify_fails_when_app_version_missing(self) -> None:
        app_manifest = {"production": {"8.4.9": {"mac": "https://example.com/mac.dmg"}}}

        async def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url).endswith("/app/releases.json"):
                return httpx.Response(200, json=app_manifest)
            if str(request.url).endswith("/ot3-oe/releases.json"):
                return httpx.Response(200, json={"productionV2": {}})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            report = await verify_release_assets("flex", "ot3@8.5.0", client=client)

        self.assertFalse(report.passed)
        app_check = next(check for check in report.checks if check.name == "app releases.json version")
        self.assertEqual(app_check.status, "fail")


if __name__ == "__main__":
    unittest.main()
