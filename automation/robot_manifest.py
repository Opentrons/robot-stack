from typing import Optional, Tuple

import httpx
from rich.console import Console

from automation.release import RobotReleasesCollection

console: Console = Console()


async def fetch_robot_releases(
    client: httpx.AsyncClient, label: str, url: str
) -> Tuple[str, Optional[RobotReleasesCollection], Optional[str]]:
    """Download JSON metadata and wrap grouped releases in RobotReleasesCollection."""
    try:
        r: httpx.Response = await client.get(url, timeout=10.0)
        r.raise_for_status()
        prod = r.json().get("production", {})
        if not prod:
            raise ValueError("no 'production' entries in JSON")
        coll = RobotReleasesCollection.from_production(prod)
        return label, coll, None
    except Exception as e:
        return label, None, str(e)
