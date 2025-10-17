"""SQLite-Datenbankfunktionen für den Paketmanager."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Iterable, List, Optional

from .config import CONFIG
from .models import Shipment


def init_database(db_path: Path | None = None) -> None:
    """Initialisiert die Datenbankstruktur."""
    path = db_path or CONFIG.database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT NOT NULL,
                customer TEXT NOT NULL,
                zone TEXT NOT NULL,
                created_at TEXT NOT NULL,
                source_tracking_number TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_shipments_tracking
                ON shipments(tracking_number)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT NOT NULL,
                customer TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def _connect(path: Path | None = None) -> sqlite3.Connection:
    return sqlite3.connect(path or CONFIG.database_path)


@contextmanager
def get_connection(path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
    conn = _connect(path)
    try:
        yield conn
    finally:
        conn.close()


def upsert_ocr_entries(entries: Iterable[tuple[str, str]], *, path: Path | None = None) -> None:
    """Speichert die OCR-Ergebnisse und ersetzt vorhandene Daten."""
    with get_connection(path) as conn:
        conn.execute("DELETE FROM ocr_entries")
        conn.executemany(
            "INSERT INTO ocr_entries (tracking_number, customer, updated_at) VALUES (?, ?, ?)",
            ((tracking, customer, datetime.utcnow().isoformat()) for tracking, customer in entries),
        )
        conn.commit()


def fetch_ocr_entries(*, path: Path | None = None) -> List[tuple[str, str]]:
    with get_connection(path) as conn:
        cursor = conn.execute("SELECT tracking_number, customer FROM ocr_entries")
        return list(cursor.fetchall())


def insert_shipment(
    tracking_number: str,
    customer: str,
    zone: str,
    *,
    source_tracking_number: Optional[str] = None,
    path: Path | None = None,
) -> None:
    with get_connection(path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO shipments
                (tracking_number, customer, zone, created_at, source_tracking_number)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                tracking_number,
                customer,
                zone,
                datetime.utcnow().isoformat(),
                source_tracking_number,
            ),
        )
        conn.commit()


def fetch_shipments(*, path: Path | None = None) -> List[Shipment]:
    with get_connection(path) as conn:
        rows = conn.execute(
            """
            SELECT id, tracking_number, customer, zone, created_at, source_tracking_number
            FROM shipments
            ORDER BY created_at DESC
            """
        ).fetchall()
    shipments: List[Shipment] = []
    for row in rows:
        shipments.append(
            Shipment(
                id=row[0],
                tracking_number=row[1],
                customer=row[2],
                zone=row[3],
                created_at=datetime.fromisoformat(row[4]),
                source_tracking_number=row[5],
            )
        )
    return shipments
