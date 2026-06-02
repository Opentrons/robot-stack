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
    ot2_prerelease_for_stability,
    ot2_release_date_today,
    version_from_external_tag,
    version_from_internal_tag,
)


def _max_external_release_num_in_month(existing_tags: set[str], release_date: date) -> int:
    """Return the highest monthly build counter N already used this calendar month."""
    release_nums: list[int] = []
    for tag in existing_tags:
        version = version_from_external_tag(tag)
        if version is None:
            continue
        try:
            year, month, release_num, _, _ = decode_ot2_external_version(version)
        except ValueError:
            continue
        if (year, month) == (release_date.year, release_date.month):
            release_nums.append(release_num)
    return max(release_nums, default=-1)


def _external_stability_bases_in_month(
    existing_tags: set[str],
    release_date: date,
    stability: Ot2Stability,
) -> set[int]:
    """Return N values that already have alpha or beta tags this month."""
    bases: set[int] = set()
    for tag in existing_tags:
        version = version_from_external_tag(tag)
        if version is None:
            continue
        try:
            year, month, release_num, tag_pre, tag_pre_num = decode_ot2_external_version(version)
        except ValueError:
            continue
        if (year, month) == (release_date.year, release_date.month) and tag_pre == stability and tag_pre_num is not None:
            bases.add(release_num)
    return bases


def infer_ot2_external_base_version(
    existing_tags: set[str],
    stability: Ot2Stability = "stable",
    release_date: date | None = None,
) -> str:
    """Return the YY.M.N base the next external tag will use."""
    if release_date is None:
        release_date = ot2_release_date_today()

    max_n = _max_external_release_num_in_month(existing_tags, release_date)

    if stability == "stable":
        next_n = max_n + 1
        if next_n > 9:
            raise ValueError("More than 10 external releases this month (N > 9)")
        return encode_ot2_external_version(release_date.year, release_date.month, next_n)

    stability_bases = _external_stability_bases_in_month(existing_tags, release_date, stability)
    if stability == "beta" and not stability_bases:
        # First beta on a build line shares N with the latest alpha base (e.g. 26.5.1-alpha.0 -> 26.5.1-beta.0).
        alpha_bases = _external_stability_bases_in_month(existing_tags, release_date, "alpha")
        base_n = max(alpha_bases) if alpha_bases else max_n + 1
    else:
        base_n = max(stability_bases) if stability_bases else max_n + 1
    if base_n > 9:
        raise ValueError("More than 10 external releases this month (N > 9)")
    return encode_ot2_external_version(release_date.year, release_date.month, base_n)


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
    release_date: date | None = None,
) -> str:
    """Pick the next v tag for the calendar month and stability channel."""
    if release_date is None:
        release_date = ot2_release_date_today()

    if stability == "stable":
        next_version = infer_ot2_external_base_version(existing_tags, "stable", release_date)
        return f"v{next_version}"

    base_version = infer_ot2_external_base_version(existing_tags, stability, release_date)
    year, month, release_num, _, _ = decode_ot2_external_version(base_version)

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
