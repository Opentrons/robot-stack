"""Constants for release metadata URLs used to evaluate latest published versions across platforms and release channels."""

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Final, Dict

import httpx
import yaml
from rich.console import Console
from rich.table import Table
from rich import box
from datetime import datetime

# ------------------------------------------------------------------------------
# Alpha Channel
# ------------------------------------------------------------------------------

ALPHA_APP_WINDOWS_URL: Final[str] = "https://builds.opentrons.com/app/alpha.yml"
ALPHA_APP_MAC_URL: Final[str] = "https://builds.opentrons.com/app/alpha-mac.yml"
ALPHA_APP_LINUX_URL: Final[str] = "https://builds.opentrons.com/app/alpha-linux.yml"

# ------------------------------------------------------------------------------
# Beta Channel
# ------------------------------------------------------------------------------

BETA_APP_WINDOWS_URL: Final[str] = "https://builds.opentrons.com/app/beta.yml"
BETA_APP_MAC_URL: Final[str] = "https://builds.opentrons.com/app/beta-mac.yml"
BETA_APP_LINUX_URL: Final[str] = "https://builds.opentrons.com/app/beta-linux.yml"

# ------------------------------------------------------------------------------
# Latest Stable Channel
# ------------------------------------------------------------------------------

LATEST_APP_WINDOWS_URL: Final[str] = "https://builds.opentrons.com/app/latest.yml"
LATEST_APP_MAC_URL: Final[str] = "https://builds.opentrons.com/app/latest-mac.yml"
LATEST_APP_LINUX_URL: Final[str] = "https://builds.opentrons.com/app/latest-linux.yml"

# ------------------------------------------------------------------------------
# Release JSON Metadata for the Flex and OT2
# ------------------------------------------------------------------------------

# Informational ONLY for the App, Electron update uses the yml files
RELEASE_APP_JSON_URL: Final[str] = "https://builds.opentrons.com/app/releases.json"
RELEASE_FLEX_JSON_URL: Final[str] = "https://builds.opentrons.com/ot3-oe/releases.json"
RELEASE_OT2_JSON_URL: Final[str] = "https://builds.opentrons.com/ot2-br/releases.json"

# ------------------------------------------------------------------------------
# Internal Release JSON Metadata for the Flex and OT2
# ------------------------------------------------------------------------------

# Informational ONLY for the App, Electron update uses the yml files
INTERNAL_RELEASE_APP_JSON_URL: Final[str] = "https://ot3-development.builds.opentrons.com/app/releases.json"
INTERNAL_RELEASE_FLEX_JSON_URL: Final[str] = "https://ot3-development.builds.opentrons.com/ot3-oe/releases.json"
INTERNAL_RELEASE_OT2_JSON_URL: Final[str] = "https://ot3-development.builds.opentrons.com/ot2-br/releases.json"

# ------------------------------------------------------------------------------


APP_YAML_URLS: Final[Dict[str, str]] = {
    "Alpha (Windows)": ALPHA_APP_WINDOWS_URL,
    "Alpha (Mac)": ALPHA_APP_MAC_URL,
    "Alpha (Linux)": ALPHA_APP_LINUX_URL,
    "Beta (Windows)": BETA_APP_WINDOWS_URL,
    "Beta (Mac)": BETA_APP_MAC_URL,
    "Beta (Linux)": BETA_APP_LINUX_URL,
    "Latest (Windows)": LATEST_APP_WINDOWS_URL,
    "Latest (Mac)": LATEST_APP_MAC_URL,
    "Latest (Linux)": LATEST_APP_LINUX_URL,
}


# -------------------------------------------------------------------
# Data Models
# -------------------------------------------------------------------


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


# -------------------------------------------------------------------
# Async Fetch
# -------------------------------------------------------------------


async def fetch_app_metadata(client: httpx.AsyncClient, label: str, url: str) -> tuple[str, Optional[AppMetadata], Optional[str]]:
    """Fetch and parse YAML metadata asynchronously, ignoring extra file fields."""
    try:
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        data = yaml.safe_load(response.text)

        # Only pick the known AppFile fields
        files: list[AppFile] = [
            AppFile(
                url=file_info["url"],
                sha512=file_info["sha512"],
                size=file_info["size"],
            )
            for file_info in data.get("files", [])
            if "url" in file_info and "sha512" in file_info and "size" in file_info
        ]

        metadata = AppMetadata(
            version=data["version"],
            files=files,
            path=data["path"],
            sha512=data["sha512"],
            releaseNotes=data.get("releaseNotes", ""),
            releaseDate=data.get("releaseDate"),
        )
        return label, metadata, None
    except Exception as e:
        return label, None, str(e)


async def main() -> None:
    """Main entry point to fetch all YAML metadata concurrently and print with Rich."""
    console = Console()
    table = Table(title="Opentrons App Metadata", box=box.SIMPLE_HEAVY)
    table.add_column("Channel", style="cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Path", style="magenta")
    table.add_column("Release Date", style="yellow")

    async with httpx.AsyncClient() as client:
        tasks = [fetch_app_metadata(client, label, url) for label, url in APP_YAML_URLS.items()]
        results = await asyncio.gather(*tasks)

    for label, metadata, error in results:
        if error:
            table.add_row(label, "ERROR", "-", f"[red]{error}[/red]")
        else:
            # parse UTC ISO, convert to local, format nicely
            if metadata.releaseDate:
                utc_dt = datetime.fromisoformat(metadata.releaseDate.replace("Z", "+00:00"))
                local_dt = utc_dt.astimezone()
                date_str = local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
            else:
                date_str = "N/A"
            table.add_row(
                label,
                metadata.version,
                metadata.path,
                date_str,
            )

    console.print(table)


# Execute only when run directly
if __name__ == "__main__":
    asyncio.run(main())
