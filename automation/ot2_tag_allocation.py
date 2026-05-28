"""Suggest next OT-2 release tags from existing tags (release planning only).

Used by `just go` before a human pushes tags. Build/CI in opentrons-ot2 reads the pushed tag;
it does not call these helpers.
"""

from __future__ import annotations

from datetime import date

from automation.ot2_calendar_semver import (
    Ot2Stability,
    decode_ot2_external_version,
    decode_ot2_internal_version,
    encode_ot2_external_version,
    encode_ot2_internal_version,
    ot2_external_version_for_month,
    ot2_prerelease_for_stability,
    ot2_release_date_today,
    version_from_external_tag,
    version_from_internal_tag,
)


def allocate_next_internal_tag(
    existing_tags: set[str],
    stability: Ot2Stability = "stable",
    release_date: date | None = None,
) -> str:
    """Pick the next internal@ tag for a calendar day and stability channel."""
    if release_date is None:
        release_date = ot2_release_date_today()

    expected_prerelease = ot2_prerelease_for_stability(stability)
    same_day_builds: list[int] = []

    for tag in existing_tags:
        try:
            version = version_from_internal_tag(tag)
            if version is None:
                continue
            year, month, day, build_num, prerelease = decode_ot2_internal_version(version)
        except ValueError:
            continue
        if (year, month, day) == (release_date.year, release_date.month, release_date.day) and prerelease == expected_prerelease:
            same_day_builds.append(build_num)

    next_build = max(same_day_builds, default=0) + 1
    next_version = encode_ot2_internal_version(release_date.year, release_date.month, release_date.day, next_build)
    if expected_prerelease is not None:
        next_version = f"{next_version}-{expected_prerelease}"
    return f"internal@{next_version}"


def allocate_next_external_tag(
    existing_tags: set[str],
    stability: Ot2Stability = "stable",
    base_version: str | None = None,
    release_date: date | None = None,
) -> str:
    """Pick the next v tag for the calendar month and stability channel."""
    if release_date is None:
        release_date = ot2_release_date_today()

    if stability == "stable":
        same_month_nums: list[int] = []
        for tag in existing_tags:
            version = version_from_external_tag(tag)
            if version is None:
                continue
            try:
                year, month, release_num, prerelease, _ = decode_ot2_external_version(version)
            except ValueError:
                continue
            if (year, month) == (release_date.year, release_date.month) and prerelease is None:
                same_month_nums.append(release_num)
        next_num = max(same_month_nums, default=-1) + 1
        if next_num > 9:
            raise ValueError("More than 10 external stable releases this month (N > 9)")
        next_version = encode_ot2_external_version(release_date.year, release_date.month, next_num)
        return f"v{next_version}"

    if base_version is None:
        base_version = ot2_external_version_for_month(release_date, 0)

    year, month, release_num, _, _ = decode_ot2_external_version(base_version)
    if (year, month) != (release_date.year, release_date.month):
        raise ValueError("base_version month must match release month")

    same_prerelease_nums: list[int] = []
    for tag in existing_tags:
        version = version_from_external_tag(tag)
        if version is None:
            continue
        try:
            tag_year, tag_month, tag_num, tag_pre, tag_pre_num = decode_ot2_external_version(version)
        except ValueError:
            continue
        if (tag_year, tag_month, tag_num) == (year, month, release_num) and tag_pre == stability and tag_pre_num is not None:
            same_prerelease_nums.append(tag_pre_num)

    next_pre_num = max(same_prerelease_nums, default=-1) + 1
    next_version = encode_ot2_external_version(year, month, release_num, stability, next_pre_num)
    return f"v{next_version}"
