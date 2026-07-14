"""Structured release plans for review and careful apply.

Plans are human-readable YAML files named after the app monorepo tag. Generate with
``just go --write-plan`` and apply after review with ``just apply-release-plan``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, cast

import yaml
from rich.console import Console
from rich.panel import Panel

from automation.release_branch_config import ReleaseBranchConfig

PLAN_SCHEMA_VERSION = 1
DEFAULT_PLAN_DIR = Path(".build/plans")

TagStepAction = Literal[
    "checkout",
    "verify_remote_branch",
    "create_tag",
    "verify_tag_log",
    "push_tags",
]

console = Console(log_time=False)


@dataclass(frozen=True)
class TagStep:
    """One git operation in a repo release plan."""

    action: TagStepAction
    branch: Optional[str] = None
    expected_commit: Optional[str] = None
    tag: Optional[str] = None
    tags: Tuple[str, ...] = ()
    message: Optional[str] = None
    count: int = 10


@dataclass(frozen=True)
class FollowUpCommand:
    """Advisory command to run before or after tag pushes."""

    phase: Literal["pre_apply", "post_apply"]
    command: str
    description: str
    required_before_app_push: bool = False


@dataclass(frozen=True)
class RepoReleasePlan:
    """Tag plan for one repository in push order."""

    name: str
    role: Literal["stack", "app"]
    local_path: str
    default_branch: str
    branch: str
    needs_tag: bool
    reason: str
    latest_tag: Optional[str]
    next_tags: Tuple[str, ...]
    head_commit: str
    existing_firmware_version_tag: Optional[str] = None
    steps: Tuple[TagStep, ...] = ()


@dataclass(frozen=True)
class ReleasePlan:
    """Full multi-repo release plan for one app tag."""

    schema_version: int
    generated_at: str
    path: str
    path_label: str
    release_type: str
    stability: str
    version: str
    app_tag: str
    release_version: str
    app_branch_override: Optional[str]
    stack_branch_overrides: Dict[str, str]
    push_order: Tuple[str, ...]
    repos: Tuple[RepoReleasePlan, ...]
    follow_ups: Tuple[FollowUpCommand, ...]
    head_commit_checksum: Optional[str] = None
    plan_path: Optional[str] = None

    def repos_needing_tags(self) -> Tuple[RepoReleasePlan, ...]:
        """Return repos that will create and push new tags."""
        return tuple(repo for repo in self.repos if repo.needs_tag)


@dataclass(frozen=True)
class RepoCommitDrift:
    """One repo whose remote branch tip no longer matches the plan."""

    name: str
    branch: str
    planned_commit: str
    remote_commit: str


@dataclass(frozen=True)
class PlanStalenessReport:
    """Whether a plan's recorded branch tips still match origin."""

    is_stale: bool
    planned_checksum: Optional[str]
    current_checksum: Optional[str]
    drifts: Tuple[RepoCommitDrift, ...]
    missing_checksum: bool = False
    detail: str = ""


RepoApplyStatus = Literal["skipped", "applied", "pending", "drifted", "conflict", "error"]


@dataclass(frozen=True)
class RepoApplyState:
    """Apply readiness for one repository in a release plan."""

    repo_name: str
    status: RepoApplyStatus
    detail: str
    remote_commit: Optional[str] = None


@dataclass(frozen=True)
class PlanApplyReadiness:
    """Whether a plan can be applied, resumed, or must be regenerated."""

    can_apply: bool
    is_partial: bool
    repo_states: Tuple[RepoApplyState, ...]
    pending_repos: Tuple[str, ...]
    applied_repos: Tuple[str, ...]
    blocked_repos: Tuple[str, ...]
    detail: str


