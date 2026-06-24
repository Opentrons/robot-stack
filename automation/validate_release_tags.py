"""Verify coordinated Flex release tags exist in opentrons, oe-core, and ot3-firmware."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from automation.flex_coordinated_tags import (
    coordinated_tag_for_repo,
    is_external_stack_coordination_tag,
    is_firmware_version_tag,
    normalize_tag,
)

console = Console(log_time=False)

WORKSPACE_ROOT: Final[Path] = Path(__file__).resolve().parent.parent

FLEX_COORDINATED_REPOS: Final[tuple[tuple[str, Path], ...]] = (
    ("opentrons", WORKSPACE_ROOT / "opentrons"),
    ("oe-core", WORKSPACE_ROOT / "oe-core"),
    ("ot3-firmware", WORKSPACE_ROOT / "ot3-firmware"),
)


@dataclass(frozen=True)
class TagCheckResult:
    """Outcome of looking up one release tag in a local repo."""

    repo_name: str
    local_path: Path
    tag: str
    present: bool
    commit: Optional[str] = None
    subject: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None


def is_flex_stack_coordination_tag(tag: str) -> bool:
    """Return True when the tag is an app/oe-core stack coordination tag."""
    clean = normalize_tag(tag)
    return clean.startswith("ot3@") or is_external_stack_coordination_tag(clean)


def run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command and capture stdout/stderr as text."""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def fetch_repo(repo_path: Path) -> None:
    """Fetch tags from origin, overwriting stale local tags with remote refs."""
    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Not a git repo: {repo_path}")
    result = run_git(["fetch", "--tags", "--force", "origin"], repo_path)
    if result.returncode != 0:
        raise RuntimeError(f"git fetch failed in {repo_path}: {result.stderr.strip() or result.stdout.strip()}")


def check_tag_in_repo(repo_name: str, repo_path: Path, tag: str) -> TagCheckResult:
    """Return whether an annotated or lightweight tag exists locally."""
    clean_tag = normalize_tag(tag)
    if not (repo_path / ".git").is_dir():
        return TagCheckResult(
            repo_name=repo_name,
            local_path=repo_path,
            tag=clean_tag,
            present=False,
            error=f"repo not cloned at {repo_path}",
        )

    resolve = run_git(["rev-parse", "--verify", f"{clean_tag}^{{commit}}"], repo_path)
    if resolve.returncode != 0:
        return TagCheckResult(
            repo_name=repo_name,
            local_path=repo_path,
            tag=clean_tag,
            present=False,
            error="tag not found",
        )

    commit = resolve.stdout.strip()
    subject_result = run_git(
        ["log", "-1", "--format=%s", commit],
        repo_path,
    )
    subject = subject_result.stdout.strip() if subject_result.returncode == 0 else None
    short_commit = commit[:12] if len(commit) >= 12 else commit

    return TagCheckResult(
        repo_name=repo_name,
        local_path=repo_path,
        tag=clean_tag,
        present=True,
        commit=short_commit,
        subject=subject,
    )


def integer_version_tags_on_commit(repo_path: Path, commit: str) -> list[str]:
    """Return integer vN firmware version tags pointing at a commit."""
    result = run_git(["tag", "--points-at", commit], repo_path)
    if result.returncode != 0:
        return []
    tags = [tag.strip() for tag in result.stdout.splitlines() if tag.strip()]
    return sorted(
        (tag for tag in tags if is_firmware_version_tag(tag)),
        key=lambda tag: int(tag[1:]),
    )


def check_firmware_version_tag(repo_path: Path, coordination_result: TagCheckResult) -> TagCheckResult:
    """Verify ot3-firmware has an integer vN version tag on the coordination commit."""
    if not coordination_result.present or coordination_result.commit is None:
        return TagCheckResult(
            repo_name="ot3-firmware",
            local_path=repo_path,
            tag="vN",
            present=False,
            error="coordination tag missing",
            note="integer version tag required on same commit",
        )

    full_commit = run_git(
        ["rev-parse", "--verify", f"{coordination_result.tag}^{{commit}}"],
        repo_path,
    )
    if full_commit.returncode != 0:
        return TagCheckResult(
            repo_name="ot3-firmware",
            local_path=repo_path,
            tag="vN",
            present=False,
            error="could not resolve coordination commit",
            note="integer version tag required on same commit",
        )

    version_tags = integer_version_tags_on_commit(repo_path, full_commit.stdout.strip())
    if not version_tags:
        return TagCheckResult(
            repo_name="ot3-firmware",
            local_path=repo_path,
            tag="vN",
            present=False,
            error="no integer vN tag on coordination commit",
            note="tag vN on same commit as coordination tag",
        )

    latest = version_tags[-1]
    return TagCheckResult(
        repo_name="ot3-firmware",
        local_path=repo_path,
        tag=latest,
        present=True,
        commit=coordination_result.commit,
        subject=coordination_result.subject,
        note="integer version tag on same commit",
    )


