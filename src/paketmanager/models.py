"""Datamodelle für OCR-Einträge und Sendungen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class OcrEntry:
    tracking_number: str
    customer: str


@dataclass(slots=True)
class Shipment:
    id: int
    tracking_number: str
    customer: str
    zone: str
    created_at: datetime
    source_tracking_number: str | None = None
