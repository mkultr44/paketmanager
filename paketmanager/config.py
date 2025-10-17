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

SFTP_HOST: str = "217.154.10.167"
SFTP_PORT: int = 22
SFTP_USERNAME: str = "hermes"
SFTP_PASSWORD: str = "2tHM3e#hdv5A"
SFTP_REMOTE_PATH: str = "hermes-directory.csv"

# Interval (in milliseconds) for synchronising the delivery list.
SYNC_INTERVAL_MS: int = 60_000

# Default zones that can be overridden in a local configuration later on.
DEFAULT_ZONES: List[Zone] = [
    Zone("Zone A"),
    Zone("Zone B"),
    Zone("Zone C"),
    Zone("Zone D"),
]

# Similarity threshold for automatically associating scanned numbers with OCR entries.
FUZZY_MATCH_THRESHOLD: float = 0.6

