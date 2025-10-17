"""Fetch and parse delivery lists from the remote WebDAV share."""
from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional
from urllib.parse import urljoin

import requests

from .config import PREFERRED_FILENAMES, REMOTE_DAV_URL
from .models import Delivery

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RemoteFile:
    """Metadata describing a file hosted on the WebDAV share."""

    href: str
    name: str
    modified: datetime
    etag: str | None = None


class WebDavClient:
    """Very small WebDAV client for read-only access."""

    def __init__(self, base_url: str = REMOTE_DAV_URL) -> None:
        self.base_url = base_url.rstrip("/") + "/"

    def list_files(self) -> List[RemoteFile]:
        headers = {"Depth": "1"}
        response = requests.request("PROPFIND", self.base_url, headers=headers)
        response.raise_for_status()
        return list(_parse_propfind_response(self.base_url, response.text))

    def download(self, remote_file: RemoteFile) -> bytes:
        response = requests.get(remote_file.href)
        response.raise_for_status()
        return response.content


def _parse_propfind_response(base_url: str, body: str) -> Iterable[RemoteFile]:
    """Parse a minimal subset of the PROPFIND XML response."""

    import xml.etree.ElementTree as ET

    namespace = {
        "d": "DAV:",
    }
    root = ET.fromstring(body)
    for response in root.findall("d:response", namespace):
        href_el = response.find("d:href", namespace)
        if href_el is None:
            continue
        href = href_el.text or ""
        if not href.lower().startswith("http"):
            href = urljoin(base_url, href)
        if href.rstrip("/") == base_url.rstrip("/"):
            # Ignore directory entry itself.
            continue
        prop = response.find("d:propstat/d:prop", namespace)
        if prop is None:
            continue
        name = href.rstrip("/").split("/")[-1]
        modified_text = prop.findtext("d:getlastmodified", default="", namespaces=namespace)
        etag_text = prop.findtext("d:getetag", default="", namespaces=namespace)
        try:
            modified = datetime.strptime(modified_text, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            modified = datetime.utcnow()
        yield RemoteFile(
            href=href,
            name=name,
            modified=modified,
            etag=etag_text.strip('"') or None,
        )


class DeliveryFetcher:
    """High-level helper for downloading and parsing delivery data."""

    def __init__(self, client: Optional[WebDavClient] = None) -> None:
        self.client = client or WebDavClient()
        self._last_etag: str | None = None

    def fetch_latest(self) -> List[Delivery]:
        files = self.client.list_files()
        if not files:
            logger.warning("No files available on the WebDAV share")
            return []
        files.sort(key=self._file_sort_key, reverse=True)
        chosen = files[0]
        content = self.client.download(chosen)
        if chosen.etag:
            self._last_etag = chosen.etag
        return self._parse_content(content)

    def has_updates(self) -> bool:
        files = self.client.list_files()
        if not files:
            return False
        files.sort(key=self._file_sort_key, reverse=True)
        latest = files[0]
        if latest.etag and self._last_etag:
            return latest.etag != self._last_etag
        return True

    @staticmethod
    def _file_sort_key(remote_file: RemoteFile) -> tuple[int, datetime]:
        preferred_index = len(PREFERRED_FILENAMES)
        try:
            preferred_index = PREFERRED_FILENAMES.index(remote_file.name)
        except ValueError:
            pass
        return -preferred_index, remote_file.modified

    @staticmethod
    def _parse_content(content: bytes) -> List[Delivery]:
        text = content.decode("utf-8", errors="replace")
        if text.lstrip().startswith("{") or text.lstrip().startswith("["):
            return _parse_json(text)
        return _parse_csv(text)


def _parse_json(text: str) -> List[Delivery]:
    data = json.loads(text)
    deliveries: List[Delivery] = []
    if isinstance(data, dict):
        data = data.get("deliveries") or data.get("items") or []
    for item in data:
        tracking = str(item.get("tracking_number") or item.get("tracking") or item.get("sendungsnummer") or "").strip()
        customer = str(item.get("customer") or item.get("kunde") or "").strip()
        if tracking:
            deliveries.append(Delivery(tracking_number=tracking, customer=customer, extra=item))
    return deliveries


def _parse_csv(text: str) -> List[Delivery]:
    reader = csv.DictReader(io.StringIO(text))
    deliveries: List[Delivery] = []
    for row in reader:
        tracking = str(row.get("tracking_number") or row.get("tracking") or row.get("sendungsnummer") or "").strip()
        customer = str(row.get("customer") or row.get("kunde") or "").strip()
        if tracking:
            deliveries.append(Delivery(tracking_number=tracking, customer=customer, extra=row))
    return deliveries
