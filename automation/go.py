from __future__ import annotations

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple, cast
from zoneinfo import ZoneInfo

import semver
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


@dataclass(frozen=True)
class TagPlan:
    """Whether a repo needs a new tag and what to create if so."""

    needs_tag: bool
    latest_tag: Optional[str]
    next_tag: Optional[str]
    branch: str
    reason: str


# ------------------------------------------------------------------------------
# OT-2 calendar semver (internal and external use different patch schemes)
# ------------------------------------------------------------------------------


OT3_FIRMWARE_EXTERNAL_TAG_RE = re.compile(r"^v(\d+)$")
OT3_FIRMWARE_INTERNAL_TAG_RE = re.compile(r"^internal@v(\d+)$")
OT2_RELEASE_TZ = ZoneInfo("America/New_York")
OT2_MONTH_CAP = r"([1-9]|1[0-2])"
OT2_INTERNAL_VERSION_RE = re.compile(rf"^(\d{{2}})\.{OT2_MONTH_CAP}\.(\d+)(?:-(alpha|beta))?$")
OT2_EXTERNAL_VERSION_RE = re.compile(rf"^(\d{{2}})\.{OT2_MONTH_CAP}\.([0-9])(?:-(alpha|beta)\.(\d+))?$")
OT2_STABILITIES = ("stable", "alpha", "beta")
FLEX_STABILITIES = ("stable", "unstable")
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


def ot2_prerelease_for_stability(stability: str) -> Optional[str]:
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
    for prefix in ("internal@", "ot3@", "v"):
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
) -> str:
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
    return next_tag


def format_tag_commands(next_tag: str, release_version: str) -> Tuple[str, str, str]:
    """Return create, verify, and push commands for an annotated release tag."""
    create = f"git tag -a {next_tag} -m 'chore(release): {release_version}'"
    verify = f"git log {next_tag} --oneline -n 10"
    push = f"git push origin {next_tag}"
    return create, verify, push


def release_branch_for_repo(state: RepoState, repo: RepoSpec, version: str) -> str:
    """Return chore_release when present, otherwise the repo default branch."""
    chore = chore_release_branch(version)
    return chore if chore in state.branch_tags else repo.default_branch


def branch_head_commit(repo: RepoSpec, branch: str) -> str:
    """Return the commit hash at the tip of a local branch."""
    return run_git_command(["rev-parse", branch], cwd=repo.local_path)


def tag_commit(repo: RepoSpec, tag: str) -> str:
    """Return the commit hash an annotated or lightweight tag points to."""
    return run_git_command(["rev-list", "-n", "1", tag], cwd=repo.local_path)


def latest_channel_tag(state: RepoState, repo: RepoSpec, branch: str, release_type: str) -> Optional[str]:
    """Return the newest tag on branch for the selected release channel."""
    pattern = repo.external_tag_pattern if release_type == "external" else repo.internal_tag_pattern
    tags = state.branch_tags.get(branch, {}).get(pattern, [])
    return tags[0] if tags else None


def needs_new_tag(repo: RepoSpec, branch: str, latest_tag: Optional[str]) -> bool:
    """Return True when branch HEAD is ahead of the latest channel tag."""
    if latest_tag is None:
        return True
    return branch_head_commit(repo, branch) != tag_commit(repo, latest_tag)


def tags_merged_on_branch(state: RepoState, branch: str) -> List[str]:
    """Return all tags collected for a branch across channel patterns."""
    tags: List[str] = []
    for pattern_tags in state.branch_tags.get(branch, {}).values():
        tags.extend(pattern_tags)
    return tags


def next_alpha_tag(tag_prefix: str, tags: List[str]) -> str:
    """Return the next tag for a fixed alpha prefix such as v8.5.0-alpha."""
    matching = [tag for tag in tags if tag.startswith(tag_prefix)]
    numbers: List[int] = []
    for tag in matching:
        match = re.match(rf"{re.escape(tag_prefix)}(\d+)", tag)
        if match is not None:
            numbers.append(int(match.group(1)))
    next_num = max(numbers) + 1 if numbers else 0
    return f"{tag_prefix}{next_num}"


