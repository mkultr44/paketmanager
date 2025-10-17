"""Persistence helpers using SQLite."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from .config import DATABASE_PATH, DATA_DIR
from .models import StoredParcel


def ensure_database(path: Path = DATABASE_PATH) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS stored_parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_tracking_number TEXT NOT NULL,
                original_tracking_number TEXT,
                customer TEXT NOT NULL,
                zone TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Attempt to add the new column when upgrading from older versions.
        try:
            connection.execute(
                "ALTER TABLE stored_parcels ADD COLUMN original_tracking_number TEXT"
            )
        except sqlite3.OperationalError:
            pass
        connection.commit()


@contextmanager
def get_connection(path: Path = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    ensure_database(path)
    connection = sqlite3.connect(path)
    try:
        yield connection
    finally:
        connection.close()


def add_parcel(
    scanned_tracking_number: str,
    customer: str,
    zone: str,
    original_tracking_number: str | None = None,
    path: Path = DATABASE_PATH,
) -> int:
    with get_connection(path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO stored_parcels (
                scanned_tracking_number,
                original_tracking_number,
                customer,
                zone,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (scanned_tracking_number, original_tracking_number, customer, zone, datetime.utcnow()),
        )
        connection.commit()
        return int(cursor.lastrowid)


def list_parcels(path: Path = DATABASE_PATH) -> List[StoredParcel]:
    with get_connection(path) as connection:
        rows = connection.execute(
            """
            SELECT id, scanned_tracking_number, original_tracking_number, customer, zone, created_at
            FROM stored_parcels
            ORDER BY created_at DESC
            """
        ).fetchall()
    return [
        StoredParcel(
            id=row[0],
            scanned_tracking_number=row[1],
            original_tracking_number=row[2],
            customer=row[3],
            zone=row[4],
            created_at=_coerce_datetime(row[5]),
        )
        for row in rows
    ]


def find_zone_for_tracking(tracking_number: str, path: Path = DATABASE_PATH) -> Optional[str]:
    with get_connection(path) as connection:
        row = connection.execute(
            """
            SELECT zone
            FROM stored_parcels
            WHERE scanned_tracking_number = ? OR original_tracking_number = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tracking_number, tracking_number),
        ).fetchone()
    return row[0] if row else None


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    return datetime.utcnow()
