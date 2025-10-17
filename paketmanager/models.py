"""Data models used throughout the application."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Delivery:
    """Represents a delivery entry parsed from the OCR list."""

    tracking_number: str
    customer: str
    extra: dict | None = None


@dataclass(slots=True)
class StoredParcel:
    """Represents a parcel stored in a zone."""

    id: int
    scanned_tracking_number: str
    original_tracking_number: str | None
    customer: str
    zone: str
    created_at: datetime


@dataclass(slots=True)
class MatchResult:
    """Result of trying to match a scan with known deliveries."""

    delivery: Optional[Delivery]
    score: float
