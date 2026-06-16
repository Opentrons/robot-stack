"""Verify a coordinated Flex release tag exists in opentrons, oe-core, and ot3-firmware."""

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


def normalize_tag(tag: str) -> str:
    """Strip refs/tags/ prefix so git commands receive a plain tag name."""
    if tag.startswith("refs/tags/"):
        return tag[len("refs/tags/") :]
    return tag


def is_flex_coordinated_tag(tag: str) -> bool:
    """Return True when the tag matches the coordinated Flex release scheme."""
    clean = normalize_tag(tag)
    return clean.startswith("ot3@") or clean.startswith("v")


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
    """Fetch tags from origin for one local clone."""
    if not (repo_path / ".git").is_dir():
        raise FileNotFoundError(f"Not a git repo: {repo_path}")
    result = run_git(["fetch", "--tags", "origin"], repo_path)
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


def check_coordinated_tag(
    tag: str,
    repos: Sequence[tuple[str, Path]] = FLEX_COORDINATED_REPOS,
) -> list[TagCheckResult]:
    """Check the same release tag across all coordinated Flex repos."""
    return [check_tag_in_repo(name, path, tag) for name, path in repos]


def render_results(results: Sequence[TagCheckResult], tag: str) -> None:
    """Print a Rich table summarizing coordinated tag presence."""
    table = Table(title=f"Coordinated release tag: {normalize_tag(tag)}")
    table.add_column("Repo")
    table.add_column("Present")
    table.add_column("Commit")
    table.add_column("Subject / error")

    for result in results:
        if result.present:
            table.add_row(
                result.repo_name,
                "yes",
                result.commit or "",
                result.subject or "",
            )
        else:
            table.add_row(
                result.repo_name,
                "no",
                "",
                result.error or "missing",
            )

    console.print(table)

    missing = [result.repo_name for result in results if not result.present]
    if missing:
        console.print(
            Panel(
                "Coordinated Flex releases require the same tag on opentrons, "
                "oe-core, and ot3-firmware before pushing the app tag.\n\n"
                f"Missing in: {', '.join(missing)}",
                title="Tag check failed",
                style="red",
            )
        )
    else:
        commits = {result.commit for result in results if result.commit}
        if len(commits) > 1:
            console.print(
                Panel(
                    "The tag exists in all repos but resolves to different commits. "
                    "Verify each tag points at the intended release commit.",
                    title="Warning",
                    style="yellow",
                )
            )
        else:
            console.print(
                Panel(
                    "Tag is present in all three repos.",
                    title="Tag check passed",
                    style="green",
                )
            )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=("Verify a coordinated Flex release tag exists locally in opentrons, oe-core, and ot3-firmware."),
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Release tag to verify (e.g. ot3@8.5.0-beta.0 or v10.0.0-alpha.0).",
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Run git fetch --tags origin in each repo before checking.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entrypoint for coordinated tag validation."""
    args = parse_args(argv)
    tag = normalize_tag(args.tag)

    if not is_flex_coordinated_tag(tag):
        console.print(f"[yellow]Warning:[/yellow] {tag} is not an ot3@ or v* coordinated tag.")

    if args.fetch:
        for repo_name, repo_path in FLEX_COORDINATED_REPOS:
            console.print(f"Fetching tags in {repo_name}...")
            try:
                fetch_repo(repo_path)
            except (FileNotFoundError, RuntimeError) as error:
                console.print(f"[red]{repo_name}:[/red] {error}")
                return 1

    results = check_coordinated_tag(tag)
    render_results(results, tag)
    return 0 if all(result.present for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
