from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple
from zoneinfo import ZoneInfo

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
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
        chore = chore_release_branch(version)
        if branch_exists(self.repo_url, chore):
            branches.append(chore)
        return branches


@dataclass
class RepoState:
    branch_tags: Dict[str, Dict[str, List[str]]] = field(default_factory=dict)
    overall_tags: Dict[str, Optional[str]] = field(default_factory=dict)


# ------------------------------------------------------------------------------
# OT-2 calendar semver (internal and external use different patch schemes)
# ------------------------------------------------------------------------------


OT2_RELEASE_TZ = ZoneInfo("America/New_York")
OT2_MONTH_CAP = r"([1-9]|1[0-2])"
OT2_INTERNAL_VERSION_RE = re.compile(rf"^(\d{{2}})\.{OT2_MONTH_CAP}\.(\d+)(?:-(alpha|beta))?$")
OT2_EXTERNAL_VERSION_RE = re.compile(rf"^(\d{{2}})\.{OT2_MONTH_CAP}\.([0-9])(?:-(alpha|beta)\.(\d+))?$")
Ot2Stability = Literal["stable", "alpha", "beta"]


def ot2_release_date_today() -> date:
    """Return today's calendar date in US Eastern, used for OT-2 version components."""
    return datetime.now(OT2_RELEASE_TZ).date()


def encode_ot2_internal_version(year: int, month: int, day: int, build_num: int = 1) -> str:
    """Encode internal semver: YY.M.DNN where DNN = day * 100 + same-day build number."""
    if build_num < 1 or build_num > 99:
        raise ValueError("build_num must be between 1 and 99")
    if day < 1 or day > 31:
        raise ValueError("day must be between 1 and 31")

    yy = year % 100
    patch = day * 100 + build_num
    return f"{yy}.{month}.{patch}"


def decode_ot2_internal_version(version: str) -> Tuple[int, int, int, int, Optional[str]]:
    """Decode internal semver into (year, month, day, build_num, prerelease)."""
    clean = version.lstrip("v")
    match = OT2_INTERNAL_VERSION_RE.match(clean)
    if match is None:
        raise ValueError(f"Invalid OT-2 internal version: {version}")

    yy = int(match.group(1))
    month = int(match.group(2))
    patch = int(match.group(3))
    prerelease = match.group(4)
    year = 2000 + yy

    if 100 <= patch <= 999:
        day = patch // 100
        build_num = patch % 100
        if 1 <= day <= 9 and build_num >= 1:
            return year, month, day, build_num, prerelease

    if 1000 <= patch <= 3199:
        day = patch // 100
        build_num = patch % 100
        if 10 <= day <= 31 and build_num >= 1:
            return year, month, day, build_num, prerelease

    raise ValueError(f"Invalid OT-2 internal version patch component: {version}")


def encode_ot2_external_version(
    year: int,
    month: int,
    release_num: int = 0,
    prerelease: Optional[str] = None,
    prerelease_num: Optional[int] = None,
) -> str:
    """Encode external semver: YY.M.N with optional -alpha.N or -beta.N."""
    if release_num < 0 or release_num > 9:
        raise ValueError("release_num must be between 0 and 9")
    yy = year % 100
    version = f"{yy}.{month}.{release_num}"
    if prerelease is not None:
        if prerelease_num is None:
            raise ValueError("prerelease_num required when prerelease is set")
        version = f"{version}-{prerelease}.{prerelease_num}"
    return version


def decode_ot2_external_version(
    version: str,
) -> Tuple[int, int, int, Optional[str], Optional[int]]:
    """Decode external semver into (year, month, release_num, prerelease, prerelease_num)."""
    clean = version.lstrip("v")
    match = OT2_EXTERNAL_VERSION_RE.match(clean)
    if match is None:
        raise ValueError(f"Invalid OT-2 external version: {version}")

    yy = int(match.group(1))
    month = int(match.group(2))
    release_num = int(match.group(3))
    prerelease = match.group(4)
    prerelease_num = int(match.group(5)) if match.group(5) is not None else None
    return 2000 + yy, month, release_num, prerelease, prerelease_num


def ot2_internal_version_for_date(release_date: date | None = None, build_num: int = 1) -> str:
    """Return internal semver for a calendar date (Eastern by default)."""
    if release_date is None:
        release_date = ot2_release_date_today()
    return encode_ot2_internal_version(release_date.year, release_date.month, release_date.day, build_num)


