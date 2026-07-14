"""Tests for release plan apply ordering."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation.apply_release_plan import apply_repo_plan
from automation.release_plan import FollowUpCommand, RepoReleasePlan, TagStep


class ApplyRepoPlanTests(unittest.TestCase):
    def _app_repo(self) -> RepoReleasePlan:
        return RepoReleasePlan(
            name="opentrons",
            role="app",
            local_path="opentrons",
            default_branch="edge",
            branch="edge",
            needs_tag=True,
            reason="App monorepo tag (always last)",
            latest_tag=None,
            next_tags=("ot3@4.0.0-alpha.5",),
            head_commit="abc123",
            steps=(
                TagStep(action="create_tag", tag="ot3@4.0.0-alpha.5", message="msg"),
                TagStep(action="verify_tag_log", tag="ot3@4.0.0-alpha.5", count=10),
                TagStep(action="push_tags", tags=("ot3@4.0.0-alpha.5",)),
            ),
        )

    @patch("automation.apply_release_plan.run_follow_up", return_value="just validate-release-tags ...")
    @patch("automation.apply_release_plan.execute_step", return_value="git step")
    def test_validate_runs_before_push_not_before_create(
        self,
        mock_execute: MagicMock,
        mock_follow_up: MagicMock,
    ) -> None:
        repo = self._app_repo()
        follow_up = FollowUpCommand(
            phase="pre_apply",
            command="just validate-release-tags --tag ot3@4.0.0-alpha.5",
            description="validate",
            required_before_app_push=True,
        )

        with patch.object(Path, "resolve", return_value=Path("/tmp/opentrons")):
            result = apply_repo_plan(
                repo,
                Path("."),
                dry_run=True,
                pre_push_follow_ups=(follow_up,),
            )

        self.assertTrue(result.applied)
        self.assertEqual(mock_execute.call_count, 3)
        executed_actions = [call.args[0].action for call in mock_execute.call_args_list]
        self.assertEqual(executed_actions, ["create_tag", "verify_tag_log", "push_tags"])
        mock_follow_up.assert_called_once()


if __name__ == "__main__":
    unittest.main()
