
from typing import List, Optional, Final, Dict, Tuple
from dataclasses import dataclass


INTERNAL = "internal"
EXTERNAL = "external"
RELEASE_CHANNELS = [INTERNAL, EXTERNAL]

@dataclass
class ReleaseCycle:
    opentrons_branch: str
    oe_core_branch: str
    buildroot_branch: str
    ot3_firmware_branch: str

@dataclass
class InternalReleaseCycle(ReleaseCycle):

@dataclass
class ExternalReleaseCycle(ReleaseCycle):

@dataclass
class Release:
    channel: 
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