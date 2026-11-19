"""Tests for the public robot builds page.

Run from the repository root:

    uv run python -m unittest automation.test_robot_builds_page -v
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from automation.robot_builds_page import (
    QA_ALPHA_HREF,
    ManifestSources,
    build_manifest_state,
    publish_is_unchanged,
    render_pages,
)

GENERATED = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
SOURCES = ManifestSources(
    flex_robot="https://builds.example/ot3-oe/releases.json",
    flex_app="https://builds.example/app/releases.json",
    ot2_robot="https://ot2.example/ot2-br/releases.json",
    ot2_app="https://ot2.example/app/releases.json",
)


def _robot(system: str, full_image: str = "https://example.test/full.tar") -> dict[str, str]:
    return {
        "system": system,
        "fullImage": full_image,
        "version": "https://example.test/version.json",
        "releaseNotes": "https://example.test/notes",
    }


def _render(
    flex_robot: dict | None = None,
    flex_app: dict | None = None,
    ot2_robot: dict | None = None,
    ot2_app: dict | None = None,
) -> tuple[str, str]:
    return render_pages(
        flex_robot or {},
        flex_app or {},
        ot2_robot or {},
        ot2_app or {},
        SOURCES,
        GENERATED,
    )


class RobotBuildsPageTest(unittest.TestCase):
    def test_v2_robot_entry_wins_over_legacy(self) -> None:
        main, _alpha = _render(
            flex_robot={
                "production": {"9.1.2": _robot("https://legacy.example/system.zip", "https://legacy.example/full.tar")},
                "productionV2": {
                    "9.1.2": _robot("https://v2.example/system.zip", "https://v2.example/full.tar"),
                    "9.1.0": _robot("https://v2-only.example/system.zip"),
                },
            }
        )
        self.assertIn("https://v2.example/system.zip", main)
        self.assertNotIn("https://legacy.example/system.zip", main)
        self.assertIn("https://v2-only.example/system.zip", main)

    def test_beta_is_omitted_from_the_public_pages(self) -> None:
        main, alpha = _render(
            flex_robot={
                "productionV2": {
                    "9.1.2": _robot("https://example.test/stable-system.zip"),
                    "10.2.0-beta.0": _robot("https://example.test/beta-system.zip"),
                    "8.0.0": _robot("https://example.test/older-stable.zip"),
                    "9.0.0-beta.1": _robot("https://example.test/older-beta.zip"),
                }
            }
        )
        combined = main + alpha
        self.assertIn("9.1.2", main)
        self.assertIn("8.0.0", main)
        self.assertNotIn("10.2.0-beta.0", combined)
        self.assertNotIn("9.0.0-beta.1", combined)
        self.assertNotIn("beta-system.zip", combined)
        self.assertNotIn("class=\"banner beta\"", main)

    def test_alpha_is_only_on_the_qa_page(self) -> None:
        main, alpha = _render(
            flex_robot={"productionV2": {"10.2.0-alpha.3": _robot("https://example.test/alpha-system.zip")}},
            flex_app={"production": {"10.2.0-alpha.3": {"Opentrons.dmg": "https://example.test/alpha.dmg"}}},
        )
        self.assertNotIn("10.2.0-alpha.3", main)
        self.assertNotIn("https://example.test/alpha-system.zip", main)
        self.assertNotIn(QA_ALPHA_HREF, main)
        self.assertIn("10.2.0-alpha.3", alpha)
        self.assertIn("https://example.test/alpha.dmg", alpha)
        self.assertIn('content="noindex"', alpha)
        self.assertNotIn('content="noindex"', main)

    def test_ot2_dev_and_legacy_versions_are_omitted(self) -> None:
        main, alpha = _render(
            ot2_robot={
                "production": {
                    "26.6.0": _robot("https://example.test/ot2-26.6.0.zip"),
                    "26.6.0-beta.1": _robot("https://example.test/ot2-beta.zip"),
                    "26.5.19": _robot("https://example.test/ot2-internal-style.zip"),
                    "26.5.18.dev1": _robot("https://example.test/ot2-dev.zip"),
                    "8.8.2": _robot("https://example.test/ot2-legacy.zip"),
                }
            }
        )
        combined = main + alpha
        self.assertIn("26.6.0", main)
        self.assertNotIn("26.6.0-beta.1", combined)
        for dropped in ("26.5.19", "26.5.18.dev1", "8.8.2", "ot2-internal-style", "ot2-dev.zip", "ot2-legacy"):
            self.assertNotIn(dropped, combined)

    def test_revoked_app_versions_and_yml_keys_are_omitted(self) -> None:
        main, _alpha = _render(
            flex_app={
                "production": {
                    "9.1.2": {
                        "revoked": False,
                        "Opentrons.dmg": "https://example.test/Flex.dmg",
                        "Opentrons.exe": "https://example.test/Flex.exe",
                        "Opentrons.AppImage": "https://example.test/Flex.AppImage",
                        "latest.yml": "https://example.test/latest.yml",
                        "latest-mac.yml": "https://example.test/latest-mac.yml",
                    },
                    "9.0.0": {
                        "revoked": True,
                        "Opentrons.dmg": "https://example.test/revoked.dmg",
                    },
                }
            },
            flex_robot={"productionV2": {"9.0.0": _robot("https://example.test/revoked-robot.zip")}},
        )
        self.assertIn("https://example.test/Flex.dmg", main)
        self.assertIn("https://example.test/Flex.exe", main)
        self.assertIn("https://example.test/Flex.AppImage", main)
        self.assertNotIn("latest.yml", main)
        self.assertNotIn("revoked.dmg", main)
        self.assertNotIn("revoked-robot.zip", main)
        self.assertNotIn(">9.0.0<", main)


    def test_older_builds_preview_then_expand(self) -> None:
        versions = {
            f"{9 - i}.0.0": _robot(f"https://example.test/system-{9 - i}.zip")
            for i in range(6)
        }
        main, _alpha = _render(flex_robot={"productionV2": versions})
        history = main.split('data-history=""', 1)[1].split("</section>", 1)[0]
        # current stable 9.0.0 is the banner; older are 8..4 -> 5 older, preview 3 + 2 more
        self.assertIn("8.0.0", history)
        self.assertIn("7.0.0", history)
        self.assertIn("6.0.0", history)
        self.assertIn('class="history-more"', history)
        self.assertIn("Show 2 more", history)
        preview, _sep, more = history.partition('<details class="history-more">')
        self.assertIn("8.0.0", preview)
        self.assertIn("7.0.0", preview)
        self.assertIn("6.0.0", preview)
        self.assertNotIn("5.0.0", preview)
        self.assertIn("5.0.0", more)
        self.assertIn("4.0.0", more)

    def test_system_zip_is_primary_and_full_image_is_only_on_current_stable(self) -> None:
        main, _alpha = _render(
            flex_robot={
                "productionV2": {
                    "9.1.2": _robot("https://example.test/system.zip", "https://example.test/full-image.tar"),
                    "9.0.0": _robot("https://example.test/older-system.zip", "https://example.test/older-full-image.tar"),
                }
            }
        )
        banner = main.split('data-banner="stable"', 1)[1].split("</article>", 1)[0]
        actions, _separator, disclosure = banner.partition("<details")
        self.assertIn("https://example.test/system.zip", actions)
        self.assertNotIn("https://example.test/full-image.tar", actions)
        self.assertIn("https://example.test/full-image.tar", disclosure)
        self.assertIn("Full reflash image", disclosure)
        history = main.split('data-history=""', 1)[1]
        self.assertIn("https://example.test/older-system.zip", history)
        self.assertNotIn("https://example.test/older-full-image.tar", history)
        self.assertNotIn("Full reflash image", history)

    def test_footer_names_the_manifests_and_the_generation_time(self) -> None:
        main, alpha = _render()
        for page in (main, alpha):
            self.assertIn("Generated 2026-11-16 15:00 UTC.", page)
            for url in SOURCES.as_tuple():
                self.assertIn(url, page)



class ManifestStateTest(unittest.TestCase):
    def test_unchanged_when_manifests_and_source_match(self) -> None:
        sources = SOURCES
        bodies = {url: f"body-{i}".encode() for i, url in enumerate(sources.as_tuple())}
        current = build_manifest_state(sources, bodies, source_sha="abc")
        self.assertTrue(publish_is_unchanged(current, current))

    def test_changed_when_a_manifest_hash_differs(self) -> None:
        sources = SOURCES
        bodies = {url: f"body-{i}".encode() for i, url in enumerate(sources.as_tuple())}
        previous = build_manifest_state(sources, bodies, source_sha="abc")
        bodies[sources.flex_robot] = b"different"
        current = build_manifest_state(sources, bodies, source_sha="abc")
        self.assertFalse(publish_is_unchanged(previous, current))

    def test_changed_when_source_sha_differs(self) -> None:
        sources = SOURCES
        bodies = {url: f"body-{i}".encode() for i, url in enumerate(sources.as_tuple())}
        previous = build_manifest_state(sources, bodies, source_sha="abc")
        current = build_manifest_state(sources, bodies, source_sha="def")
        self.assertFalse(publish_is_unchanged(previous, current))

    def test_missing_previous_state_is_a_publish(self) -> None:
        sources = SOURCES
        bodies = {url: b"x" for url in sources.as_tuple()}
        current = build_manifest_state(sources, bodies, source_sha="abc")
        self.assertFalse(publish_is_unchanged(None, current))


if __name__ == "__main__":
    unittest.main()
