from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from polymarket_fair_value_engine.types import BookLevel, TokenOrderBook


def _parse_levels(raw_levels: Any) -> tuple[BookLevel, ...]:
    levels: list[BookLevel] = []
    if not isinstance(raw_levels, list):
        return tuple(levels)
    for entry in raw_levels:
        if isinstance(entry, dict):
            price = float(entry.get("price", 0.0))
            size = float(entry.get("size", entry.get("quantity", 0.0)))
        elif isinstance(entry, list) and len(entry) >= 2:
            price = float(entry[0])
            size = float(entry[1])
        else:
            continue
        if price > 0.0 and size > 0.0:
            levels.append(BookLevel(price=price, size=size))
    return tuple(levels)


class ClobRestClient:
    def __init__(self, host: str, session: requests.Session | None = None, timeout: int = 12) -> None:
        self.host = host.rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.setdefault("User-Agent", "pmfe/0.1")

    def get_order_book(self, token_id: str) -> TokenOrderBook:
        response = self.session.get(
            f"{self.host}/book",
            params={"token_id": token_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("book", payload) if isinstance(payload, dict) else {}
        bids = _parse_levels(data.get("bids", []))
        asks = _parse_levels(data.get("asks", []))
        return TokenOrderBook(
            token_id=token_id,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
            source="clob_rest",
        )