def check_coordinated_tag(
    stack_tag: str,
    repos: Sequence[tuple[str, Path]] = FLEX_COORDINATED_REPOS,
) -> list[TagCheckResult]:
    """Check stack coordination tags across Flex repos (ex* mapping on firmware)."""
    results: list[TagCheckResult] = []
    firmware_coordination: Optional[TagCheckResult] = None

    for repo_name, repo_path in repos:
        expected = coordinated_tag_for_repo(repo_name, stack_tag)
        result = check_tag_in_repo(repo_name, repo_path, expected)
        if repo_name == "ot3-firmware":
            if expected != normalize_tag(stack_tag):
                result = TagCheckResult(
                    repo_name=result.repo_name,
                    local_path=result.local_path,
                    tag=result.tag,
                    present=result.present,
                    commit=result.commit,
                    subject=result.subject,
                    error=result.error,
                    note=f"mapped from stack tag {normalize_tag(stack_tag)}",
                )
            firmware_coordination = result
        results.append(result)

    if firmware_coordination is not None:
        firmware_repo = next(path for name, path in repos if name == "ot3-firmware")
        results.append(check_firmware_version_tag(firmware_repo, firmware_coordination))

    return results


def render_results(results: Sequence[TagCheckResult], stack_tag: str) -> None:
    """Print a Rich table summarizing coordinated tag presence."""
    table = Table(title=f"Coordinated release tag: {normalize_tag(stack_tag)}")
    table.add_column("Repo / check")
    table.add_column("Tag")
    table.add_column("Present")
    table.add_column("Commit")
    table.add_column("Subject / error")

    for result in results:
        label = result.repo_name
        if result.note:
            label = f"{result.repo_name} ({result.note})"
        if result.present:
            table.add_row(
                label,
                result.tag,
                "yes",
                result.commit or "",
                result.subject or "",
            )
        else:
            table.add_row(
                label,
                result.tag,
                "no",
                "",
                result.error or "missing",
            )

    console.print(table)

    missing = [result for result in results if not result.present]
    if missing:
        console.print(
            Panel(
                "Coordinated Flex releases require matching stack tags on opentrons and oe-core, "
                "the mapped coordination tag on ot3-firmware (ex* for external), and an integer "
                "vN version tag on the same firmware commit.\n\n"
                f"Missing: {', '.join(f'{r.repo_name} ({r.tag})' for r in missing)}",
                title="Tag check failed",
                style="red",
            )
        )
    else:
        console.print(
            Panel(
                "Stack coordination tags and firmware vN version tag are present.",
                title="Tag check passed",
                style="green",
            )
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=("Verify coordinated Flex release tags locally in opentrons, oe-core, and ot3-firmware."),
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Stack release tag to verify (e.g. ot3@8.5.0-beta.0 or v10.0.0-alpha.0).",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Run git fetch --tags --force origin in each repo before checking (remote tags win).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entrypoint for coordinated tag validation."""
    args = parse_args(argv)
    stack_tag = normalize_tag(args.tag)

    if not is_flex_stack_coordination_tag(stack_tag):
        console.print(f"[yellow]Warning:[/yellow] {stack_tag} is not an ot3@ or external v* stack coordination tag.")

    if args.fetch:
        for repo_name, repo_path in FLEX_COORDINATED_REPOS:
            console.print(f"Fetching tags in {repo_name}...")
            try:
                fetch_repo(repo_path)
            except (FileNotFoundError, RuntimeError) as error:
                console.print(f"[red]{repo_name}:[/red] {error}")
                return 1

    results = check_coordinated_tag(stack_tag)
    render_results(results, stack_tag)
    return 0 if all(result.present for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
