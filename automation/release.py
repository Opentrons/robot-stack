from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import semver

INTERNAL = "internal"
EXTERNAL = "external"
RELEASE_CHANNELS = [INTERNAL, EXTERNAL]


def _robot_manifest_buckets(
    manifest: Dict[str, Any],
) -> tuple[Dict[str, Dict[str, str]], Dict[str, Dict[str, str]]]:
    """Return legacy and V2 robot release maps from a manifest."""
    legacy = manifest.get("production", {})
    v2 = manifest.get("productionV2", {})
    if not isinstance(legacy, dict):
        legacy = {}
    if not isinstance(v2, dict):
        v2 = {}
    return legacy, v2


def robot_manifest_production_entries(manifest: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Return robot release entries from an ot*-oe ``releases.json`` manifest.

    Flex publishes new robot OS builds under ``productionV2`` so pre-9.1.1 robots
    keep reading the legacy ``production`` key. Merge both maps with V2 winning on
    duplicate version keys.
    """
    legacy, v2 = _robot_manifest_buckets(manifest)
    merged: Dict[str, Dict[str, str]] = {**legacy, **v2}
    return merged


def robot_manifest_release_keys(manifest: Dict[str, Any]) -> Dict[str, str]:
    """Map each robot release version to its manifest key name."""
    legacy, v2 = _robot_manifest_buckets(manifest)
    keys = {version: "production" for version in legacy}
    keys.update({version: "productionV2" for version in v2})
    return keys


@dataclass
class ReleaseCycle:
    opentrons_branch: str
    oe_core_branch: str
    buildroot_branch: str
    ot3_firmware_branch: str


@dataclass
class InternalReleaseCycle(ReleaseCycle):
    pass


@dataclass
class ExternalReleaseCycle(ReleaseCycle):
    pass


@dataclass
class Release:
    channel: str
    robot_stack_tag: str
    robot_stack_version: str
    monorepo_chore_release: str


@dataclass
class RobotRelease:
    version: str
    full_image: str
    system: str
    version_url: str
    release_notes: str


@dataclass
class AppFile:
    url: str
    sha512: str
    size: int


@dataclass
class AppMetadata:
    version: str
    files: List[AppFile]
    path: str
    sha512: str
    releaseNotes: str
    releaseDate: Optional[str] = None


@dataclass
class RobotReleasesCollection:
    alphas: List[RobotRelease]
    betas: List[RobotRelease]
    stables: List[RobotRelease]

    @classmethod
    def from_production(cls, prod: Dict[str, Dict[str, str]]) -> "RobotReleasesCollection":
        alphas, betas, stables = [], [], []
        for ver, info in prod.items():
            rel = RobotRelease(
                version=ver,
                full_image=info["fullImage"],
                system=info["system"],
                version_url=info["version"],
                release_notes=info["releaseNotes"],
            )
            vi = semver.VersionInfo.parse(ver)
            if vi.prerelease:
                tag = vi.prerelease.split(".")[0]
                if tag == "alpha":
                    alphas.append(rel)
                elif tag == "beta":
                    betas.append(rel)
            else:
                stables.append(rel)
        return cls(alphas, betas, stables)

    def latest_alpha(self) -> Optional[RobotRelease]:
        if not self.alphas:
            return None
        return max(self.alphas, key=lambda r: semver.VersionInfo.parse(r.version))

    def latest_beta(self) -> Optional[RobotRelease]:
        if not self.betas:
            return None
        return max(self.betas, key=lambda r: semver.VersionInfo.parse(r.version))

    def latest_stable(self) -> Optional[RobotRelease]:
        if not self.stables:
            return None
        return max(self.stables, key=lambda r: semver.VersionInfo.parse(r.version))
