import subprocess
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
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
    want_chore_release: bool  # If True, include the latest chore_release-* branch
    tag_patterns: List[str]  # e.g. ["v", "internal@"]

    def branches_to_sync(self) -> List[str]:
        """Returns the list of branch names to sync for this repository."""
        branches = [self.primary_branch]
        if self.want_chore_release:
            chore = get_latest_chore_release_branch(self.repo_url)
            if chore:
                branches.append(chore)
        return branches


# ------------------------------------------------------------------------------
# Git Helpers (generalized for any repo)
# ------------------------------------------------------------------------------


def run_git_command(args: List[str], cwd: Path = None) -> str:
    result = subprocess.run(["git"] + args, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"Git command failed: {' '.join(args)}\n{result.stderr}")
    return result.stdout.strip()


def clone_or_fetch_repo(repo: RepoSpec) -> None:
    """Clones the repository if not already cloned; otherwise fetches updates."""
    if not repo.local_path.exists():
        console.log(f"[bold green]Cloning[/bold green] {repo.name} from {repo.repo_url} into {repo.local_path}")
        run_git_command(["clone", repo.repo_url, str(repo.local_path)])
    else:
        console.log(f"[bold blue]Fetching[/bold blue] updates in {repo.local_path} for {repo.name}")
        run_git_command(["fetch", "--all"], cwd=repo.local_path)


def get_latest_chore_release_branch(repo_url: str, count: int = 10) -> str:
    """
    Retrieves the latest chore_release-* branch from the remote repository.
    Only branches with a numeric suffix (after removing dots) are considered.
    """
    remote_branches = run_git_command(["ls-remote", "--heads", repo_url])
    chore_branches = [
        line.split("refs/heads/")[1] for line in remote_branches.splitlines() if "refs/heads/chore_release-" in line
    ]
    # Filter out branches with non-numeric suffixes
    numeric_chore_branches = [
        branch for branch in chore_branches if branch.replace("chore_release-", "").replace(".", "").isdigit()
    ]
    if not numeric_chore_branches:
        return ""
    latest = sorted(numeric_chore_branches, key=lambda s: semver.Version.parse(s.replace("chore_release-", "")))[-1]
    return latest


def ensure_branches_checked_out(repo: RepoSpec, branches: List[str]) -> List[Tuple[str, str]]:
    """
    Checks out the specified branches in the repository and pulls the latest changes.
    Returns a list of tuples containing branch names and the last commit timestamp.
    """
    summary = []
    for branch in branches:
        local_branches = run_git_command(["branch"], cwd=repo.local_path)
        if branch not in local_branches:
            console.log(f"[yellow]Checking out {branch}[/yellow] in {repo.name}")
            run_git_command(["checkout", "-B", branch, f"origin/{branch}"], cwd=repo.local_path)
        else:
            console.log(f"[green]{branch} already present in {repo.name}[/green], pulling latest")
            run_git_command(["checkout", branch], cwd=repo.local_path)
            run_git_command(["pull"], cwd=repo.local_path)
        # Get the last commit timestamp
        timestamp_iso = run_git_command(
            ["log", "-1", "--format=%cd", "--date=iso", branch],
            cwd=repo.local_path,
        )
        dt = datetime.fromisoformat(timestamp_iso.replace(" ", "T").replace(" +", "+"))
        timestamp = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        summary.append((branch, timestamp))
    return summary


def get_latest_tags(local_path: Path, branch: str, patterns: List[str], count: int = 7) -> List[str]:
    """
    Retrieves the latest tags matching given patterns on a specific branch.
    """
    matching_tags = []
    for pattern in patterns:
        tags = run_git_command(
            ["tag", "-l", f"{pattern}*", "--merged", branch, "--sort=-creatordate"],
            cwd=local_path,
        ).splitlines()
        matching_tags.extend(tags[:count])
    return matching_tags[:count]


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------


def main():
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

    for repo in repos:
        console.rule(f"[bold cyan]{repo.name} Repo Sync")
        console.print(f"[bold]Cloning or fetching {repo.name}...[/bold]")
        clone_or_fetch_repo(repo)

        console.print(f"[bold]Synchronizing branches for {repo.name}...[/bold]")
        branches = repo.branches_to_sync()
        branch_summary = ensure_branches_checked_out(repo, branches)

        # Print branch sync summary for this repository
        summary_table = Table(title=f"{repo.name} - Sync Summary", show_lines=True)
        summary_table.add_column("Branch", style="bold")
        summary_table.add_column("Last Commit Timestamp")
        for branch, timestamp in branch_summary:
            summary_table.add_row(branch, timestamp)
        console.print(summary_table)
        console.print(
            f":white_check_mark: [bold green]{repo.name} sync complete as of {datetime.now().isoformat()}[/bold green]\n"
        )

        # Create a dynamic Rich table for the latest tags summary based on repo.tag_patterns.
        tag_table_title = f"{repo.name} - Latest Tags per Branch"
        tags_table = Table(title=tag_table_title, show_lines=True)
        tags_table.add_column("Branch", style="bold cyan")
        # Dynamically add a column for each tag pattern.
        for pattern in repo.tag_patterns:
            tags_table.add_column(f"Latest '{pattern}' Tags", overflow="fold")

        for branch, _ in branch_summary:
            row = [branch]
            # For each pattern in tag_patterns, get the latest tags.
            for pattern in repo.tag_patterns:
                latest_tags = get_latest_tags(repo.local_path, branch, [pattern])
                tag_str = "\n".join(latest_tags) if latest_tags else "[italic]No matching tags found[/italic]"
                row.append(tag_str)
            tags_table.add_row(*row)
        console.print(tags_table)


if __name__ == "__main__":
    main()
