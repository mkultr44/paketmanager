"""Application configuration constants."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Zone:
    """Description of a storage zone."""

    name: str
    capacity: int | None = None


DATA_DIR: Path = Path.home() / ".paketmanager"
DATABASE_PATH: Path = DATA_DIR / "paketmanager.db"
REMOTE_DAV_URL: str = "https://nextcloud.aralbruehl.de/public.php/dav/files/HMMEZAB25as8mbM/"

# Interval (in milliseconds) for synchronising the delivery list.
SYNC_INTERVAL_MS: int = 60_000

# Default zones that can be overridden in a local configuration later on.
DEFAULT_ZONES: List[Zone] = [
    Zone("Zone A"),
    Zone("Zone B"),
    Zone("Zone C"),
    Zone("Zone D"),
]

# Filename preference order when multiple candidate files exist in the WebDAV share.
PREFERRED_FILENAMES: tuple[str, ...] = (
    "deliveries.json",
    "deliveries.csv",
    "lieferungen.json",
    "lieferungen.csv",
)

# Similarity threshold for automatically associating scanned numbers with OCR entries.
FUZZY_MATCH_THRESHOLD: float = 0.6