def ot2_external_version_for_month(release_date: date | None = None, release_num: int = 0) -> str:
    """Return external semver for the calendar month (Eastern), N starting at 0."""
    if release_date is None:
        release_date = ot2_release_date_today()
    return encode_ot2_external_version(release_date.year, release_date.month, release_num)


def ot2_prerelease_for_stability(stability: Ot2Stability) -> Optional[str]:
    """Map OT-2 internal stability choice to a bare semver prerelease suffix, if any."""
    if stability == "stable":
        return None
    return stability


# Backward-compatible aliases
encode_ot2_version = encode_ot2_internal_version
decode_ot2_version = decode_ot2_internal_version
ot2_version_for_date = ot2_internal_version_for_date


def strip_tag_version(tag: str) -> str:
    """Remove known tag prefixes so version parsing can inspect the semver."""
    for prefix in ("internal@", "v"):
        if tag.startswith(prefix):
            return tag[len(prefix) :]
    return tag


def chore_release_branch(version: str) -> str:
    """Return the chore_release branch name for a release version."""
    return f"chore_release-{version.lstrip('v')}"


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


def get_next_ot2_tag_command(
    repo: RepoSpec,
    version: str,
    release_type: str,
    state: RepoState,
    branch: str,
    stability: Ot2Stability = "stable",
) -> Tuple[str, str]:
    """Return the next OT-2 semver tag for the selected release channel and stability."""
    tag_prefix = "v" if release_type == "external" else "internal@"

    if release_type == "external":
        year, month, release_num, _, _ = decode_ot2_external_version(version)
        if stability == "stable":
            same_month_nums: List[int] = []
            for pat_tags in state.branch_tags.get(branch, {}).values():
                for tag in pat_tags:
                    try:
                        clean = strip_tag_version(tag)
                        tag_year, tag_month, tag_n, tag_pre, _ = decode_ot2_external_version(clean)
                    except ValueError:
                        continue
                    if (tag_year, tag_month) == (year, month) and tag_pre is None:
                        same_month_nums.append(tag_n)
            next_num = max(same_month_nums, default=-1) + 1
            if next_num > 9:
                raise ValueError("More than 10 external stable releases this month (N > 9)")
            next_version = encode_ot2_external_version(year, month, next_num)
        else:
            same_pre_nums: List[int] = []
            for pat_tags in state.branch_tags.get(branch, {}).values():
                for tag in pat_tags:
                    try:
                        clean = strip_tag_version(tag)
                        tag_year, tag_month, tag_n, tag_pre, tag_pre_num = decode_ot2_external_version(clean)
                    except ValueError:
                        continue
                    if (
                        (tag_year, tag_month, tag_n) == (year, month, release_num)
                        and tag_pre == stability
                        and tag_pre_num is not None
                    ):
                        same_pre_nums.append(tag_pre_num)
            next_pre_num = max(same_pre_nums, default=-1) + 1
            next_version = encode_ot2_external_version(year, month, release_num, stability, next_pre_num)
    else:
        year, month, day, _, _ = decode_ot2_internal_version(version)
        expected_prerelease = ot2_prerelease_for_stability(stability)

        same_day_builds: List[int] = []
        for pat_tags in state.branch_tags.get(branch, {}).values():
            for tag in pat_tags:
                try:
                    tag_year, tag_month, tag_day, tag_build, tag_prerelease = decode_ot2_internal_version(strip_tag_version(tag))
                except ValueError:
                    continue
                if (tag_year, tag_month, tag_day) == (year, month, day) and tag_prerelease == expected_prerelease:
                    same_day_builds.append(tag_build)

        next_build = max(same_day_builds, default=0) + 1
        next_version = encode_ot2_internal_version(year, month, day, next_build)
        if expected_prerelease is not None:
            next_version = f"{next_version}-{expected_prerelease}"

    next_tag = f"{tag_prefix}{next_version}"
    cmd = f"git tag -a {next_tag} -m 'chore(release): {next_tag}' && git log --oneline -n 10"
    return cmd, next_tag


