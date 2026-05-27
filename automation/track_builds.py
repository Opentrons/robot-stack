"""Find GitHub Actions build jobs for an OT-2 or Flex release tag.

After pushing a monorepo tag, this script locates the app CI run, the cross-repo
kickoff workflow, and the robot OS build in buildroot (OT-2) or oe-core (Flex).
It prints Rich output with clickable links plus a Slack-ready copy block.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console(log_time=False)

RobotPath = Literal["flex", "ot2"]
RunStatus = Literal["found", "missing", "pending"]

DEFAULT_ROBOT_PATH: RobotPath = "flex"

APP_WORKFLOW = "App test, build, and deploy"

APP_KEY_JOB_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^Deploy built app artifacts to S3$"),
    re.compile(r"^Build .+ desktop app on .+$"),
)

DISPATCH_KEY_JOB_PATTERNS: tuple[re.Pattern[str], ...] = (re.compile(r"^Start (an OT-2|a Flex) build for a branch/tag push$"),)

ROBOT_KEY_JOB_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(Decide refs to build|deciding refs to build)$"),
    re.compile(r"^(initialize build infrastructure|request ephemeral runner)$"),
    re.compile(r"^Building .+ images on stage-prod$"),
)


@dataclass(frozen=True)
class PathConfig:
    """Repos and workflow names for one robot release path."""

    label: str
    monorepo: str
    dispatch_workflow: str
    robot_repo: str
    robot_workflow: str
    robot_label: str
    internal_tag_prefix: str
    external_tag_prefix: str


PATHS: dict[RobotPath, PathConfig] = {
    "ot2": PathConfig(
        label="OT-2",
        monorepo="Opentrons/opentrons-ot2",
        dispatch_workflow="Start OT-2 build",
        robot_repo="Opentrons/buildroot",
        robot_workflow="Build OT2 image on github workflows",
        robot_label="Robot OS (buildroot)",
        internal_tag_prefix="internal@",
        external_tag_prefix="v",
    ),
    "flex": PathConfig(
        label="Flex",
        monorepo="Opentrons/opentrons",
        dispatch_workflow="Start Flex build",
        robot_repo="Opentrons/oe-core",
        robot_workflow="Build Flex image on github workflows",
        robot_label="Robot OS (oe-core)",
        internal_tag_prefix="ot3@",
        external_tag_prefix="v",
    ),
}


@dataclass(frozen=True)
class WorkflowRun:
    """One GitHub Actions workflow run."""

    database_id: int
    url: str
    status: str
    conclusion: Optional[str]
    display_title: str
    created_at: str
    workflow_name: str
    head_branch: str
    event: str


@dataclass(frozen=True)
class WorkflowJob:
    """One job inside a workflow run."""

    name: str
    url: str
    status: str
    conclusion: Optional[str]


@dataclass(frozen=True)
class BuildStage:
    """A workflow or job row to show in the report."""

    stage: str
    description: str
    repo: str
    status: RunStatus
    run: Optional[WorkflowRun]
    job: Optional[WorkflowJob]


def gh_json(args: Sequence[str]) -> Any:
    """Run a gh subcommand and parse JSON stdout."""
    result = subprocess.run(
        ["gh", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(stderr or f"gh {' '.join(args)} failed with exit code {result.returncode}")
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def tag_exists(repo: str, tag: str) -> bool:
    """Return True when an annotated or lightweight tag ref exists on GitHub."""
    encoded = urllib.parse.quote(tag, safe="")
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/ref/tags/{encoded}"],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def detect_path_from_tag(tag: str) -> RobotPath:
    """Infer robot path from a tag prefix, defaulting to Flex when ambiguous."""
    if tag.startswith("internal@"):
        return "ot2"
    if tag.startswith("ot3@"):
        return "flex"
    return DEFAULT_ROBOT_PATH


def track_builds_invocation(path: RobotPath, tag: str, *, wait: bool = True) -> str:
    """Return a copy-paste command to track CI for a release tag."""
    command = f"just track-builds --path {path} --tag {tag}"
    if wait:
        command += " --wait"
    return command


def normalize_tag(path: PathConfig, tag: str, release_type: Optional[str]) -> str:
    """Ensure the tag includes the expected channel prefix."""
    stripped = tag.strip()
    if stripped.startswith(("internal@", "ot3@", "v")):
        return stripped

    if release_type == "internal":
        return f"{path.internal_tag_prefix}{stripped.lstrip('v')}"
    if release_type == "external":
        return f"{path.external_tag_prefix}{stripped.lstrip('v')}"
    raise ValueError(f"Tag {tag!r} has no prefix; pass --release-type internal or external")


def parse_created_at(value: str) -> datetime:
    """Parse GitHub Actions createdAt timestamps."""
    if value.endswith("Z"):
        value = f"{value[:-1]}+00:00"
    return datetime.fromisoformat(value)


def workflow_run_from_dict(data: dict[str, Any]) -> WorkflowRun:
    """Build a WorkflowRun from gh run list JSON."""
    return WorkflowRun(
        database_id=int(data["databaseId"]),
        url=str(data["url"]),
        status=str(data["status"]),
        conclusion=data.get("conclusion"),
        display_title=str(data.get("displayTitle") or ""),
        created_at=str(data["createdAt"]),
        workflow_name=str(data.get("workflowName") or ""),
        head_branch=str(data.get("headBranch") or ""),
        event=str(data.get("event") or ""),
    )


def list_workflow_runs(repo: str, workflow: str, limit: int) -> list[WorkflowRun]:
    """Return recent runs for one workflow."""
    data = gh_json(
        [
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            workflow,
            "--limit",
            str(limit),
            "--json",
            "databaseId,url,status,conclusion,displayTitle,createdAt,workflowName,headBranch,event",
        ]
    )
    if not isinstance(data, list):
        return []
    return [workflow_run_from_dict(item) for item in data]


def workflow_id_for(repo: str, workflow: str) -> Optional[int]:
    """Resolve a workflow display name to its numeric GitHub Actions ID."""
    owner, name = repo.split("/", 1)
    data = gh_json(["api", f"repos/{owner}/{name}/actions/workflows", "--jq", ".workflows"])
    if not isinstance(data, list):
        return None
    for item in data:
        if not isinstance(item, dict):
            continue
        if item.get("name") == workflow:
            workflow_id = item.get("id")
            if isinstance(workflow_id, int):
                return workflow_id
    return None


def paginated_workflow_runs(
    repo: str,
    workflow: str,
    *,
    per_page: int = 100,
    max_pages: int = 5,
) -> list[WorkflowRun]:
    """Return workflow runs across multiple GitHub API pages."""
    owner, name = repo.split("/", 1)
    workflow_id = workflow_id_for(repo, workflow)
    if workflow_id is None:
        return []

    runs: list[WorkflowRun] = []
    for page in range(1, max_pages + 1):
        data = gh_json(
            [
                "api",
                f"repos/{owner}/{name}/actions/workflows/{workflow_id}/runs?per_page={per_page}&page={page}",
            ]
        )
        if not isinstance(data, dict):
            break
        workflow_runs = data.get("workflow_runs")
        if not isinstance(workflow_runs, list) or not workflow_runs:
            break
        for item in workflow_runs:
            if not isinstance(item, dict):
                continue
            runs.append(
                WorkflowRun(
                    database_id=int(item["id"]),
                    url=str(item["html_url"]),
                    status=str(item["status"]),
                    conclusion=item.get("conclusion"),
                    display_title=str(item.get("display_title") or item.get("name") or ""),
                    created_at=str(item["created_at"]),
                    workflow_name=str(item.get("name") or workflow),
                    head_branch=str(item.get("head_branch") or ""),
                    event=str(item.get("event") or ""),
                )
            )
        if len(workflow_runs) < per_page:
            break
    return runs


def find_monorepo_tag_run(runs: Sequence[WorkflowRun], tag: str) -> Optional[WorkflowRun]:
    """Find the tag-push workflow run on the monorepo."""
    matches = [run for run in runs if run.head_branch == tag and run.event == "push"]
    if not matches:
        return None
    return max(matches, key=lambda run: parse_created_at(run.created_at))


def find_robot_tag_run(
    runs: Sequence[WorkflowRun],
    tag: str,
    not_before: Optional[datetime] = None,
) -> Optional[WorkflowRun]:
    """Find the dispatched robot OS build for a monorepo tag."""
    needle = f"refs/tags/{tag}"
    matches = [run for run in runs if needle in run.display_title and run.event == "workflow_dispatch"]
    if not_before is not None:
        matches = [run for run in matches if parse_created_at(run.created_at) >= not_before]
    if not matches:
        return None
    return min(matches, key=lambda run: parse_created_at(run.created_at))


def list_run_jobs(repo: str, run_id: int) -> list[WorkflowJob]:
    """Return all jobs for one workflow run."""
    data = gh_json(["run", "view", str(run_id), "--repo", repo, "--json", "jobs"])
    if not isinstance(data, dict):
        return []
    jobs_raw = data.get("jobs")
    if not isinstance(jobs_raw, list):
        return []
    jobs: list[WorkflowJob] = []
    for item in jobs_raw:
        if not isinstance(item, dict):
            continue
        jobs.append(
            WorkflowJob(
                name=str(item.get("name") or ""),
                url=str(item.get("url") or ""),
                status=str(item.get("status") or ""),
                conclusion=item.get("conclusion"),
            )
        )
    return jobs


def pick_key_jobs(jobs: Sequence[WorkflowJob], patterns: Sequence[re.Pattern[str]]) -> list[WorkflowJob]:
    """Return non-skipped jobs whose names match any pattern."""
    selected: list[WorkflowJob] = []
    for job in jobs:
        if job.conclusion == "skipped":
            continue
        if any(pattern.search(job.name) for pattern in patterns):
            selected.append(job)
    return selected


def status_label(run: Optional[WorkflowRun], job: Optional[WorkflowJob] = None) -> tuple[RunStatus, str]:
    """Map GitHub status fields to a display label and lookup state."""
    subject = job if job is not None else run
    if subject is None:
        return "missing", "not found"

    status = subject.status
    conclusion = subject.conclusion

    if status in {"queued", "waiting", "requested", "pending", "in_progress"}:
        return "pending", "in progress"
    if conclusion == "success":
        return "found", "success"
    if conclusion == "failure":
        return "found", "failure"
    if conclusion == "cancelled":
        return "found", "cancelled"
    if conclusion == "skipped":
        return "found", "skipped"
    if status == "completed":
        return "found", conclusion or "completed"
    return "pending", status


def status_style(label: str) -> str:
    """Return a Rich color for a status label."""
    normalized = label.lower()
    if normalized in {"success"}:
        return "green"
    if normalized in {"failure"}:
        return "red"
    if normalized in {"cancelled", "skipped"}:
        return "yellow"
    if normalized in {"in progress", "queued", "waiting", "requested", "pending"}:
        return "cyan"
    if normalized in {"not found"}:
        return "dim"
    return "white"


def collect_build_stages(
    path: PathConfig,
    tag: str,
    run_limit: int,
    robot_max_pages: int,
) -> list[BuildStage]:
    """Resolve app, kickoff, and robot OS workflow runs for a tag."""
    app_runs = list_workflow_runs(path.monorepo, APP_WORKFLOW, run_limit)
    dispatch_runs = list_workflow_runs(path.monorepo, path.dispatch_workflow, run_limit)
    robot_runs = paginated_workflow_runs(
        path.robot_repo,
        path.robot_workflow,
        max_pages=robot_max_pages,
    )

    app_run = find_monorepo_tag_run(app_runs, tag)
    dispatch_run = find_monorepo_tag_run(dispatch_runs, tag)
    dispatch_time = parse_created_at(dispatch_run.created_at) if dispatch_run else None
    robot_run = find_robot_tag_run(robot_runs, tag, not_before=dispatch_time)

    stages: list[BuildStage] = [
        BuildStage(
            stage="App",
            description=f"{path.label} app CI ({APP_WORKFLOW})",
            repo=path.monorepo,
            status="missing",
            run=app_run,
            job=None,
        ),
        BuildStage(
            stage="Kickoff",
            description=f"Cross-repo dispatch ({path.dispatch_workflow})",
            repo=path.monorepo,
            status="missing",
            run=dispatch_run,
            job=None,
        ),
        BuildStage(
            stage="Robot OS",
            description=f"{path.robot_label} ({path.robot_workflow})",
            repo=path.robot_repo,
            status="missing",
            run=robot_run,
            job=None,
        ),
    ]

    resolved: list[BuildStage] = []
    for stage in stages:
        lookup, _ = status_label(stage.run, stage.job)
        resolved.append(
            BuildStage(
                stage=stage.stage,
                description=stage.description,
                repo=stage.repo,
                status=lookup if stage.run is not None else "missing",
                run=stage.run,
                job=stage.job,
            )
        )

    extra_jobs: list[BuildStage] = []
    if app_run is not None:
        for job in pick_key_jobs(list_run_jobs(path.monorepo, app_run.database_id), APP_KEY_JOB_PATTERNS):
            lookup, _ = status_label(app_run, job)
            extra_jobs.append(
                BuildStage(
                    stage="App job",
                    description=job.name,
                    repo=path.monorepo,
                    status=lookup,
                    run=app_run,
                    job=job,
                )
            )

    if dispatch_run is not None:
        for job in pick_key_jobs(
            list_run_jobs(path.monorepo, dispatch_run.database_id),
            DISPATCH_KEY_JOB_PATTERNS,
        ):
            lookup, _ = status_label(dispatch_run, job)
            extra_jobs.append(
                BuildStage(
                    stage="Kickoff job",
                    description=job.name,
                    repo=path.monorepo,
                    status=lookup,
                    run=dispatch_run,
                    job=job,
                )
            )

    if robot_run is not None:
        for job in pick_key_jobs(
            list_run_jobs(path.robot_repo, robot_run.database_id),
            ROBOT_KEY_JOB_PATTERNS,
        ):
            lookup, _ = status_label(robot_run, job)
            extra_jobs.append(
                BuildStage(
                    stage="Robot OS job",
                    description=job.name,
                    repo=path.robot_repo,
                    status=lookup,
                    run=robot_run,
                    job=job,
                )
            )

    return resolved + extra_jobs


def stage_url(stage: BuildStage) -> Optional[str]:
    """Prefer a job URL when present, otherwise the workflow run URL."""
    if stage.job is not None and stage.job.url:
        return stage.job.url
    if stage.run is not None:
        return stage.run.url
    return None


def render_report(path: PathConfig, tag: str, stages: Sequence[BuildStage]) -> None:
    """Print Rich tables and a Slack-ready copy block."""
    summary = Table(show_header=False, box=None, padding=(0, 1))
    summary.add_row("Robot path", f"[bold]{path.label}[/]")
    summary.add_row("Tag", f"[bold cyan]{tag}[/]")
    summary.add_row("Monorepo", path.monorepo)
    summary.add_row("Robot OS repo", path.robot_repo)

    console.print()
    console.print(Panel(summary, title="Release build tracker", border_style="cyan"))

    table = Table(title="GitHub Actions runs", show_lines=True)
    table.add_column("Stage", style="bold")
    table.add_column("Description")
    table.add_column("Status")
    table.add_column("Link")

    for stage in stages:
        _, label = status_label(stage.run, stage.job)
        url = stage_url(stage)
        link_cell: str | Text
        if url:
            link_cell = Text.from_markup(f"[link={url}]{url}[/link]")
        else:
            link_cell = Text("not found yet", style="dim")

        table.add_row(
            stage.stage,
            stage.description,
            Text(label, style=status_style(label)),
            link_cell,
        )

    console.print()
    console.print(table)

    slack_lines = [
        f"{path.label} release `{tag}`",
        "",
    ]
    for stage in stages:
        if stage.stage.endswith(" job"):
            continue
        url = stage_url(stage)
        if url is None:
            slack_lines.append(f"- {stage.stage}: not found yet")
        else:
            _, label = status_label(stage.run, stage.job)
            slack_lines.append(f"- {stage.stage} ({label}): {url}")

    slack_lines.extend(["", "Key jobs:"])
    for stage in stages:
        if not stage.stage.endswith(" job"):
            continue
        url = stage_url(stage)
        if url is None:
            continue
        _, label = status_label(stage.run, stage.job)
        slack_lines.append(f"- {stage.description} ({label}): {url}")

    slack_block = "\n".join(slack_lines)
    console.print()
    console.print("[bold green]Slack copy block[/]")
    console.print(slack_block, soft_wrap=False)


def wait_for_stages(
    path: PathConfig,
    tag: str,
    run_limit: int,
    robot_max_pages: int,
    timeout_seconds: int,
    poll_seconds: int,
) -> list[BuildStage]:
    """Poll GitHub until the main workflow runs appear or timeout."""
    deadline = time.time() + timeout_seconds
    while True:
        stages = collect_build_stages(path, tag, run_limit, robot_max_pages)
        top_level = [stage for stage in stages if not stage.stage.endswith(" job")]
        if all(stage.run is not None for stage in top_level):
            return stages
        if time.time() >= deadline:
            return stages
        missing = [stage.stage for stage in top_level if stage.run is None]
        console.print(f"[yellow]Waiting for {', '.join(missing)} workflow runs...[/] (retry in {poll_seconds}s)")
        time.sleep(poll_seconds)


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Find GitHub Actions build jobs for an OT-2 or Flex release tag.",
    )
    parser.add_argument(
        "--path",
        choices=["flex", "ot2"],
        default=None,
        help=f"Robot release path (default: infer from tag, else {DEFAULT_ROBOT_PATH}).",
    )
    parser.add_argument(
        "--tag",
        help="Release tag, e.g. internal@26.5.2701, v8.5.0, or ot3@8.5.0.",
    )
    parser.add_argument(
        "--release-type",
        choices=["internal", "external"],
        help="Add the channel prefix when --tag is given without one.",
    )
    parser.add_argument(
        "--run-limit",
        type=int,
        default=40,
        help="How many recent monorepo workflow runs to scan (default: 40).",
    )
    parser.add_argument(
        "--robot-max-pages",
        type=int,
        default=5,
        help="How many 100-run pages to scan in the robot OS repo (default: 5).",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Poll until app, kickoff, and robot OS workflow runs appear.",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=900,
        help="Maximum seconds to wait with --wait (default: 900).",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=15,
        help="Seconds between polls with --wait (default: 15).",
    )
    return parser


def resolve_inputs(args: argparse.Namespace) -> tuple[RobotPath, str]:
    """Prompt for missing path or tag values and normalize the tag."""
    tag: Optional[str] = args.tag

    if tag is None:
        tag = Prompt.ask("Release tag")

    assert tag is not None

    path_name: RobotPath
    if args.path is not None:
        path_name = args.path
    else:
        path_name = detect_path_from_tag(tag)

    path = PATHS[path_name]

    if not tag.startswith(("internal@", "ot3@", "v")):
        if args.release_type is None:
            release_type = Prompt.ask("Release type", choices=["internal", "external"])
        else:
            release_type = args.release_type
        tag = normalize_tag(path, tag, release_type)

    return path_name, tag


def main() -> None:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        path_name, tag = resolve_inputs(args)
    except ValueError as err:
        console.print(f"[red]{err}[/]")
        sys.exit(1)

    path = PATHS[path_name]

    if not tag_exists(path.monorepo, tag):
        console.print(
            f"[yellow]Warning:[/] tag [bold]{tag}[/] was not found on [bold]{path.monorepo}[/]. "
            "Continuing anyway in case the tag was just pushed."
        )

    try:
        if args.wait:
            stages = wait_for_stages(
                path,
                tag,
                args.run_limit,
                args.robot_max_pages,
                args.wait_timeout,
                args.poll_seconds,
            )
        else:
            stages = collect_build_stages(path, tag, args.run_limit, args.robot_max_pages)
    except RuntimeError as err:
        console.print(f"[red]{err}[/]")
        sys.exit(1)

    render_report(path, tag, stages)

    top_level = [stage for stage in stages if not stage.stage.endswith(" job")]
    if any(stage.run is None for stage in top_level):
        console.print(
            "\n[dim]Some workflow runs were not found. "
            "Try again with --wait after pushing the tag, or increase --run-limit for older releases.[/]"
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