def next_alpha_number(tag_prefix: str, tags: List[str]) -> int:
    """Return the next alpha build number for a fixed alpha prefix."""
    matching = [tag for tag in tags if tag.startswith(tag_prefix)]
    numbers: List[int] = []
    for tag in matching:
        match = re.match(rf"{re.escape(tag_prefix)}(\d+)", tag)
        if match is not None:
            numbers.append(int(match.group(1)))
    return max(numbers) + 1 if numbers else 0


SEMVER_BASE_RE = re.compile(r"^(\d+\.\d+\.\d+)")


def semver_base_from_tag(tag: str) -> str:
    """Parse the X.Y.Z base from a release tag after stripping its prefix."""
    clean = strip_tag_version(tag)
    match = SEMVER_BASE_RE.match(clean)
    if match is None:
        raise ValueError(f"Cannot parse semver base from {tag}")
    return match.group(1)


def flex_release_semver_base(version: str) -> str:
    """Normalize the prompted Flex base version to X.Y.Z semver."""
    clean = version.lstrip("v")
    match = SEMVER_BASE_RE.match(clean)
    if match is None:
        raise ValueError(f"Invalid Flex base version: {version}")
    return match.group(1)


def get_next_oe_core_tag_command(
    state: RepoState,
    branch: str,
    release_type: str,
    stability: str,
    internal_semver_base: Optional[str] = None,
    internal_alpha_number: Optional[int] = None,
) -> str:
    """Suggest the next oe-core tag from tags merged into the release branch."""
    branch_tags = tags_merged_on_branch(state, branch)

    if release_type == "internal":
        if internal_semver_base is None:
            internal_tags = state.branch_tags.get(branch, {}).get("internal@", [])
            if not internal_tags:
                raise ValueError("No internal@ tags merged into branch")
            base = semver_base_from_tag(internal_tags[0])
        else:
            base = internal_semver_base

        if stability == "unstable":
            alpha_num = (
                internal_alpha_number
                if internal_alpha_number is not None
                else next_alpha_number(f"internal@{base}-alpha.", branch_tags)
            )
            return f"internal@{base}-alpha.{alpha_num}"

        candidate = f"internal@{base}"
        if candidate not in branch_tags:
            return candidate
        next_version = semver.VersionInfo.parse(base).bump_patch()
        return f"internal@{next_version}"

    external_tags = state.branch_tags.get(branch, {}).get("v", [])
    if not external_tags:
        raise ValueError("No external v* tags merged into branch")

    latest = external_tags[0]
    next_version = semver.VersionInfo.parse(strip_tag_version(latest)).bump_patch()
    return f"v{next_version}"


def get_next_flex_app_tag_command(
    state: RepoState,
    branch: str,
    release_type: str,
    stability: str,
    version: str,
) -> str:
    """Suggest the next opentrons tag for Flex (ot3@ internal, v external)."""
    branch_tags = tags_merged_on_branch(state, branch)

    if release_type == "internal":
        base = flex_release_semver_base(version)
        if stability == "unstable":
            alpha_num = next_alpha_number(f"ot3@{base}-alpha.", branch_tags)
            return f"ot3@{base}-alpha.{alpha_num}"

        candidate = f"ot3@{base}"
        if candidate not in branch_tags:
            return candidate
        next_version = semver.VersionInfo.parse(base).bump_patch()
        return f"ot3@{next_version}"

    release_version = version if version.startswith("v") else f"v{version}"
    if stability == "unstable":
        return next_alpha_tag(f"{release_version}-alpha.", branch_tags)

    matching = [tag for tag in branch_tags if tag.startswith(release_version)]
    if release_version not in matching:
        return release_version
    raise ValueError(f"Tag {release_version} already exists on {branch}")


