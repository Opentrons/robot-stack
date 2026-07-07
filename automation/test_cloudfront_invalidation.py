"""Tests for CloudFront invalidation helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from automation.cloudfront_invalidation import (
    CloudFrontInvalidationPlan,
    CloudFrontInvalidationRun,
    CloudFrontReleaseTarget,
    create_cloudfront_invalidation,
    format_create_invalidation_command,
    get_cloudfront_invalidation,
    parse_invalidation_payload,
    wait_for_cloudfront_invalidation,
)


def _sample_plan() -> CloudFrontInvalidationPlan:
    return CloudFrontInvalidationPlan(
        target=CloudFrontReleaseTarget(
            label="Flex external",
            host="builds.opentrons.com",
            infra_stack="release-ci",
            robot_prefix="ot3-oe",
        ),
        distribution_id="E1234567890",
        distribution_url="https://builds.opentrons.com/",
        paths=("/app/*", "/ot3-oe/*"),
        profile="robotics_robot_stack_prod-admin",
    )


class FormatCreateInvalidationCommandTests(unittest.TestCase):
    def test_includes_json_output_flag(self) -> None:
        command = format_create_invalidation_command(_sample_plan(), "E1234567890")
        self.assertIn("--output json", command)
        self.assertIn('"/app/*"', command)
        self.assertIn('"/ot3-oe/*"', command)


class ParseInvalidationPayloadTests(unittest.TestCase):
    def test_parses_create_response(self) -> None:
        payload = {
            "Invalidation": {
                "Id": "I2J3K4L5",
                "Status": "InProgress",
                "CreateTime": "2026-07-07T12:00:00.000Z",
            }
        }
        run = parse_invalidation_payload(payload, "E1234567890")
        self.assertEqual(
            run,
            CloudFrontInvalidationRun(
                invalidation_id="I2J3K4L5",
                distribution_id="E1234567890",
                status="InProgress",
                create_time="2026-07-07T12:00:00.000Z",
            ),
        )


class CloudFrontInvalidationExecutionTests(unittest.TestCase):
    def test_create_cloudfront_invalidation_calls_aws(self) -> None:
        payload = {"Invalidation": {"Id": "I1", "Status": "InProgress"}}
        with patch(
            "automation.cloudfront_invalidation.run_aws_json",
            return_value=payload,
        ) as mock_run:
            run = create_cloudfront_invalidation(_sample_plan(), "E1234567890")
        self.assertEqual(run.invalidation_id, "I1")
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        self.assertEqual(args[:3], ["cloudfront", "create-invalidation", "--distribution-id"])
        self.assertIn("/app/*", args)
        self.assertIn("/ot3-oe/*", args)

    def test_get_cloudfront_invalidation_calls_aws(self) -> None:
        payload = {"Invalidation": {"Id": "I1", "Status": "Completed"}}
        with patch(
            "automation.cloudfront_invalidation.run_aws_json",
            return_value=payload,
        ) as mock_run:
            run = get_cloudfront_invalidation("E123", "I1", profile="test-profile")
        self.assertEqual(run.status, "Completed")
        mock_run.assert_called_once_with(
            ["cloudfront", "get-invalidation", "--distribution-id", "E123", "--id", "I1"],
            profile="test-profile",
        )

    def test_wait_for_cloudfront_invalidation_polls_until_completed(self) -> None:
        run = CloudFrontInvalidationRun(
            invalidation_id="I1",
            distribution_id="E123",
            status="InProgress",
        )
        completed = CloudFrontInvalidationRun(
            invalidation_id="I1",
            distribution_id="E123",
            status="Completed",
        )
        with (
            patch("automation.cloudfront_invalidation.time.sleep"),
            patch(
                "automation.cloudfront_invalidation.get_cloudfront_invalidation",
                side_effect=[run, completed],
            ) as mock_get,
        ):
            result = wait_for_cloudfront_invalidation(
                run,
                profile="test-profile",
                timeout_seconds=60,
                poll_seconds=1,
            )
        self.assertEqual(result.status, "Completed")
        self.assertEqual(mock_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
