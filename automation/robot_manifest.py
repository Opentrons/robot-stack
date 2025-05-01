import asyncio
from dataclasses import dataclass
from typing import List, Optional, Final, Dict, Tuple
from datetime import datetime

import semver
import httpx
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


async def fetch_robot_releases(
    client: httpx.AsyncClient, label: str, url: str
) -> Tuple[str, Optional[RobotReleasesCollection], Optional[str]]:
    """Download JSON metadata and wrap grouped releases in RobotReleasesCollection."""
    try:
        r = await client.get(url, timeout=10.0)
        r.raise_for_status()
        prod = r.json().get("production", {})
        if not prod:
            raise ValueError("no 'production' entries in JSON")
        coll = RobotReleasesCollection.from_production(prod)
        return label, coll, None
    except Exception as e:
        return label, None, str(e)


def display_robot_releases(results: List[Tuple[str, Optional[RobotReleasesCollection], Optional[str]]]) -> None:
    console = Console()
    table = Table(title="Opentrons Robot JSON Releases", box=box.SIMPLE_HEAVY)
    table.add_column("Robot", style="cyan", no_wrap=True)
    table.add_column("Channel", style="blue", no_wrap=True)
    table.add_column("Version", style="green")
    table.add_column("Version URL", style="blue", no_wrap=True)

    # Collect all rows first
    rows: List[Tuple[str, str, str, str]] = []
    for label, coll, err in results:
        if err:
            rows.append((label, "ERROR", "-", f"[red]{err}[/red]"))
            continue

        for channel, getter in (
            ("alpha", coll.latest_alpha),
            ("beta", coll.latest_beta),
            ("stable", coll.latest_stable),
        ):
            rel = getter()
            if rel:
                rows.append((label, channel, rel.version, rel.version_url))

    # Sort by track order: alpha, beta, stable, then ERROR
    order = {"alpha": 0, "beta": 1, "stable": 2, "ERROR": 3}
    rows.sort(key=lambda row: order.get(row[1], 99))

    # Add sorted rows to table
    for label, channel, version, version_url in rows:
        table.add_row(label, channel, version, version_url)

    console.print(table)