def max_ot3_firmware_tag_number(state: RepoState, branch: str, release_type: str) -> int:
    """Return the highest integer firmware tag number merged into a branch."""
    pattern = "v" if release_type == "external" else "internal@"
    tag_re = OT3_FIRMWARE_EXTERNAL_TAG_RE if release_type == "external" else OT3_FIRMWARE_INTERNAL_TAG_RE
    numbers: List[int] = []
    for tag in state.branch_tags.get(branch, {}).get(pattern, []):
        match = tag_re.match(tag)
        if match is not None:
            numbers.append(int(match.group(1)))
    if not numbers:
        raise ValueError(f"No {pattern}* tags merged into branch")
    return max(numbers)


def get_next_ot3_firmware_tag_command(
    state: RepoState,
    branch: str,
    release_type: str,
) -> str:
    """Suggest the next ot3-firmware tag (vN or internal@vN) from branch tags."""
    next_num = max_ot3_firmware_tag_number(state, branch, release_type) + 1
    if release_type == "external":
        return f"v{next_num}"
    return f"internal@v{next_num}"


def flex_internal_alpha_from_opentrons(
    results: Dict[str, RepoState],
    version: str,
    stability: str,
) -> Optional[int]:
    """Return the coordinated internal alpha number derived from opentrons ot3@ tags."""
    if stability != "unstable":
        return None

    app_repo = repo_by_name("opentrons")
    app_state = results.get(app_repo.name)
    if app_state is None:
        return None

    branch = release_branch_for_repo(app_state, app_repo, version)
    base = flex_release_semver_base(version)
    branch_tags = tags_merged_on_branch(app_state, branch)
    return next_alpha_number(f"ot3@{base}-alpha.", branch_tags)


def get_next_stack_repo_tag(
    repo: RepoSpec,
    state: RepoState,
    branch: str,
    version: str,
    release_type: str,
    stability: str,
    release_path: ReleasePath,
    results: Optional[Dict[str, RepoState]] = None,
) -> str:
    """Suggest the next tag for a stack repo that is not the app monorepo."""
    if repo.name == "buildroot":
        return get_next_ot2_tag_command(
            repo,
            version,
            release_type,
            state,
            branch,
            "alpha" if stability == "alpha" else "beta" if stability == "beta" else "stable",
        )
    if repo.name == "oe-core":
        internal_base: Optional[str] = None
        internal_alpha: Optional[int] = None
        if release_type == "internal" and release_path.name == "flex":
            internal_base = flex_release_semver_base(version)
            internal_alpha = flex_internal_alpha_from_opentrons(results, version, stability) if results is not None else None
        return get_next_oe_core_tag_command(
            state,
            branch,
            release_type,
            stability,
            internal_base,
            internal_alpha,
        )
    if repo.name == "ot3-firmware":
        return get_next_ot3_firmware_tag_command(state, branch, release_type)
    raise ValueError(f"No tag suggestion logic for {repo.name}")


def get_stack_repo_tag_plan(
    repo: RepoSpec,
    state: RepoState,
    version: str,
    release_type: str,
    stability: str,
    release_path: ReleasePath,
    results: Optional[Dict[str, RepoState]] = None,
) -> TagPlan:
    """Decide whether a stack repo needs a tag and what it should be."""
    branch = release_branch_for_repo(state, repo, version)
    latest_tag = latest_channel_tag(state, repo, branch, release_type)
    needs_tag = needs_new_tag(repo, branch, latest_tag)

    if not needs_tag:
        return TagPlan(
            needs_tag=False,
            latest_tag=latest_tag,
            next_tag=None,
            branch=branch,
            reason=f"{branch} matches {latest_tag}",
        )

    next_tag = get_next_stack_repo_tag(repo, state, branch, version, release_type, stability, release_path, results)
    reason = f"commits on {branch} since {latest_tag or 'no prior channel tag'}"
    return TagPlan(
        needs_tag=True,
        latest_tag=latest_tag,
        next_tag=next_tag,
        branch=branch,
        reason=reason,
    )


