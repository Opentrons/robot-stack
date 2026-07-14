"""Apply a reviewed release plan with pre-flight git verification."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Tuple

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from automation.release_plan import (
    FollowUpCommand,
    ReleasePlan,
    RepoReleasePlan,
    TagStep,
    assess_plan_apply,
    load_release_plan,
    print_apply_readiness_report,
)

console = Console(log_time=False)


@dataclass(frozen=True)
class VerificationResult:
    """Outcome of one pre-flight verification."""

    label: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of applying one repo plan."""

    repo_name: str
    applied: bool
    detail: str


def run_git(args: Sequence[str], *, cwd: Path) -> str:
    """Run git in a repo and return stdout."""
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\n{result.stderr.strip()}")
    return result.stdout.strip()


def tag_exists(repo_dir: Path, tag: str) -> bool:
    """Return True when a tag already exists locally."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"refs/tags/{tag}^{{}}"],
        cwd=repo_dir,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def remote_tag_exists(repo_dir: Path, tag: str) -> bool:
    """Return True when a tag already exists on origin."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"],
        cwd=repo_dir,
        text=True,
        capture_output=True,
    )
    return bool(result.stdout.strip())


def verify_repo(repo: RepoReleasePlan, workspace_root: Path) -> List[VerificationResult]:
    """Run pre-flight checks for one repo that still needs tagging."""
    results: List[VerificationResult] = []
    repo_dir = (workspace_root / repo.local_path).resolve()

    if not repo_dir.is_dir():
        results.append(VerificationResult(repo.name, False, f"Missing repo directory: {repo_dir}"))
        return results

    git_dir = repo_dir / ".git"
    if not git_dir.exists():
        results.append(VerificationResult(repo.name, False, f"Not a git repository: {repo_dir}"))
        return results

    try:
        run_git(["fetch", "origin", repo.branch], cwd=repo_dir)
        remote_commit = run_git(["rev-parse", f"origin/{repo.branch}"], cwd=repo_dir)
        local_commit = run_git(["rev-parse", "HEAD"], cwd=repo_dir)
    except RuntimeError as err:
        results.append(VerificationResult(repo.name, False, str(err)))
        return results

    if remote_commit != repo.head_commit:
        results.append(
            VerificationResult(
                repo.name,
                False,
                (
                    f"origin/{repo.branch} is {remote_commit[:12]}, "
                    f"plan expected {repo.head_commit[:12]}. Regenerate with `just go-plan`."
                ),
            )
        )
    else:
        results.append(
            VerificationResult(
                repo.name,
                True,
                f"origin/{repo.branch} matches plan commit {repo.head_commit[:12]}",
            )
        )

    if local_commit != repo.head_commit:
        results.append(
            VerificationResult(
                repo.name,
                False,
                (
                    f"Local HEAD is {local_commit[:12]}, plan expected {repo.head_commit[:12]}. "
                    f"Checkout {repo.branch} and pull before apply."
                ),
            )
        )
    else:
        results.append(
            VerificationResult(
                repo.name,
                True,
                f"Local HEAD matches plan commit {repo.head_commit[:12]}",
            )
        )

    for planned_tag in repo.next_tags:
        if tag_exists(repo_dir, planned_tag):
            results.append(VerificationResult(repo.name, False, f"Local tag already exists: {planned_tag}"))
        elif remote_tag_exists(repo_dir, planned_tag):
            results.append(VerificationResult(repo.name, False, f"Remote tag already exists: {planned_tag}"))
        else:
            results.append(VerificationResult(repo.name, True, f"Tag available: {planned_tag}"))

    return results


def verify_pending_repos(pending_repos: Tuple[str, ...], plan: ReleasePlan, workspace_root: Path) -> List[VerificationResult]:
    """Verify only repos that still need new tags."""
    results: List[VerificationResult] = []
    for repo_name in pending_repos:
        repo = next(item for item in plan.repos if item.name == repo_name)
        results.extend(verify_repo(repo, workspace_root))
    return results


