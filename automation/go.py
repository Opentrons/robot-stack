import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

console = Console(log_time=False)


# ------------------------------------------------------------------------------
# Data Model
# ------------------------------------------------------------------------------


@dataclass
class RepoSpec:
    name: str
    repo_url: str
    local_path: Path
    default_branch: str
    external_tag_pattern: str
    internal_tag_pattern: str

    def branches_to_sync(self, version: str) -> List[str]:
        """Decide which branches to sync based on the base version."""
        branches = [self.default_branch]
        chore = f"chore_release-{version.lstrip('v')}"
        if branch_exists(self.repo_url, chore):
            branches.append(chore)
        return branches


@dataclass
class RepoState:
    branch_tags: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    overall_tags: Dict[str, Optional[str]] = field(default_factory=dict)


# ------------------------------------------------------------------------------
# Git Helpers
# ------------------------------------------------------------------------------


def run_git_command(args: List[str], cwd: Optional[Path] = None) -> str:
    """Run a git command and return its stdout, or raise on error."""
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Git failed: {' '.join(args)}\n{result.stderr}")
    return result.stdout.strip()


def branch_exists(repo_url: str, branch_name: str) -> bool:
    """Check if a given branch exists on the remote."""
    try:
        out = run_git_command(["ls-remote", "--heads", repo_url, f"refs/heads/{branch_name}"])
        return bool(out)
    except RuntimeError:
        return False


# ------------------------------------------------------------------------------
# Per-Repo Task
# ------------------------------------------------------------------------------


def process_repo(repo: RepoSpec, version: str) -> RepoState:
    """Clone or fetch the repo, checkout branches, and collect tags."""
    # clone or fetch
    if not (repo.local_path / ".git").exists():
        run_git_command(["clone", repo.repo_url, str(repo.local_path)])
    else:
        run_git_command(["fetch", "--all"], cwd=repo.local_path)

    # checkout branches
    branches = repo.branches_to_sync(version)
    for br in branches:
        existing = [b.strip("* ").strip() for b in run_git_command(["branch"], cwd=repo.local_path).splitlines()]
        if br not in existing:
            run_git_command(["checkout", "-B", br, f"origin/{br}"], cwd=repo.local_path)
        else:
            run_git_command(["checkout", br], cwd=repo.local_path)
            run_git_command(["pull"], cwd=repo.local_path)

    # collect tags
    state = RepoState()
    patterns = [repo.external_tag_pattern, repo.internal_tag_pattern]

    for br in branches:
        state.branch_tags[br] = {
            pat: run_git_command(
                ["tag", "-l", f"{pat}*", "--merged", br, "--sort=-creatordate"],
                cwd=repo.local_path,
            ).splitlines()[:7]
            for pat in patterns
        }

    for pat in patterns:
        tags = run_git_command(["tag", "-l", f"{pat}*", "--sort=-creatordate"], cwd=repo.local_path).splitlines()
        state.overall_tags[pat] = tags[0] if tags else None

    return state


# ------------------------------------------------------------------------------
# Table Printing Functions
# ------------------------------------------------------------------------------


def print_external_table(results: Dict[str, RepoState], repos: List[RepoSpec], version: str) -> None:
    """Print a table of external compare URLs, using chore_release branch if present."""
    tbl = Table(title="External GitHub Compare URLs")
    tbl.add_column("Repo", style="bold")
    tbl.add_column("Compare", no_wrap=True)

    for repo in repos:
        st = results.get(repo.name)
        if not st:
            continue

        pat = repo.external_tag_pattern
        chore = f"chore_release-{version.lstrip('v')}"
        branch = chore if chore in st.branch_tags else repo.default_branch
        tags = st.branch_tags[branch].get(pat, [])
        tag = tags[0] if tags else None
        base = repo.repo_url.removesuffix(".git")

        if tag:
            url = f"{base}/compare/{tag}...{branch}"
            link = Text(url, style=f"link {url}")
        else:
            link = Text("None", style="italic")

        tbl.add_row(repo.name, link)

    console.print(tbl)


def print_internal_table(results: Dict[str, RepoState], repos: List[RepoSpec], version: str) -> None:
    """Print a table of internal compare URLs, using chore_release branch if present."""
    tbl = Table(title="Internal GitHub Compare URLs")
    tbl.add_column("Repo", style="bold")
    tbl.add_column("Compare", no_wrap=True)

    for repo in repos:
        st = results.get(repo.name)
        if not st:
            continue

        pat = repo.internal_tag_pattern
        chore = f"chore_release-{version.lstrip('v')}"
        branch = chore if chore in st.branch_tags else repo.default_branch
        tags = st.branch_tags[branch].get(pat, [])
        tag = tags[0] if tags else None
        base = repo.repo_url.removesuffix(".git")

        if tag:
            url = f"{base}/compare/{tag}...{branch}"
            link = Text(url, style=f"link {url}")
        else:
            link = Text("None", style="italic")

        tbl.add_row(repo.name, link)

    console.print(tbl)


