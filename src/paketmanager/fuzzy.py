from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from rapidfuzz import fuzz, process

from .data_models import Shipment


@dataclass
class FuzzyMatchResult:
    shipment: Shipment
    score: float


class ShipmentMatcher:
    def __init__(self, shipments: Sequence[Shipment] | None = None) -> None:
        self._shipments: list[Shipment] = list(shipments or [])

    def update(self, shipments: Sequence[Shipment]) -> None:
        self._shipments = list(shipments)

    def match_tracking(self, tracking_number: str, *, min_score: float = 60) -> FuzzyMatchResult | None:
        if not self._shipments:
            return None
        choices = {shipment.tracking_number: shipment for shipment in self._shipments}
        match = process.extractOne(
            tracking_number,
            choices.keys(),
            scorer=fuzz.WRatio,
            score_cutoff=min_score,
        )
        if not match:
            return None
        matched_value, score, _ = match
        return FuzzyMatchResult(shipment=choices[matched_value], score=score)

    def filter(self, query: str, *, limit: int | None = None) -> list[FuzzyMatchResult]:
        if not query:
            return [FuzzyMatchResult(shipment=shipment, score=100.0) for shipment in self._shipments]
        choices = {shipment.tracking_number: shipment for shipment in self._shipments}
        scoring_keys = list(choices.keys()) + [shipment.customer_name for shipment in self._shipments]
        matches = process.extract(
            query,
            scoring_keys,
            scorer=fuzz.WRatio,
            limit=limit or len(scoring_keys),
        )
        results: list[FuzzyMatchResult] = []
        seen = set()
        for value, score, _ in matches:
            for shipment in self._shipments:
                if value in (shipment.tracking_number, shipment.customer_name) and shipment.tracking_number not in seen:
                    results.append(FuzzyMatchResult(shipment=shipment, score=score))
                    seen.add(shipment.tracking_number)
        return results
