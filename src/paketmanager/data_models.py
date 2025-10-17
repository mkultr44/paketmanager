from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Shipment:
    tracking_number: str
    customer_name: str
    raw_payload: dict[str, str] | None = None

    def matches(self, query: str) -> bool:
        query_lower = query.lower()
        return query_lower in self.tracking_number.lower() or query_lower in self.customer_name.lower()


@dataclass
class Assignment:
    id: int
    tracking_number: str
    customer_name: str
    zone: str
    scanned_tracking_number: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Zone:
    name: str
    capacity: int
    current_load: int = 0

    def is_full(self) -> bool:
        return self.current_load >= self.capacity

    def register_package(self) -> None:
        if self.is_full():
            raise ValueError(f"Zone {self.name} ist voll")
        self.current_load += 1

    def reset(self) -> None:
        self.current_load = 0