# ------------------------------------------------------------------------------
# Git-Log Helper
# ------------------------------------------------------------------------------


def show_changes_since_tag(repo: RepoSpec, branch: str, tag: str) -> None:
    """Print last 20 commits since <tag> on <branch>, or note none."""
    lp = repo.local_path
    head = run_git_command(["rev-parse", branch], cwd=lp)
    tagc = run_git_command(["rev-list", "-n", "1", tag], cwd=lp)

    if head == tagc:
        console.print(f"[yellow]No changes in {repo.name} since {tag} on {branch}[/]")
    else:
        console.rule(f"{repo.name} changes: {tag}...{branch}")
        log = run_git_command(["log", "--oneline", "-n", "20", f"{tag}..{branch}"], cwd=lp)
        console.print(log)


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

repos: List[RepoSpec] = [
    RepoSpec(
        name="buildroot",
        repo_url="https://github.com/Opentrons/buildroot.git",
        local_path=Path("./buildroot"),
        default_branch="opentrons-develop",
        external_tag_pattern="v",
        internal_tag_pattern="internal@",
    ),
    RepoSpec(
        name="ot3-firmware",
        repo_url="https://github.com/Opentrons/ot3-firmware.git",
        local_path=Path("./ot3-firmware"),
        default_branch="main",
        external_tag_pattern="v",
        internal_tag_pattern="internal@",
    ),
    RepoSpec(
        name="oe-core",
        repo_url="https://github.com/Opentrons/oe-core.git",
        local_path=Path("./oe-core"),
        default_branch="main",
        external_tag_pattern="v",
        internal_tag_pattern="internal@",
    ),
    RepoSpec(
        name="opentrons",
        repo_url="https://github.com/Opentrons/opentrons.git",
        local_path=Path("./opentrons"),
        default_branch="edge",
        external_tag_pattern="v",
        internal_tag_pattern="ot3@",
    ),
]


def main() -> None:
    """Prompt for release info, sync repos, and print summary + appropriate tables."""
    release_type = Prompt.ask("Release type", choices=["internal", "external"], default="external")
    stability = Prompt.ask("Stability", choices=["stable", "unstable"], default="unstable")
    version = Prompt.ask("Base version", default="v8.4.0")
    if not version.startswith("v"):
        version = f"v{version}"

    console.print(f"🛠 Release: [bold]{release_type}[/], " f"Stability: [bold]{stability}[/], " f"Version: [bold]{version}[/]\n")

    # Parallel sync & collect
    results: Dict[str, RepoState] = {}
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_repo, r, version): r for r in repos}
        for future in as_completed(futures):
            repo = futures[future]
            try:
                results[repo.name] = future.result()
                console.log(f"[green]✅ {repo.name} synced[/]")
            except Exception as err:
                console.log(f"[red]❌ {repo.name} failed: {err}[/]")

    # 1) Latest-tags summary for selected channel on chore_release if present
    summary = Table(title="Latest Tags Summary", show_lines=True)
    summary.add_column("Repo", style="bold")
    summary.add_column("Pattern")
    summary.add_column("Latest Tag")
    summary.add_column("Branch")

    for repo in repos:
        st = results.get(repo.name)
        if not st:
            continue

        pattern = repo.external_tag_pattern if release_type == "external" else repo.internal_tag_pattern
        chore = f"chore_release-{version.lstrip('v')}"
        branch = chore if chore in st.branch_tags else repo.default_branch
        tags = st.branch_tags[branch].get(pattern, [])
        tag = tags[0] if tags else None

        summary.add_row(
            repo.name,
            pattern,
            tag or "[italic]None[/italic]",
            branch,
        )

    console.print(summary)

    # 2) Table + logs for chosen channel
    if release_type == "external":
        print_external_table(results, repos, version)
        for repo in repos:
            st = results.get(repo.name)
            if not st:
                continue
            pat = repo.external_tag_pattern
            chore = f"chore_release-{version.lstrip('v')}"
            branch = chore if chore in st.branch_tags else repo.default_branch
            tags = st.branch_tags[branch].get(pat, [])
            tag = tags[0] if tags else None
            if tag:
                show_changes_since_tag(repo, branch, tag)
    else:
        print_internal_table(results, repos, version)
        for repo in repos:
            st = results.get(repo.name)
            if not st:
                continue
            pat = repo.internal_tag_pattern
            chore = f"chore_release-{version.lstrip('v')}"
            branch = chore if chore in st.branch_tags else repo.default_branch
            tags = st.branch_tags[branch].get(pat, [])
            tag = tags[0] if tags else None
            if tag:
                show_changes_since_tag(repo, branch, tag)


if __name__ == "__main__":
    main()
