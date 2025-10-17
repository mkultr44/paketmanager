"""Fuzzy Search und Matching Utility."""

from __future__ import annotations

from rapidfuzz import fuzz, process


def best_tracking_match(scanned: str, candidates: list[str], *, score_cutoff: int) -> tuple[str, float] | None:
    """Findet die beste Sendungsnummer zu einem Scan."""
    result = process.extractOne(
        scanned,
        candidates,
        scorer=fuzz.WRatio,
        score_cutoff=score_cutoff,
    )
    if not result:
        return None
    match, score, _ = result
    return match, float(score)


def fuzzy_filter(value: str, haystack: list[tuple[str, str]], *, score_cutoff: int) -> list[int]:
    """Liefert Indexe der Einträge, die den Filter erfüllen."""
    indices: list[int] = []
    for idx, (tracking, customer) in enumerate(haystack):
        if not value:
            indices.append(idx)
            continue
        if value.lower() in tracking.lower() or value.lower() in customer.lower():
            indices.append(idx)
            continue
        score_tracking = fuzz.WRatio(value, tracking)
        score_customer = fuzz.WRatio(value, customer)
        if score_tracking >= score_cutoff or score_customer >= score_cutoff:
            indices.append(idx)
    return indices