def print_verification_results(results: List[VerificationResult]) -> bool:
    """Print verification results and return True when all passed."""
    table = Table(title="Release plan verification", show_lines=True)
    table.add_column("Repo", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    all_ok = True
    for result in results:
        status = "[green]ok[/]" if result.ok else "[red]fail[/]"
        if not result.ok:
            all_ok = False
        table.add_row(result.label, status, result.detail)

    console.print(table)
    return all_ok


def execute_step(step: TagStep, repo_dir: Path, *, dry_run: bool) -> str:
    """Execute or describe one plan step."""
    if step.action == "checkout":
        if step.branch is None:
            raise ValueError("checkout step requires branch")
        command = f"git checkout {step.branch}"
        if not dry_run:
            run_git(["checkout", step.branch], cwd=repo_dir)
        return command

    if step.action == "verify_remote_branch":
        if step.branch is None or step.expected_commit is None:
            raise ValueError("verify_remote_branch requires branch and expected_commit")
        command = f"git fetch origin {step.branch} && git rev-parse origin/{step.branch}"
        if not dry_run:
            run_git(["fetch", "origin", step.branch], cwd=repo_dir)
            remote_commit = run_git(["rev-parse", f"origin/{step.branch}"], cwd=repo_dir)
            if remote_commit != step.expected_commit:
                raise RuntimeError(f"origin/{step.branch} is {remote_commit}, expected {step.expected_commit}")
            local_commit = run_git(["rev-parse", "HEAD"], cwd=repo_dir)
            if local_commit != step.expected_commit:
                raise RuntimeError(f"HEAD is {local_commit}, expected {step.expected_commit}")
        return command

    if step.action == "create_tag":
        if step.tag is None or step.message is None:
            raise ValueError("create_tag requires tag and message")
        command = f"git tag -a {step.tag} -m '{step.message}'"
        if not dry_run:
            if tag_exists(repo_dir, step.tag):
                raise RuntimeError(f"Refusing to create existing tag: {step.tag}")
            run_git(["tag", "-a", step.tag, "-m", step.message], cwd=repo_dir)
        return command

    if step.action == "verify_tag_log":
        if step.tag is None:
            raise ValueError("verify_tag_log requires tag")
        command = f"git log {step.tag} --oneline -n {step.count}"
        if not dry_run:
            run_git(["log", step.tag, "--oneline", "-n", str(step.count)], cwd=repo_dir)
        return command

    if step.action == "push_tags":
        if not step.tags:
            raise ValueError("push_tags requires tags")
        tag_args = " ".join(step.tags)
        command = f"git push origin {tag_args}"
        if not dry_run:
            run_git(["push", "origin", *step.tags], cwd=repo_dir)
        return command

    raise ValueError(f"Unsupported step action: {step.action}")


def run_follow_up(command: FollowUpCommand, *, dry_run: bool) -> str:
    """Run or describe one advisory follow-up command."""
    if dry_run:
        return command.command
    result = subprocess.run(command.command, shell=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Follow-up command failed ({result.returncode}): {command.command}")
    return command.command


def apply_repo_plan(
    repo: RepoReleasePlan,
    workspace_root: Path,
    *,
    dry_run: bool,
    pre_push_follow_ups: Sequence[FollowUpCommand] = (),
) -> ApplyResult:
    """Apply tag steps for one repository."""
    if not repo.needs_tag:
        return ApplyResult(repo.name, False, "No new tag needed")

    repo_dir = (workspace_root / repo.local_path).resolve()
    executed: List[str] = []
    try:
        for step in repo.steps:
            if step.action == "push_tags" and pre_push_follow_ups:
                for follow_up in pre_push_follow_ups:
                    console.print(f"[cyan]Pre-push check:[/] {follow_up.description}")
                    executed.append(run_follow_up(follow_up, dry_run=dry_run))
            executed.append(execute_step(step, repo_dir, dry_run=dry_run))
    except (RuntimeError, ValueError) as err:
        return ApplyResult(repo.name, False, str(err))

    if dry_run:
        detail = "\n".join(executed)
    else:
        detail = f"Pushed {', '.join(repo.next_tags)} on {repo.branch}"
    return ApplyResult(repo.name, True, detail)


def apply_release_plan(
    plan: ReleasePlan,
    *,
    workspace_root: Path,
    dry_run: bool = False,
    verify_only: bool = False,
    assume_yes: bool = False,
) -> int:
    """Apply a reviewed release plan in push order."""
    console.print(
        Panel(
            f"App tag: [bold]{plan.app_tag}[/]\n"
            f"Path: {plan.path_label} ({plan.release_type}, {plan.stability})\n"
            f"Plan generated: {plan.generated_at}"
            + (f"\nChecksum: {plan.head_commit_checksum}" if plan.head_commit_checksum is not None else ""),
            title="Applying release plan",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    readiness = assess_plan_apply(plan, workspace_root)
    print_apply_readiness_report(readiness)
    if not readiness.can_apply:
        return 1

    if verify_only:
        if readiness.pending_repos:
            verification = verify_pending_repos(readiness.pending_repos, plan, workspace_root)
            if not print_verification_results(verification):
                console.print("[red]Verification failed for pending repos.[/]")
                return 1
        console.print("[green]Verification passed.[/]")
        return 0

    if not readiness.pending_repos:
        console.print("[green]Nothing to apply; all planned tags are already on origin.[/]")
        return 0

    verification = verify_pending_repos(readiness.pending_repos, plan, workspace_root)
    if not print_verification_results(verification):
        console.print("[red]Verification failed for pending repos. Fix the issues above or regenerate the plan.[/]")
        return 1

    repos_to_apply = [next(item for item in plan.repos if item.name == repo_name) for repo_name in readiness.pending_repos]

    if not assume_yes and not dry_run:
        console.print()
        for repo in repos_to_apply:
            console.print(f"- [bold]{repo.name}[/] on [bold]{repo.branch}[/]: {', '.join(repo.next_tags)}")
        if not Confirm.ask("Apply these tag operations?", default=False):
            console.print("[yellow]Aborted.[/]")
            return 1

    pre_apply = [item for item in plan.follow_ups if item.phase == "pre_apply" and item.required_before_app_push]

    for repo_name in plan.push_order:
        repo = next(item for item in plan.repos if item.name == repo_name)
        if repo.name not in readiness.pending_repos:
            if repo.name in readiness.applied_repos:
                console.print(f"[dim]Skipping {repo.name}: already applied on origin[/]")
            elif not repo.needs_tag:
                console.print(f"[dim]Skipping {repo.name}: {repo.reason}[/]")
            continue

        console.rule(f"{repo.name} ({repo.role})")
        pre_push_follow_ups = pre_apply if repo.role == "app" else ()
        result = apply_repo_plan(
            repo,
            workspace_root,
            dry_run=dry_run,
            pre_push_follow_ups=pre_push_follow_ups,
        )
        if not result.applied:
            console.print(f"[red]{result.detail}[/]")
            return 1
        console.print(f"[green]{result.detail}[/]")

    if dry_run:
        console.print("[green]Dry run complete. No git changes were made.[/]")
    else:
        console.print()
        console.print("[bold]Tag apply complete.[/] Run these follow-up commands:")
        for follow_up in plan.follow_ups:
            if follow_up.phase == "post_apply":
                console.print(f"- {follow_up.command}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI arguments for release plan apply."""
    parser = argparse.ArgumentParser(
        description="Apply a reviewed robot-stack release plan.",
    )
    parser.add_argument(
        "--plan",
        required=True,
        type=Path,
        help="Path to a .plan.yaml file generated by `just go --write-plan`.",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path("."),
        help="Workspace root containing cloned stack repos (default: current directory).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify and print git commands without changing anything.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Run pre-flight verification only.",
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Require --yes for apply; fail instead of prompting.",
    )
    return parser


def main() -> None:
    """Load a release plan and apply it with verification."""
    parser = build_parser()
    args = parser.parse_args()

    if args.non_interactive and not args.yes and not args.dry_run and not args.verify_only:
        console.print("[red]--non-interactive requires --yes, --dry-run, or --verify-only[/]")
        sys.exit(1)

    plan_path = args.plan.resolve()
    if not plan_path.is_file():
        console.print(f"[red]Plan file not found: {plan_path}[/]")
        sys.exit(1)

    try:
        plan = load_release_plan(plan_path)
    except (ValueError, yaml.YAMLError) as err:
        console.print(f"[red]Invalid plan file: {err}[/]")
        sys.exit(1)

    workspace_root = args.workspace_root.resolve()
    exit_code = apply_release_plan(
        plan,
        workspace_root=workspace_root,
        dry_run=args.dry_run,
        verify_only=args.verify_only,
        assume_yes=args.yes,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
