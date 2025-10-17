"""Kommunikation mit der Nextcloud-WebDAV-OCR-Liste."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
from datetime import datetime
from typing import List, Optional

import requests
from dateutil import parser as date_parser

from .config import CONFIG
from .database import fetch_ocr_entries, upsert_ocr_entries
from .models import OcrEntry

LOGGER = logging.getLogger(__name__)


class OcrFetcher:
    """Lädt die Zustellungsliste von der WebDAV-Quelle."""

    def __init__(self, url: str | None = None) -> None:
        self.url = url or CONFIG.webdav_url
        self._last_hash: str | None = None
        self._last_modified: datetime | None = None

    def _download(self) -> tuple[bytes, Optional[datetime]]:
        LOGGER.info("Downloading OCR list from %s", self.url)
        response = requests.get(self.url, timeout=30)
        response.raise_for_status()
        last_modified: Optional[datetime] = None
        if header := response.headers.get("Last-Modified"):
            try:
                last_modified = date_parser.parse(header)
            except (ValueError, TypeError):
                LOGGER.warning("Unable to parse Last-Modified header: %s", header)
        return response.content, last_modified

    def _needs_update(self, content: bytes, last_modified: Optional[datetime]) -> bool:
        digest = hashlib.sha256(content).hexdigest()
        if self._last_hash is None:
            self._last_hash = digest
            self._last_modified = last_modified
            return True
        if digest != self._last_hash:
            self._last_hash = digest
            self._last_modified = last_modified
            return True
        if last_modified and self._last_modified and last_modified > self._last_modified:
            self._last_modified = last_modified
            return True
        return False

    def _parse_content(self, content: bytes) -> List[OcrEntry]:
        text = content.decode("utf-8-sig", errors="ignore")
        try:
            payload = json.loads(text)
            if isinstance(payload, list):
                entries: List[OcrEntry] = []
                for item in payload:
                    tracking = str(item.get("Sendungsnummer") or item.get("tracking_number") or "").strip()
                    customer = str(item.get("Kunde") or item.get("customer") or "").strip()
                    if tracking and customer:
                        entries.append(OcrEntry(tracking, customer))
                if entries:
                    return entries
        except json.JSONDecodeError:
            pass

        reader = csv.DictReader(io.StringIO(text))
        entries: List[OcrEntry] = []
        for row in reader:
            tracking = (row.get("Sendungsnummer") or row.get("tracking_number") or "").strip()
            customer = (row.get("Kunde") or row.get("customer") or "").strip()
            if tracking and customer:
                entries.append(OcrEntry(tracking, customer))
        if not entries:
            LOGGER.warning("No entries could be parsed from OCR payload")
        return entries

    def fetch(self) -> List[OcrEntry] | None:
        content, last_modified = self._download()
        if not self._needs_update(content, last_modified):
            LOGGER.debug("OCR list unchanged; skipping update")
            return None
        entries = self._parse_content(content)
        if entries:
            upsert_ocr_entries([(entry.tracking_number, entry.customer) for entry in entries])
            LOGGER.info("Stored %d OCR entries", len(entries))
        return entries

    def load_cached(self) -> List[OcrEntry]:
        cached = [OcrEntry(tracking, customer) for tracking, customer in fetch_ocr_entries()]
        return cached


def ensure_logging_setup() -> None:
    CONFIG.log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(CONFIG.log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

