"""Konfigurationswerte für die Paketmanager-Anwendung."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(slots=True)
class AppConfig:
    """Enthält sämtliche konfigurierbare Parameter der Anwendung."""

    webdav_url: str = (
        "https://nextcloud.aralbruehl.de/public.php/dav/files/HMMEZAB25as8mbM/zustellungsliste.csv"
    )
    polling_seconds: int = 60
    fuzzy_score_cutoff: int = 75
    zone_names: List[str] = field(
        default_factory=lambda: [
            "Zone A",
            "Zone B",
            "Zone C",
            "Zone D",
            "Zone E",
            "Zone F",
        ]
    )
    database_path: Path = Path("data/paketmanager.db")
    log_file: Path = Path("logs/paketmanager.log")


CONFIG = AppConfig()
