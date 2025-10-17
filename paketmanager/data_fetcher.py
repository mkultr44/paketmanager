"""Fetch and parse delivery lists from the remote SFTP server."""
from __future__ import annotations

import csv
import io
import json
import logging
from contextlib import contextmanager
from typing import Generator, List, Optional

import paramiko

from .config import (
    SFTP_HOST,
    SFTP_PASSWORD,
    SFTP_PORT,
    SFTP_REMOTE_PATH,
    SFTP_USERNAME,
)
from .models import Delivery

logger = logging.getLogger(__name__)


class SFTPClient:
    """Small helper around Paramiko to download a single file via SFTP."""

    def __init__(
        self,
        host: str = SFTP_HOST,
        port: int = SFTP_PORT,
        username: str = SFTP_USERNAME,
        password: str = SFTP_PASSWORD,
        remote_path: str = SFTP_REMOTE_PATH,
        timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.remote_path = remote_path
        self.timeout = timeout

    @contextmanager
    def _open_sftp(self) -> Generator[paramiko.SFTPClient, None, None]:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            look_for_keys=False,
            allow_agent=False,
            timeout=self.timeout,
        )
        try:
            sftp = client.open_sftp()
            try:
                yield sftp
            finally:
                sftp.close()
        finally:
            client.close()

    def stat(self) -> Optional[paramiko.SFTPAttributes]:
        try:
            with self._open_sftp() as sftp:
                return sftp.stat(self.remote_path)
        except FileNotFoundError:
            logger.warning("Remote delivery file %s not found", self.remote_path)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to stat remote file via SFTP: %s", exc, exc_info=True)
        return None

    def download(self) -> tuple[Optional[paramiko.SFTPAttributes], bytes]:
        try:
            with self._open_sftp() as sftp:
                attrs = sftp.stat(self.remote_path)
                with sftp.open(self.remote_path, "rb") as remote_file:
                    content = remote_file.read()
        except FileNotFoundError:
            logger.warning("Remote delivery file %s not found", self.remote_path)
            return None, b""
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to download remote file via SFTP: %s", exc, exc_info=True)
            return None, b""
        return attrs, content


class DeliveryFetcher:
    """High-level helper for downloading and parsing delivery data."""

    def __init__(self, client: Optional[SFTPClient] = None) -> None:
        self.client = client or SFTPClient()
        self._last_mtime: float | None = None

    def fetch_latest(self) -> List[Delivery]:
        attrs, content = self.client.download()
        if attrs is not None and attrs.st_mtime is not None:
            self._last_mtime = float(attrs.st_mtime)
        if not content:
            return []
        return self._parse_content(content)

    def has_updates(self) -> bool:
        attrs = self.client.stat()
        if attrs is None or attrs.st_mtime is None:
            return False
        current_mtime = float(attrs.st_mtime)
        if self._last_mtime is None:
            return True
        return current_mtime > self._last_mtime

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
        tracking = str(
            item.get("tracking_number")
            or item.get("tracking")
            or item.get("sendungsnummer")
            or ""
        ).strip()
        customer = str(item.get("customer") or item.get("kunde") or "").strip()
        if tracking:
            deliveries.append(Delivery(tracking_number=tracking, customer=customer, extra=item))
    return deliveries


def _parse_csv(text: str) -> List[Delivery]:
    reader = csv.DictReader(io.StringIO(text))
    deliveries: List[Delivery] = []
    for row in reader:
        tracking = str(
            row.get("tracking_number")
            or row.get("tracking")
            or row.get("sendungsnummer")
            or ""
        ).strip()
        customer = str(row.get("customer") or row.get("kunde") or "").strip()
        if tracking:
            deliveries.append(Delivery(tracking_number=tracking, customer=customer, extra=row))
    return deliveries
