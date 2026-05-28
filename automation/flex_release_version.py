"""Infer the active Flex release base version from tags or chore_release branches."""

from __future__ import annotations

import re
from typing import Iterable, Optional

import semver

CHORE_RELEASE_BRANCH_RE = re.compile(r"^chore_release-(?P<version>\d+\.\d+\.\d+)$")
FLEX_APP_TAG_BASE_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)(?:-alpha\.\d+)?$")
FLEX_INTERNAL_APP_TAG_BASE_RE = re.compile(r"^ot3@(?P<version>\d+\.\d+\.\d+)(?:-alpha\.\d+)?$")


def parse_chore_release_version(branch_name: str) -> Optional[str]:
    """Return X.Y.Z when branch_name is a standard chore_release branch."""
    match = CHORE_RELEASE_BRANCH_RE.match(branch_name)
    if match is None:
        return None
    return match.group("version")


def highest_chore_release_version(branch_names: Iterable[str]) -> Optional[str]:
    """Return the highest semver among strict chore_release-X.Y.Z branch names."""
    versions: list[semver.VersionInfo] = []
    for name in branch_names:
        raw = parse_chore_release_version(name)
        if raw is None:
            continue
        versions.append(semver.VersionInfo.parse(raw))
    if not versions:
        return None
    highest = max(versions, key=lambda version: (version.major, version.minor, version.patch))
    return str(highest)


def flex_base_from_app_tags(tags: Iterable[str]) -> Optional[str]:
    """Return the highest vX.Y.Z base seen in Flex external app tags."""
    versions: list[semver.VersionInfo] = []
    for tag in tags:
        match = FLEX_APP_TAG_BASE_RE.match(tag)
        if match is None:
            continue
        versions.append(semver.VersionInfo.parse(match.group("version")))
    if not versions:
        return None
    highest = max(versions, key=lambda version: (version.major, version.minor, version.patch))
    return str(highest)


def flex_base_from_internal_app_tags(tags: Iterable[str]) -> Optional[str]:
    """Return the highest X.Y.Z base seen in Flex internal ot3@ app tags."""
    versions: list[semver.VersionInfo] = []
    for tag in tags:
        match = FLEX_INTERNAL_APP_TAG_BASE_RE.match(tag)
        if match is None:
            continue
        versions.append(semver.VersionInfo.parse(match.group("version")))
    if not versions:
        return None
    highest = max(versions, key=lambda version: (version.major, version.minor, version.patch))
    return str(highest)


def flex_external_default_release_version(
    branch_names: Iterable[str],
    *,
    app_tags: Iterable[str] = (),
) -> Optional[str]:
    """Return the v-prefixed Flex base version inferred from chore_release branches or v* tags."""
    base = highest_chore_release_version(branch_names)
    if base is None:
        base = flex_base_from_app_tags(app_tags)
    if base is None:
        return None
    return f"v{base}"


def flex_internal_default_release_version(
    internal_app_tags: Iterable[str],
) -> Optional[str]:
    """Return the v-prefixed Flex base version inferred from ot3@ tags on the default branch."""
    base = flex_base_from_internal_app_tags(internal_app_tags)
    if base is None:
        return None
    return f"v{base}"


def flex_default_release_version(
    branch_names: Iterable[str],
    *,
    app_tags: Iterable[str] = (),
) -> Optional[str]:
    """Return the v-prefixed Flex base version for external releases."""
    return flex_external_default_release_version(branch_names, app_tags=app_tags)
