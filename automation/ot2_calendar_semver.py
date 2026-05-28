"""OT-2 calendar semver helpers for robot-stack release tooling.

Keep encode/decode/tag-regex rules in sync with opentrons-ot2/scripts/ot2_calendar_semver.py
and opentrons-ot2/scripts/git-version.mjs (build/CI read tags; this module does not allocate them).
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal, Optional, Tuple
from zoneinfo import ZoneInfo

OT2_RELEASE_TZ = ZoneInfo("America/New_York")
OT2_MONTH = r"(?:[1-9]|1[0-2])"
OT2_MONTH_CAP = r"([1-9]|1[0-2])"

OT2_INTERNAL_VERSION_RE = re.compile(
    rf"^(\d{{2}})\.{OT2_MONTH_CAP}\.(\d+)(?:-(alpha|beta))?$"
)
OT2_INTERNAL_TAG_RE = re.compile(
    rf"^internal@((\d{{2}})\.{OT2_MONTH_CAP}\.(\d+)(?:-(alpha|beta))?)$"
)

OT2_EXTERNAL_PRERELEASE_NUM = r"\d{1,3}"
OT2_EXTERNAL_VERSION_RE = re.compile(
    rf"^(\d{{2}})\.{OT2_MONTH_CAP}\.([0-9])(?:-(alpha|beta)\.({OT2_EXTERNAL_PRERELEASE_NUM}))?$"
)
OT2_EXTERNAL_TAG_RE = re.compile(
    rf"^v((\d{{2}})\.{OT2_MONTH_CAP}\.([0-9])(?:-(alpha|beta)\.({OT2_EXTERNAL_PRERELEASE_NUM}))?)$"
)

Ot2Stability = Literal["stable", "alpha", "beta"]


def ot2_release_date_today() -> date:
    """Return today's calendar date in US Eastern."""
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
    return encode_ot2_internal_version(
        release_date.year, release_date.month, release_date.day, build_num
    )


def ot2_external_version_for_month(release_date: date | None = None, release_num: int = 0) -> str:
    """Return external semver for the calendar month (Eastern), N starting at 0."""
    if release_date is None:
        release_date = ot2_release_date_today()
    return encode_ot2_external_version(release_date.year, release_date.month, release_num)


def ot2_prerelease_for_stability(stability: Ot2Stability) -> Optional[str]:
    """Map stability choice to internal bare prerelease suffix, if any."""
    if stability == "stable":
        return None
    return stability


def version_from_internal_tag(tag: str) -> Optional[str]:
    """Return the semver tail from an internal@ tag, or None if not calendar semver."""
    match = OT2_INTERNAL_TAG_RE.match(tag)
    if match is None:
        return None
    return match.group(1)


def version_from_external_tag(tag: str) -> Optional[str]:
    """Return the semver tail from a v tag, or None if not calendar semver."""
    match = OT2_EXTERNAL_TAG_RE.match(tag)
    if match is None:
        return None
    return match.group(1)


encode_ot2_version = encode_ot2_internal_version
decode_ot2_version = decode_ot2_internal_version
ot2_version_for_date = ot2_internal_version_for_date