def remote_tag_commit(repo_dir: Path, tag: str) -> Optional[str]:
    """Return the commit a tag points to on origin, if it exists."""
    for ref in (f"refs/tags/{tag}^{{}}", f"refs/tags/{tag}"):
        result = subprocess.run(
            ["git", "ls-remote", "--tags", "origin", ref],
            cwd=repo_dir,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            continue
        line = result.stdout.strip().splitlines()
        if not line:
            continue
        commit, _ref = line[0].split("\t", maxsplit=1)
        return commit
    return None


def _tags_applied_at_commit(repo: RepoReleasePlan, repo_dir: Path) -> tuple[bool, str]:
    """Return whether all planned tags exist on origin at the planned commit."""
    if not repo.next_tags:
        return False, "No planned tags"

    for tag in repo.next_tags:
        tag_commit = remote_tag_commit(repo_dir, tag)
        if tag_commit is None:
            return False, f"Tag not on origin: {tag}"
        if tag_commit != repo.head_commit:
            return (
                False,
                f"Tag {tag} on origin points to {tag_commit[:12]}, expected {repo.head_commit[:12]}",
            )
    return True, f"Tags {', '.join(repo.next_tags)} already on origin at planned commit"


def assess_repo_apply_state(repo: RepoReleasePlan, workspace_root: Path) -> RepoApplyState:
    """Classify one repo as pending, already applied, drifted, or conflicting."""
    if not repo.needs_tag:
        return RepoApplyState(
            repo_name=repo.name,
            status="skipped",
            detail=repo.reason,
        )

    repo_dir = (workspace_root / repo.local_path).resolve()
    if not repo_dir.is_dir() or not (repo_dir / ".git").exists():
        return RepoApplyState(
            repo_name=repo.name,
            status="error",
            detail=f"Missing git clone: {repo_dir}",
        )

    try:
        remote_commit = fetch_remote_branch_head(repo, workspace_root)
    except RuntimeError as err:
        return RepoApplyState(
            repo_name=repo.name,
            status="error",
            detail=str(err),
            remote_commit=None,
        )

    applied, applied_detail = _tags_applied_at_commit(repo, repo_dir)
    if applied:
        return RepoApplyState(
            repo_name=repo.name,
            status="applied",
            detail=applied_detail,
            remote_commit=remote_commit,
        )

    existing_tags = [tag for tag in repo.next_tags if remote_tag_commit(repo_dir, tag) is not None]
    if existing_tags:
        return RepoApplyState(
            repo_name=repo.name,
            status="conflict",
            detail=(
                f"Partial or mismatched tags on origin: {', '.join(existing_tags)}. "
                "Resolve manually or delete incorrect tags before retrying."
            ),
            remote_commit=remote_commit,
        )

    if remote_commit != repo.head_commit:
        return RepoApplyState(
            repo_name=repo.name,
            status="drifted",
            detail=(
                f"origin/{repo.branch} is {remote_commit[:12]}, "
                f"plan expected {repo.head_commit[:12]}. Regenerate with `just go-plan`."
            ),
            remote_commit=remote_commit,
        )

    return RepoApplyState(
        repo_name=repo.name,
        status="pending",
        detail=f"Ready to tag on origin/{repo.branch} at {repo.head_commit[:12]}",
        remote_commit=remote_commit,
    )


def assess_plan_apply(plan: ReleasePlan, workspace_root: Path) -> PlanApplyReadiness:
    """Determine whether a plan can run, resume after partial apply, or must be regenerated."""
    if plan.head_commit_checksum is None:
        return PlanApplyReadiness(
            can_apply=False,
            is_partial=False,
            repo_states=(),
            pending_repos=(),
            applied_repos=(),
            blocked_repos=(),
            detail="Plan has no head_commit_checksum. Regenerate with `just go-plan`.",
        )

    repo_states = tuple(assess_repo_apply_state(repo, workspace_root) for repo in plan.repos)
    pending = tuple(state.repo_name for state in repo_states if state.status == "pending")
    applied = tuple(state.repo_name for state in repo_states if state.status == "applied")
    blocked = tuple(state.repo_name for state in repo_states if state.status in {"drifted", "conflict", "error"})

    if blocked:
        blocked_details = [f"{state.repo_name}: {state.detail}" for state in repo_states if state.repo_name in blocked]
        if applied and any(state.status == "drifted" for state in repo_states):
            detail = (
                "Plan is partially applied, but a remaining repo drifted:\n"
                + "\n".join(blocked_details)
                + "\n\nRegenerate with `just go-plan` using the same release flags. "
                "Already-applied repos should report needs_tag=false in the new plan."
            )
        else:
            detail = "Plan cannot be applied:\n" + "\n".join(blocked_details)
        return PlanApplyReadiness(
            can_apply=False,
            is_partial=bool(applied),
            repo_states=repo_states,
            pending_repos=pending,
            applied_repos=applied,
            blocked_repos=blocked,
            detail=detail,
        )

    if not pending and applied:
        return PlanApplyReadiness(
            can_apply=True,
            is_partial=False,
            repo_states=repo_states,
            pending_repos=pending,
            applied_repos=applied,
            blocked_repos=blocked,
            detail="All planned tags are already on origin at the planned commits.",
        )

    if applied:
        detail = "Resuming partial apply. Already applied: " + ", ".join(applied) + ". Pending: " + ", ".join(pending) + "."
    else:
        detail = "Plan is ready to apply."

    return PlanApplyReadiness(
        can_apply=True,
        is_partial=bool(applied),
        repo_states=repo_states,
        pending_repos=pending,
        applied_repos=applied,
        blocked_repos=blocked,
        detail=detail,
    )


def print_apply_readiness_report(readiness: PlanApplyReadiness) -> None:
    """Print per-repo apply state and overall readiness."""
    from rich.table import Table

    table = Table(title="Release plan apply readiness", show_lines=True)
    table.add_column("Repo", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    for state in readiness.repo_states:
        if state.status == "skipped":
            continue
        color = {
            "applied": "green",
            "pending": "cyan",
            "drifted": "red",
            "conflict": "red",
            "error": "red",
        }.get(state.status, "white")
        table.add_row(state.repo_name, f"[{color}]{state.status}[/]", state.detail)

    console.print(table)
    if readiness.can_apply:
        console.print(f"[green]{readiness.detail}[/]")
    else:
        console.print()
        console.print(
            Panel(
                readiness.detail,
                title="Cannot apply plan",
                border_style="red",
                padding=(1, 2),
            )
        )


def repos_in_push_order(plan: ReleasePlan) -> Tuple[RepoReleasePlan, ...]:
    """Return repo plan entries ordered for tag push."""
    ordered: List[RepoReleasePlan] = []
    for repo_name in plan.push_order:
        ordered.append(next(repo for repo in plan.repos if repo.name == repo_name))
    return tuple(ordered)


def integrity_payload(plan: ReleasePlan) -> Dict[str, Any]:
    """Return the canonical payload hashed into ``head_commit_checksum``."""
    return {
        "push_order": list(plan.push_order),
        "repos": [
            {
                "name": repo.name,
                "branch": repo.branch,
                "head_commit": repo.head_commit,
            }
            for repo in repos_in_push_order(plan)
        ],
    }


def compute_head_commit_checksum(plan: ReleasePlan) -> str:
    """Return a stable checksum for all planned branch tips."""
    canonical = json.dumps(integrity_payload(plan), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def with_plan_integrity(plan: ReleasePlan) -> ReleasePlan:
    """Return a plan annotated with a head-commit checksum."""
    return replace(plan, head_commit_checksum=compute_head_commit_checksum(plan))


def plan_filename(app_tag: str) -> str:
    """Return the default plan filename for an app monorepo tag."""
    return f"{app_tag}.plan.yaml"


def default_plan_path(app_tag: str, plan_dir: Path = DEFAULT_PLAN_DIR) -> Path:
    """Return the default output path for a release plan."""
    return plan_dir / plan_filename(app_tag)


def _step_to_dict(step: TagStep) -> Dict[str, Any]:
    """Serialize one tag step, omitting empty optional fields."""
    payload: Dict[str, Any] = {"action": step.action}
    if step.branch is not None:
        payload["branch"] = step.branch
    if step.expected_commit is not None:
        payload["expected_commit"] = step.expected_commit
    if step.tag is not None:
        payload["tag"] = step.tag
    if step.tags:
        payload["tags"] = list(step.tags)
    if step.message is not None:
        payload["message"] = step.message
    if step.action == "verify_tag_log":
        payload["count"] = step.count
    return payload


def _dict_to_step(raw: Dict[str, Any]) -> TagStep:
    """Deserialize one tag step from YAML."""
    action = cast(TagStepAction, raw["action"])
    tags = tuple(raw.get("tags", []))
    return TagStep(
        action=action,
        branch=raw.get("branch"),
        expected_commit=raw.get("expected_commit"),
        tag=raw.get("tag"),
        tags=tags,
        message=raw.get("message"),
        count=int(raw.get("count", 10)),
    )


def release_plan_to_dict(plan: ReleasePlan) -> Dict[str, Any]:
    """Convert a release plan to a YAML-serializable mapping."""
    payload: Dict[str, Any] = {
        "schema_version": plan.schema_version,
        "generated_at": plan.generated_at,
        "release": {
            "path": plan.path,
            "path_label": plan.path_label,
            "release_type": plan.release_type,
            "stability": plan.stability,
            "version": plan.version,
            "app_tag": plan.app_tag,
            "release_version": plan.release_version,
        },
        "branches": {
            "app_branch": plan.app_branch_override,
            "stack_branches": dict(plan.stack_branch_overrides),
        },
        "push_order": list(plan.push_order),
        "repos": [
            {
                "name": repo.name,
                "role": repo.role,
                "local_path": repo.local_path,
                "default_branch": repo.default_branch,
                "branch": repo.branch,
                "needs_tag": repo.needs_tag,
                "reason": repo.reason,
                "latest_tag": repo.latest_tag,
                "next_tags": list(repo.next_tags),
                "head_commit": repo.head_commit,
                "existing_firmware_version_tag": repo.existing_firmware_version_tag,
                "steps": [_step_to_dict(step) for step in repo.steps],
            }
            for repo in plan.repos
        ],
        "follow_ups": [
            {
                "phase": follow_up.phase,
                "command": follow_up.command,
                "description": follow_up.description,
                "required_before_app_push": follow_up.required_before_app_push,
            }
            for follow_up in plan.follow_ups
        ],
    }
    if plan.head_commit_checksum is not None:
        payload["integrity"] = {
            "head_commit_checksum": plan.head_commit_checksum,
            "repos": integrity_payload(plan)["repos"],
        }
    return payload


def release_plan_from_dict(data: Dict[str, Any], plan_path: Optional[Path] = None) -> ReleasePlan:
    """Load a release plan from a YAML mapping."""
    schema_version = int(data.get("schema_version", 0))
    if schema_version != PLAN_SCHEMA_VERSION:
        raise ValueError(f"Unsupported plan schema version: {schema_version}")

    release = data["release"]
    branches = data.get("branches", {})
    stack_overrides = branches.get("stack_branches", {})
    if not isinstance(stack_overrides, dict):
        raise ValueError("branches.stack_branches must be a mapping")

    repos: List[RepoReleasePlan] = []
    for raw_repo in data["repos"]:
        steps = tuple(_dict_to_step(step) for step in raw_repo.get("steps", []))
        repos.append(
            RepoReleasePlan(
                name=raw_repo["name"],
                role=cast(Literal["stack", "app"], raw_repo["role"]),
                local_path=raw_repo["local_path"],
                default_branch=raw_repo["default_branch"],
                branch=raw_repo["branch"],
                needs_tag=bool(raw_repo["needs_tag"]),
                reason=raw_repo.get("reason", ""),
                latest_tag=raw_repo.get("latest_tag"),
                next_tags=tuple(raw_repo.get("next_tags", [])),
                head_commit=raw_repo["head_commit"],
                existing_firmware_version_tag=raw_repo.get("existing_firmware_version_tag"),
                steps=steps,
            )
        )

    follow_ups = tuple(
        FollowUpCommand(
            phase=cast(Literal["pre_apply", "post_apply"], raw["phase"]),
            command=raw["command"],
            description=raw["description"],
            required_before_app_push=bool(raw.get("required_before_app_push", False)),
        )
        for raw in data.get("follow_ups", [])
    )

    integrity = data.get("integrity", {})
    head_commit_checksum = None
    if isinstance(integrity, dict):
        raw_checksum = integrity.get("head_commit_checksum")
        if isinstance(raw_checksum, str):
            head_commit_checksum = raw_checksum

    return ReleasePlan(
        schema_version=schema_version,
        generated_at=str(data["generated_at"]),
        path=release["path"],
        path_label=release["path_label"],
        release_type=release["release_type"],
        stability=release["stability"],
        version=release["version"],
        app_tag=release["app_tag"],
        release_version=release["release_version"],
        app_branch_override=branches.get("app_branch"),
        stack_branch_overrides={str(k): str(v) for k, v in stack_overrides.items()},
        push_order=tuple(data["push_order"]),
        repos=tuple(repos),
        follow_ups=follow_ups,
        head_commit_checksum=head_commit_checksum,
        plan_path=str(plan_path) if plan_path is not None else None,
    )


def write_release_plan(plan: ReleasePlan, output_path: Path) -> Path:
    """Write a release plan to YAML with review comments."""
    annotated = with_plan_integrity(plan)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Opentrons robot-stack release plan\n"
        "# Review every repo branch and head_commit before applying.\n"
        f"# Checksum: {annotated.head_commit_checksum}\n"
        f"# Apply: just apply-release-plan --plan {output_path}\n"
        "# Dry run: add --dry-run\n"
        "# Regenerate if stale: just go-plan ...\n"
    )
    body = yaml.safe_dump(
        release_plan_to_dict(annotated),
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    output_path.write_text(header + body, encoding="utf-8")
    return output_path


def load_release_plan(plan_path: Path) -> ReleasePlan:
    """Load a release plan from disk."""
    text = plan_path.read_text(encoding="utf-8")
    if text.startswith("#"):
        text = "\n".join(line for line in text.splitlines() if not line.startswith("#"))
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid plan file: {plan_path}")
    return release_plan_from_dict(data, plan_path=plan_path)


def build_tag_steps(
    *,
    repo_name: str,
    branch: str,
    default_branch: str,
    head_commit: str,
    needs_tag: bool,
    next_tag: Optional[str],
    release_version: str,
    secondary_tags: Tuple[str, ...] = (),
    existing_firmware_version_tag: Optional[str] = None,
) -> Tuple[TagStep, ...]:
    """Build structured git steps for one repo tag plan."""
    if not needs_tag or next_tag is None:
        return ()

    steps: List[TagStep] = []
    if branch != default_branch:
        steps.append(TagStep(action="checkout", branch=branch))

    steps.append(
        TagStep(
            action="verify_remote_branch",
            branch=branch,
            expected_commit=head_commit,
        )
    )

    if repo_name == "ot3-firmware" and len(secondary_tags) == 1:
        version_tag = secondary_tags[0]
        steps.extend(
            [
                TagStep(
                    action="create_tag",
                    tag=version_tag,
                    message=f"Flex firmware {version_tag}",
                ),
                TagStep(
                    action="create_tag",
                    tag=next_tag,
                    message=f"chore(release): {release_version}",
                ),
                TagStep(action="verify_tag_log", tag=next_tag, count=10),
                TagStep(action="push_tags", tags=(version_tag, next_tag)),
            ]
        )
        return tuple(steps)

    if repo_name == "ot3-firmware" and existing_firmware_version_tag is not None:
        steps.extend(
            [
                TagStep(
                    action="create_tag",
                    tag=next_tag,
                    message=f"chore(release): {release_version}",
                ),
                TagStep(action="verify_tag_log", tag=next_tag, count=10),
                TagStep(action="push_tags", tags=(next_tag,)),
            ]
        )
        return tuple(steps)

    steps.extend(
        [
            TagStep(
                action="create_tag",
                tag=next_tag,
                message=f"chore(release): {release_version}",
            ),
            TagStep(action="verify_tag_log", tag=next_tag, count=10),
            TagStep(action="push_tags", tags=(next_tag,)),
        ]
    )
    return tuple(steps)


def build_follow_up_commands(path: str, app_tag: str) -> Tuple[FollowUpCommand, ...]:
    """Return advisory commands that remain manual after tag apply."""
    validate_command = f"just validate-release-tags --tag {app_tag}"
    track_command = f"just track-builds --non-interactive --path {path} --tag {app_tag} --wait"
    invalidate_command = f"just invalidate-cloudfront --non-interactive --path {path} --tag {app_tag} --execute --wait"
    verify_assets_command = f"just verify-release-assets --non-interactive --path {path} --tag {app_tag}"

    return (
        FollowUpCommand(
            phase="pre_apply",
            command=validate_command,
            description=("Verify coordinated Flex stack tags locally after creating the app tag and before pushing it."),
            required_before_app_push=path == "flex",
        ),
        FollowUpCommand(
            phase="post_apply",
            command=track_command,
            description="Track app, kickoff, and robot OS CI after pushing the app tag.",
        ),
        FollowUpCommand(
            phase="post_apply",
            command=invalidate_command,
            description="Invalidate CloudFront after builds finish.",
        ),
        FollowUpCommand(
            phase="post_apply",
            command=verify_assets_command,
            description="Verify live app and robot assets for the release tag.",
        ),
    )


def build_release_plan(
    *,
    release_path: Any,
    release_type: str,
    stability: str,
    version: str,
    results: Dict[str, Any],
    branch_config: Optional[ReleaseBranchConfig] = None,
) -> ReleasePlan:
    """Build a structured release plan from synced repo state."""
    from automation.go import (
        RepoState,
        branch_head_commit,
        compute_app_tag,
        get_stack_repo_tag_plan,
        release_branch_for_repo,
        release_version_label,
        repo_by_name,
    )

    typed_results = cast(Dict[str, RepoState], results)
    app_tag = compute_app_tag(release_path, typed_results, version, release_type, stability, branch_config)
    if app_tag is None:
        raise ValueError("Could not determine app monorepo tag for release plan")

    release_version = release_version_label(release_path, release_type, version, app_tag)
    push_order = tuple(list(release_path.stack_tag_repos) + [release_path.taggable_repo])
    repo_entries: List[RepoReleasePlan] = []

    for repo_name in release_path.stack_tag_repos:
        repo = repo_by_name(repo_name)
        state = typed_results[repo.name]
        tag_plan = get_stack_repo_tag_plan(
            repo,
            state,
            version,
            release_type,
            stability,
            release_path,
            typed_results,
            app_tag,
            branch_config,
        )
        repo_entries.append(_repo_plan_from_tag_plan(repo, tag_plan, release_version, role="stack"))

    app_repo = repo_by_name(release_path.taggable_repo)
    app_state = typed_results[app_repo.name]
    app_branch = release_branch_for_repo(
        app_state,
        app_repo,
        version,
        release_path,
        release_type,
        branch_config,
    )
    app_head = branch_head_commit(app_repo, app_branch)
    app_steps = build_tag_steps(
        repo_name=app_repo.name,
        branch=app_branch,
        default_branch=app_repo.default_branch,
        head_commit=app_head,
        needs_tag=True,
        next_tag=app_tag,
        release_version=release_version,
    )
    repo_entries.append(
        RepoReleasePlan(
            name=app_repo.name,
            role="app",
            local_path=str(app_repo.local_path),
            default_branch=app_repo.default_branch,
            branch=app_branch,
            needs_tag=True,
            reason="App monorepo tag (always last)",
            latest_tag=None,
            next_tags=(app_tag,),
            head_commit=app_head,
            steps=app_steps,
        )
    )

    overrides = branch_config.stack_branches if branch_config is not None else {}
    app_branch_override = branch_config.app_branch if branch_config is not None else None

    return ReleasePlan(
        schema_version=PLAN_SCHEMA_VERSION,
        generated_at=datetime.now(timezone.utc).isoformat(),
        path=release_path.name,
        path_label=release_path.label,
        release_type=release_type,
        stability=stability,
        version=version,
        app_tag=app_tag,
        release_version=release_version,
        app_branch_override=app_branch_override,
        stack_branch_overrides=dict(overrides),
        push_order=push_order,
        repos=tuple(repo_entries),
        follow_ups=build_follow_up_commands(release_path.name, app_tag),
    )


def _repo_plan_from_tag_plan(
    repo: Any,
    tag_plan: Any,
    release_version: str,
    *,
    role: Literal["stack", "app"],
) -> RepoReleasePlan:
    """Convert a ``TagPlan`` into a structured repo plan entry."""
    from automation.go import branch_head_commit

    head_commit = branch_head_commit(repo, tag_plan.branch)
    next_tags: Tuple[str, ...]
    if tag_plan.next_tag is None:
        next_tags = ()
    elif tag_plan.secondary_tags:
        next_tags = (tag_plan.next_tag, *tag_plan.secondary_tags)
    else:
        next_tags = (tag_plan.next_tag,)

    steps = build_tag_steps(
        repo_name=repo.name,
        branch=tag_plan.branch,
        default_branch=repo.default_branch,
        head_commit=head_commit,
        needs_tag=tag_plan.needs_tag,
        next_tag=tag_plan.next_tag,
        release_version=release_version,
        secondary_tags=tag_plan.secondary_tags,
        existing_firmware_version_tag=tag_plan.existing_firmware_version_tag,
    )

    return RepoReleasePlan(
        name=repo.name,
        role=role,
        local_path=str(repo.local_path),
        default_branch=repo.default_branch,
        branch=tag_plan.branch,
        needs_tag=tag_plan.needs_tag,
        reason=tag_plan.reason,
        latest_tag=tag_plan.latest_tag,
        next_tags=next_tags,
        head_commit=head_commit,
        existing_firmware_version_tag=tag_plan.existing_firmware_version_tag,
        steps=steps,
    )


def format_plan_summary(plan: ReleasePlan) -> str:
    """Return a short human-readable summary for terminal output."""
    lines = [
        f"Release plan for {plan.app_tag}",
        f"Path: {plan.path_label} ({plan.release_type}, {plan.stability})",
        f"Version base: {plan.version}",
    ]
    if plan.head_commit_checksum is not None:
        lines.append(f"Checksum: {plan.head_commit_checksum}")
    lines.extend(["", "Push order:"])
    for index, repo_name in enumerate(plan.push_order, start=1):
        repo = next(item for item in plan.repos if item.name == repo_name)
        status = "tag" if repo.needs_tag else "skip"
        tag_text = ", ".join(repo.next_tags) if repo.next_tags else "none"
        lines.append(f"  {index}. {repo_name} [{status}] branch={repo.branch} head={repo.head_commit[:12]} tags={tag_text}")

    pre_apply = [item for item in plan.follow_ups if item.phase == "pre_apply" and item.required_before_app_push]
    if pre_apply:
        lines.extend(["", "Required before app tag push:"])
        for item in pre_apply:
            lines.append(f"  - {item.command}")

    return "\n".join(lines)


def format_agent_plan_instructions(plan: ReleasePlan, plan_path: Path) -> str:
    """Return agent-oriented next steps after ``just go-plan``."""
    regenerate = (
        f"just go-plan --path {plan.path} --release-type {plan.release_type} "
        f"--stability {plan.stability} --version {plan.version}"
    )
    lines = [
        "Review the plan file before applying tags.",
        f"Plan file: {plan_path}",
    ]
    if plan.head_commit_checksum is not None:
        lines.append(f"Checksum: {plan.head_commit_checksum}")
    lines.extend(
        [
            "",
            "Next steps for the operator:",
            f"1. Review: {plan_path}",
            f"2. Dry run: just apply-release-plan --plan {plan_path} --dry-run",
            f"3. Apply tags: just apply-release-plan --plan {plan_path} --yes",
            "",
            "If apply reports the plan is stale, regenerate with:",
            regenerate,
            "",
            "Do not print raw git tag commands. The plan file is the source of truth.",
        ]
    )
    return "\n".join(lines)


def _run_git(args: List[str], *, cwd: Path) -> str:
    """Run git in a repo and return stdout."""
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def fetch_remote_branch_head(repo: RepoReleasePlan, workspace_root: Path) -> str:
    """Return the current origin branch tip for one planned repo."""
    repo_dir = (workspace_root / repo.local_path).resolve()
    _run_git(["fetch", "origin", repo.branch], cwd=repo_dir)
    return _run_git(["rev-parse", f"origin/{repo.branch}"], cwd=repo_dir)


def build_current_integrity_plan(plan: ReleasePlan, workspace_root: Path) -> ReleasePlan:
    """Return a copy of the plan with head commits refreshed from origin."""
    refreshed_repos: List[RepoReleasePlan] = []
    for repo in plan.repos:
        try:
            remote_head = fetch_remote_branch_head(repo, workspace_root)
        except RuntimeError:
            remote_head = repo.head_commit
        refreshed_repos.append(replace(repo, head_commit=remote_head))
    refreshed = replace(plan, repos=tuple(refreshed_repos))
    return replace(refreshed, head_commit_checksum=compute_head_commit_checksum(refreshed))


def check_plan_staleness(plan: ReleasePlan, workspace_root: Path) -> PlanStalenessReport:
    """Compare the plan checksum and per-repo branch tips against origin."""
    if plan.head_commit_checksum is None:
        return PlanStalenessReport(
            is_stale=True,
            planned_checksum=None,
            current_checksum=None,
            drifts=(),
            missing_checksum=True,
            detail="Plan has no head_commit_checksum. Regenerate with `just go-plan`.",
        )

    drifts: List[RepoCommitDrift] = []
    remote_heads: Dict[str, str] = {}
    for repo in repos_in_push_order(plan):
        try:
            remote_commit = fetch_remote_branch_head(repo, workspace_root)
        except RuntimeError as err:
            return PlanStalenessReport(
                is_stale=True,
                planned_checksum=plan.head_commit_checksum,
                current_checksum=None,
                drifts=(),
                detail=f"Could not read origin/{repo.branch} for {repo.name}: {err}",
            )

        remote_heads[repo.name] = remote_commit
        if remote_commit != repo.head_commit:
            drifts.append(
                RepoCommitDrift(
                    name=repo.name,
                    branch=repo.branch,
                    planned_commit=repo.head_commit,
                    remote_commit=remote_commit,
                )
            )

    refreshed_repos = tuple(replace(repo, head_commit=remote_heads.get(repo.name, repo.head_commit)) for repo in plan.repos)
    refreshed_plan = replace(plan, repos=refreshed_repos)
    current_checksum = compute_head_commit_checksum(refreshed_plan)
    is_stale = bool(drifts) or current_checksum != plan.head_commit_checksum
    detail = "Plan matches origin branch tips."
    if drifts:
        drift_lines = [
            (f"{drift.name} origin/{drift.branch}: planned {drift.planned_commit[:12]}, current {drift.remote_commit[:12]}")
            for drift in drifts
        ]
        detail = "Branch tips drifted since plan generation:\n" + "\n".join(drift_lines)

    return PlanStalenessReport(
        is_stale=is_stale,
        planned_checksum=plan.head_commit_checksum,
        current_checksum=current_checksum,
        drifts=tuple(drifts),
        detail=detail,
    )


def print_staleness_report(report: PlanStalenessReport) -> None:
    """Print a staleness warning before apply or verify."""
    if report.missing_checksum:
        console.print()
        console.print(
            Panel(
                report.detail,
                title="Plan integrity warning",
                border_style="yellow",
                padding=(1, 2),
            )
        )
        return

    if not report.is_stale:
        console.print("[green]Plan checksum matches current origin branch tips.[/]")
        return

    body = report.detail
    if report.planned_checksum and report.current_checksum:
        body += (
            f"\n\nPlanned checksum: {report.planned_checksum}\n"
            f"Current checksum:  {report.current_checksum}\n\n"
            "Regenerate the plan with `just go-plan` before applying."
        )
    console.print()
    console.print(
        Panel(
            body,
            title="Plan is stale",
            border_style="red",
            padding=(1, 2),
        )
    )


def print_plan_summary(plan: ReleasePlan, plan_path: Path) -> None:
    """Print a concise plan summary and output path."""
    console.print()
    console.print(
        Panel(
            format_plan_summary(plan) + f"\n\nPlan file: [bold cyan]{plan_path}[/]",
            title="Release plan",
            border_style="green",
            padding=(1, 2),
        )
    )


def print_agent_plan_instructions(plan: ReleasePlan, plan_path: Path) -> None:
    """Print agent-oriented instructions after ``just go-plan``."""
    annotated = with_plan_integrity(plan)
    console.print()
    console.print(
        Panel(
            format_agent_plan_instructions(annotated, plan_path),
            title="Agent release plan",
            border_style="green",
            padding=(1, 2),
        )
    )
