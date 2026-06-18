"""Classify release tags by stability and find latest tags per pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from automation.ot2_calendar_semver import (
    Ot2Stability,
    decode_ot2_external_version,
    decode_ot2_internal_version,
    version_from_external_tag,
    version_from_internal_tag,
)

FlexStability = Literal["stable", "alpha", "beta"]

FLEX_INTERNAL_STABLE_RE = re.compile(r"^ot3@(\d+\.\d+\.\d+)$")
FLEX_INTERNAL_ALPHA_RE = re.compile(r"^ot3@(\d+\.\d+\.\d+)-alpha\.(\d+)$")
FLEX_INTERNAL_BETA_RE = re.compile(r"^ot3@(\d+\.\d+\.\d+)-beta\.(\d+)$")

FLEX_EXTERNAL_STABLE_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
FLEX_EXTERNAL_ALPHA_RE = re.compile(r"^v(\d+\.\d+\.\d+)-alpha\.(\d+)$")
FLEX_EXTERNAL_BETA_RE = re.compile(r"^v(\d+\.\d+\.\d+)-beta\.(\d+)$")


@dataclass(frozen=True)
class StabilityLatestTags:
    """Latest release tag for each stability lane in one pipeline."""

    stable: Optional[str] = None
    alpha: Optional[str] = None
    beta: Optional[str] = None


@dataclass(frozen=True)
class NextFlexTagSuggestion:
    """Suggested next Flex app tag for one stability lane at a semver base."""

    tag: str
    stability: FlexStability
    latest_in_repo: Optional[str]
    latest_on_branch: Optional[str]
    note: Optional[str] = None


def flex_tag_stability(tag: str, release_type: str) -> Optional[FlexStability]:
    """Return the stability lane for a Flex app or stack coordination tag."""
    if release_type == "internal":
        if FLEX_INTERNAL_STABLE_RE.match(tag):
            return "stable"
        if FLEX_INTERNAL_ALPHA_RE.match(tag):
            return "alpha"
        if FLEX_INTERNAL_BETA_RE.match(tag):
            return "beta"
        return None

    if FLEX_EXTERNAL_STABLE_RE.match(tag):
        return "stable"
    if FLEX_EXTERNAL_ALPHA_RE.match(tag):
        return "alpha"
    if FLEX_EXTERNAL_BETA_RE.match(tag):
        return "beta"
    return None


def flex_tag_base(tag: str, release_type: str) -> Optional[str]:
    """Return the X.Y.Z base for a Flex release tag, if parseable."""
    stability = flex_tag_stability(tag, release_type)
    if stability is None:
        return None

    if release_type == "internal":
        patterns = (FLEX_INTERNAL_STABLE_RE, FLEX_INTERNAL_ALPHA_RE, FLEX_INTERNAL_BETA_RE)
    else:
        patterns = (FLEX_EXTERNAL_STABLE_RE, FLEX_EXTERNAL_ALPHA_RE, FLEX_EXTERNAL_BETA_RE)

    for pattern in patterns:
        match = pattern.match(tag)
        if match is not None:
            return match.group(1)
    return None


def ot2_tag_stability(tag: str, release_type: str) -> Optional[Ot2Stability]:
    """Return the stability lane for an OT-2 app tag."""
    if release_type == "internal":
        version = version_from_internal_tag(tag)
        if version is None:
            return None
        try:
            _, _, _, _, prerelease = decode_ot2_internal_version(version)
        except ValueError:
            return None
        if prerelease == "alpha":
            return "alpha"
        if prerelease == "beta":
            return "beta"
        return "stable"

    version = version_from_external_tag(tag)
    if version is None:
        return None
    try:
        _, _, _, prerelease, _ = decode_ot2_external_version(version)
    except ValueError:
        return None
    if prerelease == "alpha":
        return "alpha"
    if prerelease == "beta":
        return "beta"
    return "stable"


def filter_flex_tags_for_base(tags: Iterable[str], release_type: str, base: str) -> list[str]:
    """Return Flex tags whose X.Y.Z base matches ``base``."""
    matched: list[str] = []
    for tag in tags:
        tag_base = flex_tag_base(tag, release_type)
        if tag_base == base:
            matched.append(tag)
    return matched


def flex_tags_in_lane(
    tags: Iterable[str],
    release_type: str,
    stability: FlexStability,
    base: str,
) -> list[str]:
    """Return tags in one stability lane at a semver base, preserving input order."""
    return [
        tag for tag in tags if flex_tag_base(tag, release_type) == base and flex_tag_stability(tag, release_type) == stability
    ]


def latest_tags_by_stability_flex(
    tags: Iterable[str],
    release_type: str,
    *,
    base: Optional[str] = None,
) -> StabilityLatestTags:
    """Return the newest stable, alpha, and beta Flex tags in ``tags``."""
    stable: Optional[str] = None
    alpha: Optional[str] = None
    beta: Optional[str] = None

    for tag in tags:
        tag_base = flex_tag_base(tag, release_type)
        if base is not None and tag_base != base:
            continue

        lane = flex_tag_stability(tag, release_type)
        if lane == "stable" and stable is None:
            stable = tag
        elif lane == "alpha" and alpha is None:
            alpha = tag
        elif lane == "beta" and beta is None:
            beta = tag

        if stable is not None and alpha is not None and beta is not None:
            break

    return StabilityLatestTags(stable=stable, alpha=alpha, beta=beta)


def latest_tags_by_stability_ot2(
    tags: Iterable[str],
    release_type: str,
) -> StabilityLatestTags:
    """Return the newest stable, alpha, and beta OT-2 tags in ``tags``."""
    stable: Optional[str] = None
    alpha: Optional[str] = None
    beta: Optional[str] = None

    for tag in tags:
        lane = ot2_tag_stability(tag, release_type)
        if lane == "stable" and stable is None:
            stable = tag
        elif lane == "alpha" and alpha is None:
            alpha = tag
        elif lane == "beta" and beta is None:
            beta = tag

        if stable is not None and alpha is not None and beta is not None:
            break

    return StabilityLatestTags(stable=stable, alpha=alpha, beta=beta)


def latest_merged_flex_tag_for_stability(
    tags: Iterable[str],
    release_type: str,
    stability: FlexStability,
    base: str,
) -> Optional[str]:
    """Return the newest merged tag for one Flex stability lane and semver base."""
    for tag in tags:
        if flex_tag_base(tag, release_type) != base:
            continue
        if flex_tag_stability(tag, release_type) == stability:
            return tag
    return None


def latest_merged_ot2_tag_for_stability(
    tags: Iterable[str],
    release_type: str,
    stability: Ot2Stability,
) -> Optional[str]:
    """Return the newest merged OT-2 tag for one stability lane."""
    for tag in tags:
        if ot2_tag_stability(tag, release_type) == stability:
            return tag
    return None
