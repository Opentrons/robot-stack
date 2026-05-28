"""CloudFront invalidation helpers for robot-stack release builds.

Distribution hosts and infra stacks come from robot-stack-infra tfvars:

- release-ci prod: builds.opentrons.com
- ot3-ci prod: ot3-development.builds.opentrons.com
- ot2-ci prod: ot2.builds.opentrons.com
- ot2-internal-ci prod: ot2-development.builds.opentrons.com
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Literal, Optional

from rich.console import Console
from rich.prompt import Prompt

from automation.flex_urls import FLEX_EXTERNAL, FLEX_INTERNAL, FLEX_ROBOT_PREFIX
from automation.ot2_urls import OT2_EXTERNAL, OT2_INTERNAL, OT2_ROBOT_PREFIX

RobotPath = Literal["flex", "ot2"]
ReleaseChannel = Literal["internal", "external"]

ROBOT_STACK_PROD_PROFILE = "robotics_robot_stack_prod-admin"
APP_INVALIDATION_PREFIX = "/app/*"
DEFAULT_ROBOT_PATH: RobotPath = "flex"

console = Console(log_time=False)


@dataclass(frozen=True)
class CloudFrontReleaseTarget:
    """One prod CloudFront front door for a robot path and release channel."""

    label: str
    host: str
    infra_stack: str
    robot_prefix: str
    terraform_output: Optional[str] = None


@dataclass(frozen=True)
class CloudFrontInvalidationPlan:
    """Resolved CloudFront invalidation target for one release."""

    target: CloudFrontReleaseTarget
    distribution_id: Optional[str]
    distribution_url: str
    paths: tuple[str, ...]
    profile: str


def release_channel_from_tag(tag: str) -> ReleaseChannel:
    """Infer internal vs external channel from a release tag prefix."""
    if tag.startswith(("internal@", "ot3@")):
        return "internal"
    return "external"


def cloudfront_release_target(path: RobotPath, tag: str) -> CloudFrontReleaseTarget:
    """Return the CloudFront target for a tagged release build."""
    channel = release_channel_from_tag(tag)
    if path == "flex":
        if channel == "internal":
            return CloudFrontReleaseTarget(
                label="Flex internal",
                host=FLEX_INTERNAL.app_host,
                infra_stack="ot3-ci",
                robot_prefix=FLEX_ROBOT_PREFIX,
            )
        return CloudFrontReleaseTarget(
            label="Flex external",
            host=FLEX_EXTERNAL.app_host,
            infra_stack="release-ci",
            robot_prefix=FLEX_ROBOT_PREFIX,
            terraform_output="opentrons_app_builds_cloudfront_distribution_id",
        )

    if channel == "internal":
        return CloudFrontReleaseTarget(
            label="OT-2 internal",
            host=OT2_INTERNAL.app_host,
            infra_stack="ot2-internal-ci",
            robot_prefix=OT2_ROBOT_PREFIX,
        )
    return CloudFrontReleaseTarget(
        label="OT-2 external",
        host=OT2_EXTERNAL.app_host,
        infra_stack="ot2-ci",
        robot_prefix=OT2_ROBOT_PREFIX,
    )


def invalidation_paths(robot_prefix: str) -> tuple[str, ...]:
    """Return CloudFront path patterns to invalidate after a release build."""
    return (APP_INVALIDATION_PREFIX, f"/{robot_prefix}/*")


def distribution_url(host: str) -> str:
    """Return the HTTPS URL served by a CloudFront distribution alias."""
    return f"https://{host}/"


def list_distribution_ids_by_alias(profile: str) -> dict[str, str]:
    """Map CloudFront alternate domain names to distribution IDs."""
    result = subprocess.run(
        ["aws", "cloudfront", "list-distributions", "--profile", profile, "--output", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return {}

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    items = payload.get("DistributionList", {}).get("Items") or []
    mapping: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        distribution_id = item.get("Id")
        if not isinstance(distribution_id, str):
            continue
        aliases = item.get("Aliases", {}).get("Items") or []
        for alias in aliases:
            if isinstance(alias, str):
                mapping[alias] = distribution_id
    return mapping


def resolve_distribution_id(host: str, profile: str = ROBOT_STACK_PROD_PROFILE) -> Optional[str]:
    """Look up a CloudFront distribution ID by its alternate domain name."""
    return list_distribution_ids_by_alias(profile).get(host)


def build_invalidation_plan(
    path: RobotPath,
    tag: str,
    *,
    profile: str = ROBOT_STACK_PROD_PROFILE,
    lookup_distribution_id: bool = True,
) -> CloudFrontInvalidationPlan:
    """Resolve the CloudFront distribution and paths for a release tag."""
    target = cloudfront_release_target(path, tag)
    paths = invalidation_paths(target.robot_prefix)
    distribution_id = resolve_distribution_id(target.host, profile) if lookup_distribution_id else None
    return CloudFrontInvalidationPlan(
        target=target,
        distribution_id=distribution_id,
        distribution_url=distribution_url(target.host),
        paths=paths,
        profile=profile,
    )


def format_create_invalidation_command(plan: CloudFrontInvalidationPlan, distribution_id: str) -> str:
    """Return a copy-paste aws cloudfront create-invalidation command."""
    path_args = " ".join(plan.paths)
    return f"aws cloudfront create-invalidation --profile {plan.profile} --distribution-id {distribution_id} --paths {path_args}"


def format_cloudfront_invalidation_report(plan: CloudFrontInvalidationPlan) -> str:
    """Build human-readable CloudFront invalidation guidance for a release."""
    target = plan.target
    lines = [
        f"# {target.label} release ({target.host} via {target.infra_stack} prod)",
        f"url: {plan.distribution_url}",
    ]

    if plan.distribution_id is None:
        lookup_command = (
            f"aws cloudfront list-distributions --profile {plan.profile} "
            f"--query \"DistributionList.Items[?Aliases.Items[?@=='{target.host}']].Id\" "
            "--output text"
        )
        lines.extend(
            [
                "distribution_id: not resolved",
                f"# Lookup: {lookup_command}",
            ]
        )
        if target.terraform_output is not None:
            lines.append(f"# release-ci prod terraform output alternative: terraform output -raw {target.terraform_output}")
        placeholder_id = f"<distribution-id-for-{target.host}>"
        lines.append(format_create_invalidation_command(plan, placeholder_id))
        return "\n".join(lines)

    lines.extend(
        [
            f"distribution_id: {plan.distribution_id}",
            f"paths: {' '.join(plan.paths)}",
            format_create_invalidation_command(plan, plan.distribution_id),
        ]
    )
    return "\n".join(lines)


def detect_path_from_tag(tag: str) -> RobotPath:
    """Infer robot path from a tag prefix, defaulting to Flex when ambiguous."""
    if tag.startswith("internal@"):
        return "ot2"
    if tag.startswith("ot3@"):
        return "flex"
    return DEFAULT_ROBOT_PATH


def normalize_release_tag(path: RobotPath, tag: str, release_type: Optional[str]) -> str:
    """Ensure the tag includes the expected channel prefix."""
    stripped = tag.strip()
    if stripped.startswith(("internal@", "ot3@", "v")):
        return stripped

    if release_type == "internal":
        prefix = "ot3@" if path == "flex" else "internal@"
        return f"{prefix}{stripped.lstrip('v')}"
    if release_type == "external":
        return stripped if stripped.startswith("v") else f"v{stripped.lstrip('v')}"
    raise ValueError(f"Tag {tag!r} has no prefix; pass --release-type internal or external")


def resolve_release_tag(
    tag: Optional[str],
    *,
    path: Optional[RobotPath] = None,
    release_type: Optional[str] = None,
    non_interactive: bool = False,
) -> tuple[RobotPath, str]:
    """Resolve robot path and normalized tag from CLI args or prompts."""
    if tag is None:
        if non_interactive:
            raise ValueError("--tag is required with --non-interactive")
        resolved_tag = Prompt.ask("Release tag")
    else:
        resolved_tag = tag

    path_name = path if path is not None else detect_path_from_tag(resolved_tag)

    if not resolved_tag.startswith(("internal@", "ot3@", "v")):
        channel = release_type
        if channel is None:
            if non_interactive:
                raise ValueError("--release-type is required with --non-interactive when --tag has no channel prefix")
            channel = Prompt.ask("Release type", choices=["internal", "external"])
        if channel not in {"internal", "external"}:
            raise ValueError("Release type must be internal or external")
        resolved_tag = normalize_release_tag(path_name, resolved_tag, channel)

    return path_name, resolved_tag


def print_cloudfront_invalidation(
    path: RobotPath,
    tag: str,
    *,
    profile: str = ROBOT_STACK_PROD_PROFILE,
    lookup_distribution_id: bool = True,
    output: Console | None = None,
) -> CloudFrontInvalidationPlan:
    """Print CloudFront mapping and a copy-paste invalidation command."""
    out = output or console
    plan = build_invalidation_plan(
        path,
        tag,
        profile=profile,
        lookup_distribution_id=lookup_distribution_id,
    )
    report = format_cloudfront_invalidation_report(plan)
    out.print()
    out.print("[bold green]CloudFront invalidation[/]")
    out.print(report, soft_wrap=False)
    return plan
