"""Per-repo release branch overrides for ``just go``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ReleaseBranchConfig:
    """Optional branch overrides for a release run."""

    app_branch: Optional[str] = None
    stack_branches: Dict[str, str] = field(default_factory=dict)


def parse_stack_branch_override(raw: str) -> tuple[str, str]:
    """Parse ``REPO=BRANCH`` from a CLI ``--stack-branch`` value."""
    if "=" not in raw:
        raise ValueError(f"Expected REPO=BRANCH, got: {raw}")
    repo_name, branch = raw.split("=", maxsplit=1)
    repo_name = repo_name.strip()
    branch = branch.strip()
    if not repo_name or not branch:
        raise ValueError(f"Expected REPO=BRANCH, got: {raw}")
    return repo_name, branch


def parse_stack_branch_overrides(values: Optional[List[str]]) -> Dict[str, str]:
    """Parse repeated ``--stack-branch REPO=BRANCH`` flags."""
    overrides: Dict[str, str] = {}
    if not values:
        return overrides
    for raw in values:
        repo_name, branch = parse_stack_branch_override(raw)
        overrides[repo_name] = branch
    return overrides


def build_release_branch_config(
    *,
    app_branch: Optional[str] = None,
    stack_branch: Optional[List[str]] = None,
) -> ReleaseBranchConfig:
    """Build branch overrides from CLI flag values."""
    return ReleaseBranchConfig(
        app_branch=app_branch.strip() if app_branch else None,
        stack_branches=parse_stack_branch_overrides(stack_branch),
    )