def get_next_tag_command(
    repo: RepoSpec,
    version: str,
    stability: str,
    state: RepoState,
    branch: str,
    release_type: str = "external",
    release_path: Optional[ReleasePath] = None,
) -> Tuple[str, str]:
    """Return the git command and next tag name for the next annotated tag."""
    if release_path is not None and release_path.name == "ot2":
        ot2_stability: Ot2Stability = (
            "alpha" if stability == "alpha" else "beta" if stability == "beta" else "stable"
        )
        return get_next_ot2_tag_command(
            repo,
            version,
            release_type,
            state,
            branch,
            ot2_stability,
        )

    # Determine tag pattern
    if stability == "unstable":
        tag_prefix = f"{version}-alpha."
    else:
        tag_prefix = version
    # Find all tags for this pattern
    tags = []
    for pat_tags in state.branch_tags.get(branch, {}).values():
        tags.extend(pat_tags)
    # Filter tags matching the prefix
    matching = [t for t in tags if t.startswith(tag_prefix)]
    # Extract numeric suffix for alpha tags
    if stability == "unstable":
        numbers = []
        for t in matching:
            m = re.match(rf"{re.escape(tag_prefix)}(\d+)", t)
            if m is not None:
                numbers.append(int(m.group(1)))
        next_num = max(numbers) + 1 if numbers else 0
        next_tag = f"{tag_prefix}{next_num}"
    else:
        # For stable, just use the version if not present
        if version not in matching:
            next_tag = version
        else:
            raise ValueError(f"Tag {version} already exists on {branch}")
    # Annotated tag command
    cmd = f"git tag -a {next_tag} -m 'chore(release): {next_tag}' && git log --oneline -n 10"
    return cmd, next_tag


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
        chore = chore_release_branch(version)
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
        chore = chore_release_branch(version)
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
    RepoSpec(
        name="opentrons-ot2",
        repo_url="https://github.com/Opentrons/opentrons-ot2.git",
        local_path=Path("./opentrons-ot2"),
        default_branch="edge",
        external_tag_pattern="v",
        internal_tag_pattern="internal@",
    ),
    RepoSpec(
        name="robot-stack-infra",
        repo_url="https://github.com/Opentrons/robot-stack-infra.git",
        local_path=Path("./robot-stack-infra"),
        default_branch="main",
        external_tag_pattern="release@",
        internal_tag_pattern="release-ci@",
    ),
]


@dataclass(frozen=True)
class ReleasePath:
    """Repos and app tagging behavior for a robot release path."""

    name: str
    label: str
    repo_names: frozenset[str]
    taggable_repo: str


RELEASE_PATHS: Dict[str, ReleasePath] = {
    "flex": ReleasePath(
        name="flex",
        label="Flex",
        repo_names=frozenset({"opentrons", "oe-core", "ot3-firmware"}),
        taggable_repo="opentrons",
    ),
    "ot2": ReleasePath(
        name="ot2",
        label="OT-2",
        repo_names=frozenset({"opentrons-ot2", "buildroot"}),
        taggable_repo="opentrons-ot2",
    ),
}


ALWAYS_SYNC_REPO_NAMES = frozenset({"robot-stack-infra"})


def repos_for_path(path: ReleasePath) -> List[RepoSpec]:
    """Return release-path repo specs, in manifest order."""
    return [repo for repo in repos if repo.name in path.repo_names]


def repos_to_sync(path: ReleasePath) -> List[RepoSpec]:
    """Return all repo specs to clone or pull, including always-synced reference repos."""
    names = path.repo_names | ALWAYS_SYNC_REPO_NAMES
    return [repo for repo in repos if repo.name in names]


def prompt_release_version(release_path: ReleasePath, release_type: str = "external") -> str:
    """Prompt for the base release version appropriate to the selected robot path."""
    if release_path.name == "ot2":
        if release_type == "external":
            default_version = ot2_external_version_for_month()
            prompt_label = "Base version (OT-2 external YY.M.N)"
            while True:
                version = Prompt.ask(prompt_label, default=default_version)
                try:
                    decode_ot2_external_version(version.lstrip("v"))
                except ValueError as err:
                    console.print(f"[red]Invalid OT-2 external version: {err}[/]")
                    continue
                return version.lstrip("v")

        default_version = ot2_internal_version_for_date()
        while True:
            version = Prompt.ask("Base version (OT-2 internal YY.M.DNN)", default=default_version)
            try:
                decode_ot2_internal_version(version.lstrip("v"))
            except ValueError as err:
                console.print(f"[red]Invalid OT-2 internal version: {err}[/]")
                continue
            return version.lstrip("v")

    version = Prompt.ask("Base version", default="v8.5.0")
    if not version.startswith("v"):
        version = f"v{version}"
    return version


