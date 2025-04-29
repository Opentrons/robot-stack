import asyncio
from dataclasses import dataclass
from typing import List, Optional, Final, Dict, Tuple
from datetime import datetime

import semver
import httpx
import yaml
from rich.console import Console
from rich.table import Table
from rich import box


console = Console()




def print_versions_table(versions: List[dict]) -> None:
    """Display versions in a Rich table."""
    table = Table(title="Recent S3 Object Versions")
    table.add_column("VersionId", style="cyan")
    table.add_column("IsLatest", style="green")
    table.add_column("LastModified", style="magenta")
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("ETag", style="white")
    for v in versions:
        table.add_row(
            v["VersionId"],
            str(v["IsLatest"]),
            v["LastModified"].isoformat(),
            str(v["Size"]),
            v["ETag"],
        )
    console.print(table)



async def fetch_app_metadata(client: httpx.AsyncClient, label: str, url: str) -> Tuple[str, Optional[AppMetadata], Optional[str]]:
    """Fetch and parse YAML metadata asynchronously, ignoring extra file fields."""
    try:
        r = await client.get(url, timeout=10.0)
        r.raise_for_status()
        data = yaml.safe_load(r.text)
        files = [
            AppFile(url=f["url"], sha512=f["sha512"], size=f["size"])
            for f in data.get("files", [])
            if "url" in f and "sha512" in f and "size" in f
        ]
        meta = AppMetadata(
            version=data["version"],
            files=files,
            path=data["path"],
            sha512=data["sha512"],
            releaseNotes=data.get("releaseNotes", ""),
            releaseDate=data.get("releaseDate"),
        )
        return label, meta, None
    except Exception as e:
        return label, None, str(e)

def display_app_metadata(results: List[Tuple[str, Optional[AppMetadata], Optional[str]]]) -> None:
    console = Console()
    table = Table(title="Opentrons App YAML Manifests", box=box.SIMPLE_HEAVY)
    table.add_column("Channel", style="cyan", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Path", style="magenta")
    table.add_column("Release Date", style="yellow")

    for label, meta, err in results:
        if err:
            table.add_row(label, "ERROR", "-", f"[red]{err}[/red]")
        else:
            if meta.releaseDate:
                utc = datetime.fromisoformat(meta.releaseDate.replace("Z", "+00:00"))
                local = utc.astimezone()
                ds = local.strftime("%Y-%m-%d %H:%M:%S %Z")
            else:
                ds = "N/A"
            table.add_row(label, meta.version, meta.path, ds)

    console.print(table)
