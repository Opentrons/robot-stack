"""Tests for structured release plan building and serialization."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation.go import RELEASE_PATHS, RepoState
from automation.release_plan import (
    PLAN_SCHEMA_VERSION,
    RepoReleasePlan,
    TagStep,
    assess_plan_apply,
    assess_repo_apply_state,
    build_release_plan,
    build_tag_steps,
    check_plan_staleness,
    compute_head_commit_checksum,
    default_plan_path,
    load_release_plan,
    plan_filename,
    release_plan_from_dict,
    release_plan_to_dict,
    with_plan_integrity,
    write_release_plan,
)

FLEX = RELEASE_PATHS["flex"]


class BuildTagStepsTests(unittest.TestCase):
    def test_includes_checkout_and_verify_for_non_default_branch(self) -> None:
        steps = build_tag_steps(
            repo_name="oe-core",
            branch="chore_release-9.1.0",
            default_branch="main",
            head_commit="abc123",
            needs_tag=True,
            next_tag="v9.1.0-alpha.4",
            release_version="v9.1.0-alpha.4",
        )
        self.assertEqual(steps[0].action, "checkout")
        self.assertEqual(steps[1].action, "verify_remote_branch")
        self.assertEqual(steps[1].expected_commit, "abc123")
        self.assertEqual(steps[-1].action, "push_tags")

    def test_firmware_dual_tag_steps(self) -> None:
        steps = build_tag_steps(
            repo_name="ot3-firmware",
            branch="main",
            default_branch="main",
            head_commit="deadbeef",
            needs_tag=True,
            next_tag="ex9.1.0-alpha.7",
            release_version="v9.1.0-alpha.7",
            secondary_tags=("v70",),
        )
        create_tags = [step.tag for step in steps if step.action == "create_tag"]
        self.assertEqual(create_tags, ["v70", "ex9.1.0-alpha.7"])
        push_step = next(step for step in steps if step.action == "push_tags")
        self.assertEqual(push_step.tags, ("v70", "ex9.1.0-alpha.7"))

    def test_skip_when_no_tag_needed(self) -> None:
        steps = build_tag_steps(
            repo_name="oe-core",
            branch="main",
            default_branch="main",
            head_commit="abc123",
            needs_tag=False,
            next_tag=None,
            release_version="v9.1.0",
        )
        self.assertEqual(steps, ())


class ReleasePlanSerializationTests(unittest.TestCase):
    def test_round_trip_dict(self) -> None:
        sample = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "generated_at": "2026-07-14T12:00:00+00:00",
            "release": {
                "path": "flex",
                "path_label": "Flex",
                "release_type": "internal",
                "stability": "beta",
                "version": "v4.0.0",
                "app_tag": "ot3@4.0.0-beta.0",
                "release_version": "ot3@4.0.0-beta.0",
            },
            "branches": {
                "app_branch": "edge",
                "stack_branches": {"oe-core": "main"},
            },
            "push_order": ["ot3-firmware", "oe-core", "opentrons"],
            "repos": [
                {
                    "name": "opentrons",
                    "role": "app",
                    "local_path": "opentrons",
                    "default_branch": "edge",
                    "branch": "edge",
                    "needs_tag": True,
                    "reason": "App monorepo tag (always last)",
                    "latest_tag": None,
                    "next_tags": ["ot3@4.0.0-beta.0"],
                    "head_commit": "abc123",
                    "existing_firmware_version_tag": None,
                    "steps": [
                        {
                            "action": "verify_remote_branch",
                            "branch": "edge",
                            "expected_commit": "abc123",
                        },
                        {
                            "action": "create_tag",
                            "tag": "ot3@4.0.0-beta.0",
                            "message": "chore(release): ot3@4.0.0-beta.0",
                        },
                        {"action": "verify_tag_log", "tag": "ot3@4.0.0-beta.0", "count": 10},
                        {"action": "push_tags", "tags": ["ot3@4.0.0-beta.0"]},
                    ],
                }
            ],
            "follow_ups": [
                {
                    "phase": "pre_apply",
                    "command": "just validate-release-tags --tag ot3@4.0.0-beta.0",
                    "description": "Verify coordinated tags",
                    "required_before_app_push": True,
                }
            ],
        }
        plan = release_plan_from_dict(sample)
        restored = release_plan_to_dict(plan)
        self.assertEqual(restored["release"]["app_tag"], "ot3@4.0.0-beta.0")
        self.assertEqual(restored["repos"][0]["head_commit"], "abc123")

    def test_write_and_load_plan_file(self) -> None:
        sample = _sample_plan_dict()
        plan = release_plan_from_dict(sample)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / plan_filename("ot3@4.0.0-beta.0")
            write_release_plan(plan, path)
            loaded = load_release_plan(path)
            self.assertEqual(loaded.app_tag, "ot3@4.0.0-beta.0")
            self.assertIsNotNone(loaded.head_commit_checksum)
            self.assertTrue(path.read_text(encoding="utf-8").startswith("# Opentrons robot-stack release plan"))

    def test_default_plan_path_uses_app_tag(self) -> None:
        self.assertEqual(
            default_plan_path("internal@26.5.2601"),
            Path(".build/plans/internal@26.5.2601.plan.yaml"),
        )


class BuildReleasePlanTests(unittest.TestCase):
    @patch("automation.go.branch_head_commit", return_value="abc123")
    @patch("automation.go.compute_app_tag", return_value="ot3@4.0.0-beta.0")
    @patch("automation.go.get_stack_repo_tag_plan")
    def test_builds_push_order_with_app_last(
        self,
        mock_stack_plan: MagicMock,
        _mock_app_tag: object,
        _mock_head: object,
    ) -> None:
        from automation.go import TagPlan

        mock_stack_plan.side_effect = [
            TagPlan(
                needs_tag=False,
                latest_tag="ot3@4.0.0-beta.0",
                next_tag=None,
                branch="main",
                reason="Already tagged",
            ),
            TagPlan(
                needs_tag=False,
                latest_tag="ot3@4.0.0-beta.0",
                next_tag=None,
                branch="main",
                reason="Already tagged",
            ),
        ]
        results = {
            "opentrons": RepoState(),
            "oe-core": RepoState(),
            "ot3-firmware": RepoState(),
        }

        plan = build_release_plan(
            release_path=FLEX,
            release_type="internal",
            stability="beta",
            version="v4.0.0",
            results=results,
        )

        self.assertEqual(plan.app_tag, "ot3@4.0.0-beta.0")
        self.assertEqual(plan.push_order[-1], "opentrons")
        self.assertTrue(any(repo.name == "opentrons" and repo.role == "app" for repo in plan.repos))


def _sample_plan_dict() -> dict:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "generated_at": "2026-07-14T12:00:00+00:00",
        "release": {
            "path": "flex",
            "path_label": "Flex",
            "release_type": "internal",
            "stability": "beta",
            "version": "v4.0.0",
            "app_tag": "ot3@4.0.0-beta.0",
            "release_version": "ot3@4.0.0-beta.0",
        },
        "branches": {"app_branch": None, "stack_branches": {}},
        "push_order": ["oe-core", "opentrons"],
        "repos": [
            {
                "name": "oe-core",
                "role": "stack",
                "local_path": "oe-core",
                "default_branch": "main",
                "branch": "main",
                "needs_tag": True,
                "reason": "Needs tag",
                "latest_tag": None,
                "next_tags": ["ot3@4.0.0-beta.0"],
                "head_commit": "aaa111",
                "existing_firmware_version_tag": None,
                "steps": [],
            },
            {
                "name": "opentrons",
                "role": "app",
                "local_path": "opentrons",
                "default_branch": "edge",
                "branch": "edge",
                "needs_tag": True,
                "reason": "App monorepo tag (always last)",
                "latest_tag": None,
                "next_tags": ["ot3@4.0.0-beta.0"],
                "head_commit": "bbb222",
                "existing_firmware_version_tag": None,
                "steps": [],
            },
        ],
        "follow_ups": [],
    }


class PlanIntegrityTests(unittest.TestCase):
    def test_checksum_is_stable_for_same_commits(self) -> None:
        plan = release_plan_from_dict(_sample_plan_dict())
        first = compute_head_commit_checksum(plan)
        second = compute_head_commit_checksum(plan)
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))

    def test_checksum_changes_when_head_commit_changes(self) -> None:
        plan = release_plan_from_dict(_sample_plan_dict())
        original = compute_head_commit_checksum(plan)
        data = _sample_plan_dict()
        data["repos"][0]["head_commit"] = "changed1"
        changed = compute_head_commit_checksum(release_plan_from_dict(data))
        self.assertNotEqual(original, changed)

    def test_write_plan_includes_checksum(self) -> None:
        plan = release_plan_from_dict(_sample_plan_dict())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / plan_filename(plan.app_tag)
            write_release_plan(plan, path)
            loaded = load_release_plan(path)
            self.assertIsNotNone(loaded.head_commit_checksum)
            self.assertIn("integrity:", path.read_text(encoding="utf-8"))

    def test_with_plan_integrity_sets_checksum(self) -> None:
        plan = release_plan_from_dict(_sample_plan_dict())
        annotated = with_plan_integrity(plan)
        self.assertEqual(annotated.head_commit_checksum, compute_head_commit_checksum(plan))


class PlanStalenessTests(unittest.TestCase):
    @patch("automation.release_plan.fetch_remote_branch_head")
    def test_detects_drifted_repo(self, mock_fetch: MagicMock) -> None:
        plan = with_plan_integrity(release_plan_from_dict(_sample_plan_dict()))
        mock_fetch.side_effect = ["aaa111", "ccc333"]

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "oe-core").mkdir()
            (workspace / "opentrons").mkdir()
            report = check_plan_staleness(plan, workspace)

        self.assertTrue(report.is_stale)
        self.assertEqual(len(report.drifts), 1)
        self.assertEqual(report.drifts[0].name, "opentrons")
        self.assertEqual(report.drifts[0].remote_commit, "ccc333")

    @patch("automation.release_plan.fetch_remote_branch_head")
    def test_fresh_plan_is_not_stale(self, mock_fetch: MagicMock) -> None:
        plan = with_plan_integrity(release_plan_from_dict(_sample_plan_dict()))
        mock_fetch.side_effect = ["aaa111", "bbb222"]

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "oe-core").mkdir()
            (workspace / "opentrons").mkdir()
            report = check_plan_staleness(plan, workspace)

        self.assertFalse(report.is_stale)
        self.assertEqual(report.drifts, ())

    def test_missing_checksum_is_stale(self) -> None:
        plan = release_plan_from_dict(_sample_plan_dict())
        report = check_plan_staleness(plan, Path("."))
        self.assertTrue(report.is_stale)
        self.assertTrue(report.missing_checksum)


class PlanApplyReadinessTests(unittest.TestCase):
    def _repo(self, *, name: str, head_commit: str, branch: str = "main") -> RepoReleasePlan:
        return RepoReleasePlan(
            name=name,
            role="stack",
            local_path=name,
            default_branch=branch,
            branch=branch,
            needs_tag=True,
            reason="needs tag",
            latest_tag=None,
            next_tags=("ot3@4.0.0-alpha.5",),
            head_commit=head_commit,
            steps=(
                TagStep(action="verify_remote_branch", branch=branch, expected_commit=head_commit),
                TagStep(action="create_tag", tag="ot3@4.0.0-alpha.5", message="msg"),
                TagStep(action="push_tags", tags=("ot3@4.0.0-alpha.5",)),
            ),
        )

    @patch("automation.release_plan.remote_tag_commit", return_value=None)
    @patch("automation.release_plan.fetch_remote_branch_head", return_value="abc123")
    def test_pending_repo_is_ready(self, _mock_fetch: MagicMock, _mock_tag: MagicMock) -> None:
        repo = self._repo(name="oe-core", head_commit="abc123")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "oe-core" / ".git").mkdir(parents=True)
            state = assess_repo_apply_state(repo, workspace)
        self.assertEqual(state.status, "pending")

    @patch("automation.release_plan.remote_tag_commit", return_value="abc123")
    @patch("automation.release_plan.fetch_remote_branch_head", return_value="def456")
    def test_applied_repo_ignores_branch_drift(self, _mock_fetch: MagicMock, _mock_tag: MagicMock) -> None:
        repo = self._repo(name="oe-core", head_commit="abc123")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "oe-core" / ".git").mkdir(parents=True)
            state = assess_repo_apply_state(repo, workspace)
        self.assertEqual(state.status, "applied")

    @patch("automation.release_plan.remote_tag_commit", return_value=None)
    @patch("automation.release_plan.fetch_remote_branch_head", return_value="def456")
    def test_drifted_repo_blocks_apply(self, _mock_fetch: MagicMock, _mock_tag: MagicMock) -> None:
        repo = self._repo(name="opentrons", head_commit="abc123", branch="edge")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "opentrons" / ".git").mkdir(parents=True)
            state = assess_repo_apply_state(repo, workspace)
        self.assertEqual(state.status, "drifted")

    @patch("automation.release_plan.assess_repo_apply_state")
    def test_partial_apply_can_resume(self, mock_assess: MagicMock) -> None:
        from automation.release_plan import RepoApplyState

        plan = with_plan_integrity(release_plan_from_dict(_sample_plan_dict()))
        mock_assess.side_effect = [
            RepoApplyState("oe-core", "applied", "done"),
            RepoApplyState("opentrons", "pending", "ready"),
        ]
        readiness = assess_plan_apply(plan, Path("."))
        self.assertTrue(readiness.can_apply)
        self.assertTrue(readiness.is_partial)
        self.assertEqual(readiness.applied_repos, ("oe-core",))
        self.assertEqual(readiness.pending_repos, ("opentrons",))

    @patch("automation.release_plan.assess_repo_apply_state")
    def test_partial_apply_with_drift_blocks(self, mock_assess: MagicMock) -> None:
        from automation.release_plan import RepoApplyState

        plan = with_plan_integrity(release_plan_from_dict(_sample_plan_dict()))
        mock_assess.side_effect = [
            RepoApplyState("oe-core", "applied", "done"),
            RepoApplyState("opentrons", "drifted", "branch moved"),
        ]
        readiness = assess_plan_apply(plan, Path("."))
        self.assertFalse(readiness.can_apply)
        self.assertTrue(readiness.is_partial)
        self.assertIn("partially applied", readiness.detail)


if __name__ == "__main__":
    unittest.main()
