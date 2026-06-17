"""Flex coordinated release tag naming shared by go.py and validate_release_tags.py."""

from __future__ import annotations

import re
from typing import Final, Optional

FIRMWARE_VERSION_TAG_RE: Final[re.Pattern[str]] = re.compile(r"^v\d+$")
EXTERNAL_STACK_TAG_RE: Final[re.Pattern[str]] = re.compile(r"^v\d+\.\d+\.\d+(?:-(?:alpha|beta)\.\d+)?$")


def normalize_tag(tag: str) -> str:
    """Strip refs/tags/ prefix so git commands receive a plain tag name."""
    if tag.startswith("refs/tags/"):
        return tag[len("refs/tags/") :]
    return tag


def is_firmware_version_tag(tag: str) -> bool:
    """Return True for integer-only firmware version tags such as v70."""
    return bool(FIRMWARE_VERSION_TAG_RE.match(normalize_tag(tag)))


def is_external_stack_coordination_tag(tag: str) -> bool:
    """Return True for external semver coordination tags (vX.Y.Z, not integer vN)."""
    clean = normalize_tag(tag)
    return bool(clean.startswith("v") and EXTERNAL_STACK_TAG_RE.match(clean))


def stack_coordinated_tag_to_firmware_tag(stack_tag: str) -> Optional[str]:
    """Map an external stack tag to the ot3-firmware coordination tag (ex* prefix).

    External ``v9.1.0-alpha.7`` becomes ``ex9.1.0-alpha.7``. Internal ``ot3@*`` and
    integer ``vN`` version tags are not mapped (returns None).
    """
    clean = normalize_tag(stack_tag)
    if clean.startswith("ex"):
        return None
    if clean.startswith("v") and not is_firmware_version_tag(clean):
        return f"ex{clean[1:]}"
    return None


def coordinated_tag_for_repo(repo_name: str, stack_tag: str) -> str:
    """Return the coordination tag expected in a given Flex repo for a stack dispatch."""
    clean = normalize_tag(stack_tag)
    if repo_name == "ot3-firmware":
        return stack_coordinated_tag_to_firmware_tag(clean) or clean
    return clean
