from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from io import StringIO
from typing import Iterable
from urllib.parse import urljoin

import requests

from .data_models import Shipment


@dataclass
class RemoteConfig:
    base_url: str
    filename: str
    verify_tls: bool = True


class RemoteShipmentFetcher:
    def __init__(self, config: RemoteConfig, *, timeout: int = 10) -> None:
        self.config = config
        self.timeout = timeout
        self._etag: str | None = None

    @property
    def target_url(self) -> str:
        return urljoin(self.config.base_url.rstrip("/") + "/", self.config.filename)

    def fetch_if_modified(self) -> list[Shipment] | None:
        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag
        response = requests.get(
            self.target_url,
            headers=headers,
            timeout=self.timeout,
            verify=self.config.verify_tls,
        )
        if response.status_code == requests.codes.not_modified:
            return None
        response.raise_for_status()
        self._etag = response.headers.get("ETag", self._etag)
        return list(self._parse_payload(response.text))

    def _parse_payload(self, raw: str) -> Iterable[Shipment]:
        raw = raw.strip()
        if not raw:
            return []
        if raw.startswith("{") or raw.startswith("["):
            return self._parse_json(raw)
        return self._parse_csv(raw)

    def _parse_json(self, raw: str) -> Iterable[Shipment]:
        payload = json.loads(raw)
        shipments = []
        if isinstance(payload, dict):
            payload = payload.get("shipments", [])
        for entry in payload:
            tracking_number = str(entry.get("tracking_number") or entry.get("sendungsnummer") or "").strip()
            customer_name = str(entry.get("customer") or entry.get("kunde") or "").strip()
            if not tracking_number:
                continue
            shipments.append(
                Shipment(
                    tracking_number=tracking_number,
                    customer_name=customer_name,
                    raw_payload=entry,
                )
            )
        return shipments

    def _parse_csv(self, raw: str) -> Iterable[Shipment]:
        reader = csv.DictReader(StringIO(raw), delimiter=";", skipinitialspace=True)
        shipments: list[Shipment] = []
        for row in reader:
            tracking_number = (row.get("tracking_number") or row.get("sendungsnummer") or "").strip()
            customer_name = (row.get("customer") or row.get("kunde") or "").strip()
            if not tracking_number:
                continue
            shipments.append(
                Shipment(
                    tracking_number=tracking_number,
                    customer_name=customer_name,
                    raw_payload=row,
                )
            )
        return shipments
