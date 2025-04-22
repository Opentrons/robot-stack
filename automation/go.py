import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
import semver

console = Console(log_time=False)

# ------------------------------------------------------------------------------
# Data Model
# ------------------------------------------------------------------------------


@dataclass
class RepoSpec:
    name: str
    repo_url: str
    local_path: Path
    primary_branch: str
    want_chore_release: bool
    tag_patterns: List[str]

    def branches_to_sync(self) -> List[str]:
        branches = [self.primary_branch]
        if self.want_chore_release:
            chore = get_latest_chore_release_branch(self.repo_url)
            if chore:
                branches.append(chore)
        return branches


# Define repository specifications
repos = [
    RepoSpec(
        name="buildroot",
        repo_url="https://github.com/Opentrons/buildroot.git",
        local_path=Path("./buildroot"),
        primary_branch="opentrons-develop",
        want_chore_release=True,
        tag_patterns=["v", "internal@"],
    ),
    RepoSpec(
        name="ot3-firmware",
        repo_url="https://github.com/Opentrons/ot3-firmware.git",
        local_path=Path("./ot3-firmware"),
        primary_branch="main",
        want_chore_release=True,
        tag_patterns=["v", "internal@"],
    ),
    RepoSpec(
        name="oe-core",
        repo_url="https://github.com/Opentrons/oe-core.git",
        local_path=Path("./oe-core"),
        primary_branch="main",
        want_chore_release=True,
        tag_patterns=["v", "internal@"],
    ),
    RepoSpec(
        name="opentrons",
        repo_url="https://github.com/Opentrons/opentrons.git",
        local_path=Path("./opentrons"),
        primary_branch="edge",
        want_chore_release=True,
        tag_patterns=["v", "ot3@"],
    ),
]


@dataclass
class RepoState:
    branch_tags: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    overall_tags: Dict[str, Optional[str]] = field(default_factory=dict)


# ------------------------------------------------------------------------------
# Git Helpers
# ------------------------------------------------------------------------------


def run_git_command(args: List[str], cwd: Path = None) -> str:
    result = subprocess.run(["git"] + args, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(args)}\n{result.stderr}")
    return result.stdout.strip()


def clone_or_fetch_repo(repo: RepoSpec) -> None:
    if not (repo.local_path.exists() and (repo.local_path / ".git").exists()):
        console.log(f"[bold green]Cloning[/bold green] {repo.name}")
        repo.local_path.parent.mkdir(parents=True, exist_ok=True)
        run_git_command(["clone", repo.repo_url, str(repo.local_path)])
    else:
        console.log(f"[bold blue]Fetching[/bold blue] {repo.name}")
        run_git_command(["fetch", "--all"], cwd=repo.local_path)


def get_latest_chore_release_branch(repo_url: str) -> str:
    out = run_git_command(["ls-remote", "--heads", repo_url])
    branches = [line.split("refs/heads/")[1] for line in out.splitlines() if "refs/heads/chore_release-" in line]
    numeric = [b for b in branches if b.replace("chore_release-", "").replace(".", "").isdigit()]
    if not numeric:
        return ""
    latest = sorted(
        numeric,
        key=lambda s: semver.Version.parse(s.replace("chore_release-", "")),
    )[-1]
    return latest


def ensure_branches_checked_out(repo: RepoSpec, branches: List[str]) -> None:
    for branch in branches:
        local = run_git_command(["branch"], cwd=repo.local_path)
        if branch not in local:
            run_git_command(["checkout", "-B", branch, f"origin/{branch}"], cwd=repo.local_path)
        else:
            run_git_command(["checkout", branch], cwd=repo.local_path)
            run_git_command(["pull"], cwd=repo.local_path)


def get_latest_tags(local_path: Path, branch: str, patterns: List[str], count: int = 7) -> List[str]:
    tags = []
    for pattern in patterns:
        out = run_git_command(
            ["tag", "-l", f"{pattern}*", "--merged", branch, "--sort=-creatordate"],
            cwd=local_path,
        )
        tags.extend(out.splitlines()[:count])
    return tags


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------


def main():
    results: Dict[str, RepoState] = {}
    for repo in repos:
        clone_or_fetch_repo(repo)
        branches = repo.branches_to_sync()
        ensure_branches_checked_out(repo, branches)

        state = RepoState()
        for branch in branches:
            state.branch_tags[branch] = {}
            for pattern in repo.tag_patterns:
                tags = get_latest_tags(repo.local_path, branch, [pattern])
                state.branch_tags[branch][pattern] = tags

        # overall latest by pattern (from primary branch)
        for pattern in repo.tag_patterns:
            all_tags = run_git_command(
                ["tag", "-l", f"{pattern}*", "--sort=-creatordate"],
                cwd=repo.local_path,
            ).splitlines()
            state.overall_tags[pattern] = all_tags[0] if all_tags else None

        results[repo.name] = state
        console.log(f"[green]✅ {repo.name} synced[/green]")

    # final summary
    summary = Table(title="Latest Tags Summary", show_lines=True)
    summary.add_column("Repo", style="bold")
    summary.add_column("Pattern")
    summary.add_column("Overall Latest")
    summary.add_column("Branch Found In")

    for name, state in results.items():
        for pattern, overall in state.overall_tags.items():
            branch_found: Optional[str] = None
            if overall:
                for branch, tags in state.branch_tags.items():
                    if overall in tags:
                        branch_found = branch
                        break
            summary.add_row(name, pattern, overall or "[italic]None[/italic]", branch_found or "[italic]N/A[/italic]")

    console.print(summary)


if __name__ == "__main__":
    main()