def main() -> None:
    """Prompt for release info, sync repos, and print summary + appropriate tables."""
    assumptions_md = Markdown(
        """
##Tool Assumptions

- All tags we care about are *annotated*
  - example `git tag -a v8.4.0-alpha.8 -m 'chore(release): v8.4.0-alpha.8'`
    - This gives the tag a message, creator, and date
    - Then we use `git tag -l --sort=-creatordate` to get the latest tag
- Across every robot-stack repo, isolation branches for a release cycle look like: `chore_release-<version>`
"""
    )

    console.print(Panel(assumptions_md, title="🔧 Assumptions", border_style="cyan"))
    robot_path_name = Prompt.ask("Robot path", choices=list(RELEASE_PATHS), default="flex")
    release_path = RELEASE_PATHS[robot_path_name]
    active_repos = repos_for_path(release_path)
    sync_repos = repos_to_sync(release_path)
    release_type = Prompt.ask("Release type", choices=["internal", "external"], default="external")
    if release_path.name == "ot2":
        stability = Prompt.ask("Stability", choices=["stable", "alpha", "beta"], default="stable")
        version = prompt_release_version(release_path, release_type)
        console.print(
            f"🛠 Path: [bold]{release_path.label}[/], Release: [bold]{release_type}[/], "
            f"Stability: [bold]{stability}[/], Version: [bold]{version}[/]\n"
        )
    else:
        stability = Prompt.ask("Stability", choices=["stable", "unstable"], default="unstable")
        version = prompt_release_version(release_path, release_type)
        console.print(
            f"🛠 Path: [bold]{release_path.label}[/], Release: [bold]{release_type}[/], "
            f"Stability: [bold]{stability}[/], Version: [bold]{version}[/]\n"
        )

    # Parallel sync & collect
    results: Dict[str, RepoState] = {}
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_repo, r, version): r for r in sync_repos}
        for future in as_completed(futures):
            repo = futures[future]
            try:
                results[repo.name] = future.result()
                console.log(f"[green]✅ {repo.name} synced[/]")
            except Exception as err:
                console.log(f"[red]❌ {repo.name} failed: {err}[/]")

    # 1) Latest-tags summary for selected channel on chore_release if present
    summary = Table(title=f"Latest Tags Summary ({release_path.label})", show_lines=True)
    summary.add_column("Repo", style="bold")
    summary.add_column("Pattern")
    summary.add_column("Latest Tag")
    summary.add_column("Branch")

    for repo in active_repos:
        st = results.get(repo.name)
        if not st:
            continue

        pattern = repo.external_tag_pattern if release_type == "external" else repo.internal_tag_pattern
        chore = chore_release_branch(version)
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
        print_external_table(results, active_repos, version)
        for repo in active_repos:
            if repo.name != release_path.taggable_repo:
                continue
            st = results.get(repo.name)
            if not st:
                continue
            pat = repo.external_tag_pattern
            chore = chore_release_branch(version)
            branch = chore if chore in st.branch_tags else repo.default_branch
            tags = st.branch_tags[branch].get(pat, [])
            tag = tags[0] if tags else None
            if tag:
                show_changes_since_tag(repo, branch, tag)
            # Print next tag command for taggable app repos
            try:
                cmd, next_tag = get_next_tag_command(repo, version, stability, st, branch, release_type, release_path)
                console.print(f"[bold green]Next tag command for {repo.name}:[/] {cmd}")
            except Exception as e:
                console.print(f"[yellow]No next tag for {repo.name}: {e}")
    else:
        print_internal_table(results, active_repos, version)
        for repo in active_repos:
            if repo.name != release_path.taggable_repo:
                continue
            st = results.get(repo.name)
            if not st:
                continue
            pat = repo.internal_tag_pattern
            chore = chore_release_branch(version)
            branch = chore if chore in st.branch_tags else repo.default_branch
            tags = st.branch_tags[branch].get(pat, [])
            tag = tags[0] if tags else None
            if tag:
                show_changes_since_tag(repo, branch, tag)
            # Print next tag command for taggable app repos
            try:
                cmd, next_tag = get_next_tag_command(repo, version, stability, st, branch, release_type, release_path)
                console.print(f"[bold green]Next tag command for {repo.name}:[/] {cmd}")
            except Exception as e:
                console.print(f"[yellow]No next tag for {repo.name}: {e}")


if __name__ == "__main__":
    main()