def release_version_label(
    release_path: ReleasePath,
    release_type: str,
    version: str,
    app_tag: Optional[str],
) -> str:
    """Return the monorepo release version referenced in stack repo tag messages."""
    if app_tag is not None:
        return app_tag

    repo = repo_by_name(release_path.taggable_repo)
    prefix = repo.external_tag_pattern if release_type == "external" else repo.internal_tag_pattern
    clean = version.lstrip("v")
    if prefix in {"internal@", "ot3@"}:
        return f"{prefix}{clean}"
    return version if version.startswith("v") else f"v{version}"


def print_suggested_tag_block(label: str, next_tag: str, release_version: str) -> None:
    """Print a header panel and git commands for creating and pushing a tag."""
    create, verify, push = format_tag_commands(next_tag, release_version)
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{next_tag}[/]\n\n"
            f"[bold green]Create:[/] {create}\n"
            f"[bold green]Verify:[/] {verify}\n"
            f"[bold green]Push:[/]   {push}",
            title=f"Suggested {label}",
            border_style="green",
            padding=(1, 2),
        )
    )


def print_tag_plan(repo: RepoSpec, plan: TagPlan, release_version: str) -> None:
    """Print whether a repo needs a tag and the commands to create and push it."""
    if not plan.needs_tag:
        console.print(f"[green]No new tag needed[/] on [bold]{plan.branch}[/] ({plan.reason})")
        return

    console.print(f"[yellow]New tag needed[/] on [bold]{plan.branch}[/] ({plan.reason})")
    if plan.latest_tag:
        show_changes_since_tag(repo, plan.branch, plan.latest_tag)

    if plan.next_tag is None:
        console.print("[red]Could not determine next tag[/]")
        return

    print_suggested_tag_block(f"{repo.name} tag", plan.next_tag, release_version)


def get_next_tag_command(
    repo: RepoSpec,
    version: str,
    stability: str,
    state: RepoState,
    branch: str,
    release_type: str = "external",
    release_path: Optional[ReleasePath] = None,
) -> str:
    """Return the next annotated tag name for the app repo."""
    if release_path is not None and release_path.name == "ot2":
        ot2_stability: Ot2Stability = "alpha" if stability == "alpha" else "beta" if stability == "beta" else "stable"
        return get_next_ot2_tag_command(
            repo,
            version,
            release_type,
            state,
            branch,
            ot2_stability,
        )

    if release_path is not None and release_path.name == "flex":
        return get_next_flex_app_tag_command(state, branch, release_type, stability, version)

    branch_tags = tags_merged_on_branch(state, branch)
    if stability == "unstable":
        return next_alpha_tag(f"{version}-alpha.", branch_tags)

    matching = [tag for tag in branch_tags if tag.startswith(version)]
    if version not in matching:
        return version
    raise ValueError(f"Tag {version} already exists on {branch}")


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
    stack_tag_repos: Tuple[str, ...]


STACK_REPO_LABELS: Dict[str, str] = {
    "oe-core": "robot OS",
    "ot3-firmware": "firmware",
    "buildroot": "robot OS",
}


