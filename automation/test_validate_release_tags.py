"""Tests for coordinated Flex release tag validation."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from automation.flex_coordinated_tags import (
    is_firmware_version_tag,
    normalize_tag,
    stack_coordinated_tag_to_firmware_tag,
)
from automation.validate_release_tags import (
    check_tag_in_repo,
    fetch_repo,
    is_flex_stack_coordination_tag,
)


class NormalizeTagTests(unittest.TestCase):
    """normalize_tag strips refs/tags/ when present."""

    def test_plain_tag(self) -> None:
        self.assertEqual(normalize_tag("ot3@8.5.0-alpha.0"), "ot3@8.5.0-alpha.0")

    def test_refs_tags_prefix(self) -> None:
        self.assertEqual(
            normalize_tag("refs/tags/v10.0.0-beta.1"),
            "v10.0.0-beta.1",
        )


class CoordinatedTagSchemeTests(unittest.TestCase):
    """is_flex_stack_coordination_tag recognizes ot3@ and external v* tags."""

    def test_internal_tag(self) -> None:
        self.assertTrue(is_flex_stack_coordination_tag("ot3@8.5.0-beta.0"))

    def test_external_tag(self) -> None:
        self.assertTrue(is_flex_stack_coordination_tag("v10.0.0-alpha.0"))

    def test_firmware_integer_not_stack_tag(self) -> None:
        self.assertFalse(is_flex_stack_coordination_tag("v70"))
        self.assertTrue(is_firmware_version_tag("v70"))

    def test_legacy_internal_prefix_rejected(self) -> None:
        self.assertFalse(is_flex_stack_coordination_tag("internal@8.5.0"))

    def test_external_maps_to_ex_on_firmware(self) -> None:
        self.assertEqual(
            stack_coordinated_tag_to_firmware_tag("v9.1.0-alpha.7"),
            "ex9.1.0-alpha.7",
        )


class FetchRepoTests(unittest.TestCase):
    """fetch_repo force-updates local tags from origin."""

    def test_fetch_uses_force_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

            def fake_run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(args, ["fetch", "--tags", "--force", "origin"])
                self.assertEqual(cwd, repo)
                return completed

            import automation.validate_release_tags as validate_module

            original = validate_module.run_git
            validate_module.run_git = fake_run_git  # type: ignore[method-assign]
            try:
                fetch_repo(repo)
            finally:
                validate_module.run_git = original


class CheckTagInRepoTests(unittest.TestCase):
    """check_tag_in_repo resolves annotated tags in a temp git repo."""

    def test_finds_existing_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            (repo / "README").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "add", "README"], cwd=repo, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "initial"],
                cwd=repo,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "tag", "-a", "ot3@1.0.0", "-m", "release"],
                cwd=repo,
                check=True,
                capture_output=True,
            )

            result = check_tag_in_repo("opentrons", repo, "ot3@1.0.0")
            self.assertTrue(result.present)
            self.assertIsNotNone(result.commit)

    def test_missing_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            result = check_tag_in_repo("oe-core", repo, "ot3@9.9.9")
            self.assertFalse(result.present)


if __name__ == "__main__":
    unittest.main()
