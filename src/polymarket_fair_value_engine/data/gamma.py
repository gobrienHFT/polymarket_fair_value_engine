from __future__ import annotations

import logging
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


class GammaClient:
    def __init__(self, base_url: str, session: requests.Session | None = None, timeout: int = 12) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.setdefault("User-Agent", "pmfe/0.1")

    def get_markets(self, **params: Any) -> list[dict[str, Any]]:
        response = self.session.get(f"{self.base_url}/markets", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        LOGGER.warning("Unexpected Gamma payload shape", extra={"context": {"type": type(payload).__name__}})
        return []

    def get_market_by_slug(self, slug: str) -> list[dict[str, Any]]:
        return self.get_markets(slug=slug)

