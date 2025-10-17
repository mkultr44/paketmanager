from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .data_models import Assignment

SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_number TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    scanned_tracking_number TEXT NOT NULL,
    zone TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.executescript(SCHEMA)

    def add_assignment(
        self,
        *,
        tracking_number: str,
        customer_name: str,
        scanned_tracking_number: str,
        zone: str,
    ) -> Assignment:
        created_at = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO assignments (tracking_number, customer_name, scanned_tracking_number, zone, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (tracking_number, customer_name, scanned_tracking_number, zone, created_at),
            )
            assignment_id = cursor.lastrowid
        return Assignment(
            id=assignment_id,
            tracking_number=tracking_number,
            customer_name=customer_name,
            scanned_tracking_number=scanned_tracking_number,
            zone=zone,
            created_at=datetime.fromisoformat(created_at),
        )

    def list_assignments(self) -> Iterable[Assignment]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, tracking_number, customer_name, scanned_tracking_number, zone, created_at FROM assignments"
            )
            for row in cursor:
                yield Assignment(
                    id=row["id"],
                    tracking_number=row["tracking_number"],
                    customer_name=row["customer_name"],
                    scanned_tracking_number=row["scanned_tracking_number"],
                    zone=row["zone"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