RELEASE_PATHS: Dict[str, ReleasePath] = {
    "flex": ReleasePath(
        name="flex",
        label="Flex",
        repo_names=frozenset({"opentrons", "oe-core", "ot3-firmware"}),
        taggable_repo="opentrons",
        stack_tag_repos=("ot3-firmware", "oe-core"),
    ),
    "ot2": ReleasePath(
        name="ot2",
        label="OT-2",
        repo_names=frozenset({"opentrons-ot2", "buildroot"}),
        taggable_repo="opentrons-ot2",
        stack_tag_repos=("buildroot",),
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
    default_version = default_release_version(release_path, release_type)
    if release_path.name == "ot2":
        if release_type == "external":
            prompt_label = "Base version (OT-2 external YY.M.N)"
            while True:
                version = Prompt.ask(prompt_label, default=default_version)
                try:
                    return normalize_release_version(release_path, release_type, version)
                except ValueError as err:
                    console.print(f"[red]Invalid OT-2 external version: {err}[/]")
                    continue

        while True:
            version = Prompt.ask("Base version (OT-2 internal YY.M.DNN)", default=default_version)
            try:
                return normalize_release_version(release_path, release_type, version)
            except ValueError as err:
                console.print(f"[red]Invalid OT-2 internal version: {err}[/]")
                continue

    version = Prompt.ask("Base version", default=default_version)
    return normalize_release_version(release_path, release_type, version)


def default_robot_path() -> str:
    """Return the default robot path when no CLI flag is given."""
    return "flex"


def default_release_type() -> str:
    """Return the default release channel when no CLI flag is given."""
    return "external"


def default_stability(release_path: ReleasePath) -> str:
    """Return the default stability choice for a robot path."""
    return "stable" if release_path.name == "ot2" else "unstable"


def default_release_version(release_path: ReleasePath, release_type: str) -> str:
    """Return the default base version for a robot path and channel."""
    if release_path.name == "ot2":
        if release_type == "external":
            return ot2_external_version_for_month()
        return ot2_internal_version_for_date()
    return "v8.5.0"


def normalize_release_version(release_path: ReleasePath, release_type: str, version: str) -> str:
    """Normalize and validate a base release version string."""
    if release_path.name == "ot2":
        clean = version.lstrip("v")
        if release_type == "external":
            decode_ot2_external_version(clean)
        else:
            decode_ot2_internal_version(clean)
        return clean

    normalized = version if version.startswith("v") else f"v{version.lstrip('v')}"
    return normalized


def validate_stability(release_path: ReleasePath, stability: str) -> None:
    """Raise ValueError when stability is invalid for the selected robot path."""
    allowed = OT2_STABILITIES if release_path.name == "ot2" else FLEX_STABILITIES
    if stability not in allowed:
        raise ValueError(f"Stability must be one of {', '.join(allowed)} for {release_path.label}")


def build_parser() -> argparse.ArgumentParser:
    """Configure CLI arguments for non-interactive and agentic use."""
    parser = argparse.ArgumentParser(
        description="Sync stack repos and print release tagging guidance.",
    )
    parser.add_argument(
        "--path",
        choices=list(RELEASE_PATHS),
        help="Robot release path (default: flex, or prompt).",
    )
    parser.add_argument(
        "--release-type",
        choices=["internal", "external"],
        help="Release channel (default: external, or prompt).",
    )
    parser.add_argument(
        "--stability",
        help="OT-2: stable, alpha, or beta. Flex: stable or unstable (alpha builds).",
    )
    parser.add_argument(
        "--version",
        help="Base release version (Flex: vX.Y.Z; OT-2 internal: YY.M.DNN; OT-2 external: YY.M.N).",
    )
    parser.add_argument(
        "--skip-assumptions",
        action="store_true",
        help="Do not print the assumptions panel.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; use defaults for omitted options.",
    )
    return parser


def resolve_robot_path_name(args: argparse.Namespace) -> str:
    """Resolve robot path from CLI args, defaults, or prompt."""
    if args.path is not None:
        return args.path
    if args.non_interactive:
        return default_robot_path()
    return Prompt.ask("Robot path", choices=list(RELEASE_PATHS), default=default_robot_path())


def resolve_release_type(args: argparse.Namespace) -> str:
    """Resolve release channel from CLI args, defaults, or prompt."""
    if args.release_type is not None:
        return args.release_type
    if args.non_interactive:
        return default_release_type()
    return Prompt.ask("Release type", choices=["internal", "external"], default=default_release_type())


def resolve_stability(release_path: ReleasePath, args: argparse.Namespace) -> str:
    """Resolve stability from CLI args, defaults, or prompt."""
    if args.stability is not None:
        try:
            validate_stability(release_path, args.stability)
        except ValueError as err:
            console.print(f"[red]{err}[/]")
            sys.exit(1)
        return args.stability

    if args.non_interactive:
        return default_stability(release_path)

    choices = list(OT2_STABILITIES if release_path.name == "ot2" else FLEX_STABILITIES)
    return Prompt.ask("Stability", choices=choices, default=default_stability(release_path))


def resolve_release_version(release_path: ReleasePath, release_type: str, args: argparse.Namespace) -> str:
    """Resolve base version from CLI args, defaults, or prompt."""
    if args.version is not None:
        try:
            return normalize_release_version(release_path, release_type, args.version)
        except ValueError as err:
            console.print(f"[red]Invalid version: {err}[/]")
            sys.exit(1)
    if args.non_interactive:
        return default_release_version(release_path, release_type)
    return prompt_release_version(release_path, release_type)


ASSUMPTIONS_MARKDOWN = Markdown(
    """
##Tool Assumptions

- All tags we care about are *annotated*
  - example app tag: `git tag -a v8.4.0-alpha.8 -m 'chore(release): v8.4.0-alpha.8'`
  - stack repo tags use their own name but reference the monorepo release in the message:
    `git tag -a v0.10.1 -m 'chore(release): v8.4.0-alpha.8'`
    - This gives the tag a message, creator, and date
    - Then we use `git tag -l --sort=-creatordate` to get the latest tag
- Across every robot-stack repo, isolation branches for a release cycle look like: `chore_release-<version>`
"""
)


def print_assumptions_panel() -> None:
    """Print the release tooling assumptions panel."""
    console.print(Panel(ASSUMPTIONS_MARKDOWN, title="🔧 Assumptions", border_style="cyan"))


def repo_by_name(name: str) -> RepoSpec:
    """Return the RepoSpec for a known repo name."""
    for repo in repos:
        if repo.name == name:
            return repo
    raise KeyError(f"Unknown repo: {name}")


def compute_app_tag(
    release_path: ReleasePath,
    results: Dict[str, RepoState],
    version: str,
    release_type: str,
    stability: str,
) -> Optional[str]:
    """Return the next suggested app monorepo tag without printing."""
    repo = repo_by_name(release_path.taggable_repo)
    state = results.get(repo.name)
    if state is None:
        return None

    branch = release_branch_for_repo(state, repo, version)
    try:
        return get_next_tag_command(
            repo,
            version,
            stability,
            state,
            branch,
            release_type,
            release_path,
        )
    except Exception as err:
        console.print(f"[yellow]No next tag for {repo.name}: {err}[/]")
        return None


def print_app_tag_section(
    release_path: ReleasePath,
    results: Dict[str, RepoState],
    version: str,
    release_type: str,
    stability: str,
    release_version: str,
) -> None:
    """Print change summary and tag commands for the app repo."""
    repo = repo_by_name(release_path.taggable_repo)
    state = results.get(repo.name)
    if state is None:
        return

    pattern = repo.external_tag_pattern if release_type == "external" else repo.internal_tag_pattern
    branch = release_branch_for_repo(state, repo, version)
    tags = state.branch_tags[branch].get(pattern, [])
    latest_tag = tags[0] if tags else None
    if latest_tag:
        show_changes_since_tag(repo, branch, latest_tag)

    next_tag = compute_app_tag(release_path, results, version, release_type, stability)
    if next_tag is None:
        return
    print_suggested_tag_block("app tag", next_tag, release_version)


def stack_repo_push_order(release_path: ReleasePath) -> List[str]:
    """Return dependent stack repos in the order their tags should be pushed."""
    return list(release_path.stack_tag_repos)


def print_tag_push_order_note(release_path: ReleasePath) -> None:
    """Remind the operator to push dependent repo tags before the app monorepo tag."""
    ordered = stack_repo_push_order(release_path)
    lines = [
        "Push annotated tags in this order. Dependent stack repos first, app monorepo last.",
        "",
    ]
    step = 1
    for repo_name in ordered:
        label = STACK_REPO_LABELS.get(repo_name, repo_name)
        lines.append(f"{step}. [bold]{repo_name}[/] ({label}), if a new tag is needed")
        step += 1
    lines.append(f"{step}. [bold]{release_path.taggable_repo}[/] (app), always last")
    console.print()
    console.print(Panel("\n".join(lines), title="Tag push order", border_style="yellow", padding=(1, 2)))


def print_stack_repo_tag_section(
    repo_name: str,
    release_path: ReleasePath,
    results: Dict[str, RepoState],
    version: str,
    release_type: str,
    stability: str,
    release_version: str,
) -> None:
    """Print whether a stack repo needs a tag and the commands to push it."""
    repo = repo_by_name(repo_name)
    state = results.get(repo.name)
    if state is None:
        console.print(f"[red]Missing sync state for {repo.name}[/]")
        return

    plan = get_stack_repo_tag_plan(repo, state, version, release_type, stability, release_path, results)
    print_tag_plan(repo, plan, release_version)


def print_track_builds_command(release_path: ReleasePath, app_tag: str) -> None:
    """Print follow-up commands after the app tag has been pushed."""
    from automation.track_builds import RobotPath, track_builds_invocation

    path = cast(RobotPath, release_path.name)
    track_command = track_builds_invocation(path, app_tag, wait=True)
    invalidate_command = f"just invalidate-cloudfront --path {path} --tag {app_tag}"
    console.print()
    console.print(
        Panel(
            "After pushing the app tag above:\n\n"
            f"1. Track app, kickoff, and robot OS CI:\n[bold cyan]{track_command}[/]\n\n"
            f"2. After builds finish, print CloudFront invalidation command:\n[bold cyan]{invalidate_command}[/]",
            title="Next steps",
            border_style="blue",
            padding=(1, 2),
        )
    )


def run_release(
    release_path: ReleasePath,
    release_type: str,
    stability: str,
    version: str,
) -> None:
    """Sync repos and print release tables, tag guidance, and follow-up commands."""
    active_repos = repos_for_path(release_path)
    sync_repos = repos_to_sync(release_path)

    console.print(
        f"🛠 Path: [bold]{release_path.label}[/], Release: [bold]{release_type}[/], "
        f"Stability: [bold]{stability}[/], Version: [bold]{version}[/]\n"
    )

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

    if release_type == "external":
        print_external_table(results, active_repos, version)
    else:
        print_internal_table(results, active_repos, version)

    print_tag_push_order_note(release_path)

    app_tag = compute_app_tag(release_path, results, version, release_type, stability)
    release_version = release_version_label(release_path, release_type, version, app_tag)

    for repo_name in release_path.stack_tag_repos:
        label = STACK_REPO_LABELS.get(repo_name, repo_name)
        console.rule(f"{repo_name} ({label}) tag")
        print_stack_repo_tag_section(
            repo_name,
            release_path,
            results,
            version,
            release_type,
            stability,
            release_version,
        )

    console.rule(f"{release_path.taggable_repo} (app) tag")
    print_app_tag_section(release_path, results, version, release_type, stability, release_version)

    if app_tag is not None:
        print_track_builds_command(release_path, app_tag)


def main() -> None:
    """Sync stack repos and print release tagging guidance."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.skip_assumptions:
        print_assumptions_panel()

    robot_path_name = resolve_robot_path_name(args)
    release_path = RELEASE_PATHS[robot_path_name]
    release_type = resolve_release_type(args)
    stability = resolve_stability(release_path, args)
    version = resolve_release_version(release_path, release_type, args)

    run_release(release_path, release_type, stability, version)


if __name__ == "__main__":
    main()
