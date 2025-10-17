"""Utility helpers for fuzzy matching and searching."""
from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, List, Tuple

from .models import Delivery, MatchResult


def normalise(value: str) -> str:
    """Normalise a tracking number for comparison purposes."""

    return value.strip().upper().replace(" ", "")


def similarity(a: str, b: str) -> float:
    """Return a similarity score between two strings in the range [0, 1]."""

    return SequenceMatcher(None, normalise(a), normalise(b)).ratio()


def best_match(scan: str, deliveries: Iterable[Delivery]) -> MatchResult:
    """Find the delivery that best matches the scanned tracking number."""

    best: MatchResult = MatchResult(delivery=None, score=0.0)
    for delivery in deliveries:
        score = similarity(scan, delivery.tracking_number)
        if score > best.score:
            best = MatchResult(delivery=delivery, score=score)
    return best


def fuzzy_filter(query: str, deliveries: Iterable[Delivery], limit: int = 200) -> List[Tuple[Delivery, float]]:
    """Return deliveries ranked by similarity to the given query."""

    normalised_query = normalise(query)
    if not normalised_query:
        return [(delivery, 1.0) for delivery in deliveries][:limit]

    results = [
        (delivery, similarity(normalised_query, delivery.tracking_number + " " + delivery.customer))
        for delivery in deliveries
    ]
    results.sort(key=lambda item: item[1], reverse=True)
    return results[:limit]
