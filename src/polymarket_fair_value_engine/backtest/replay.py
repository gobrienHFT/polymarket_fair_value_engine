from __future__ import annotations

import json
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.types import BookLevel, MarketFamily, MarketState, NormalizedMarket, TokenOrderBook


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Replay datetime is invalid: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Replay datetime must include a timezone offset")
    return parsed


def _book_from_dict(payload: dict[str, Any] | None) -> TokenOrderBook | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("Replay order book must be a JSON object")
    if not payload:
        return None

    def parse_levels(raw_levels: Any) -> tuple[BookLevel, ...]:
        if not isinstance(raw_levels, list):
            raise ValueError("Replay order-book levels must be a JSON array")
        levels: list[BookLevel] = []
        for level in raw_levels:
            if not isinstance(level, list) or len(level) < 2:
                raise ValueError("Replay order-book levels must contain [price, size] pairs")
            try:
                price = float(level[0])
                size = float(level[1])
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Replay order-book levels must contain numeric values") from exc
            if not isfinite(price) or not isfinite(size):
                raise ValueError("Replay order-book levels must contain finite values")
            levels.append(BookLevel(price=price, size=size))
        return tuple(levels)

    bids = parse_levels(payload.get("bids", []))
    asks = parse_levels(payload.get("asks", []))
    return TokenOrderBook(
        token_id=str(payload["token_id"]),
        bids=bids,
        asks=asks,
        timestamp=_parse_datetime(payload["timestamp"]),
        source=str(payload.get("source", "replay")),
    )


def load_replay_file(path: str | Path) -> list[MarketState]:
    file_path = Path(path)
    states: list[MarketState] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid replay JSON on line {line_number}: {exc.msg}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Replay row on line {line_number} must be a JSON object")
            market_payload = payload["market"]
            if not isinstance(market_payload, dict):
                raise ValueError(f"Replay market on line {line_number} must be a JSON object")
            market = NormalizedMarket(
                market_id=str(market_payload["market_id"]),
                slug=str(market_payload["slug"]),
                question=str(market_payload["question"]),
                series=str(market_payload["series"]),
                family=MarketFamily(str(market_payload["family"])),
                asset=market_payload.get("asset"),
                end_ts=_parse_datetime(market_payload["end_ts"]),
                start_ts=_parse_datetime(market_payload["start_ts"]) if market_payload.get("start_ts") else None,
                yes_token_id=str(market_payload["yes_token_id"]),
                no_token_id=str(market_payload["no_token_id"]),
                last_yes_price=market_payload.get("last_yes_price"),
                last_no_price=market_payload.get("last_no_price"),
                tick_size=float(market_payload.get("tick_size", 0.01)),
                size_tick=float(market_payload.get("size_tick", 0.1)),
                metadata=dict(market_payload.get("metadata", {})),
            )
            states.append(
                MarketState(
                    market=market,
                    yes_book=_book_from_dict(payload.get("yes_book")),
                    no_book=_book_from_dict(payload.get("no_book")),
                    observed_at=_parse_datetime(payload["observed_at"]),
                    reference_price=payload.get("reference_price"),
                    stale=bool(payload.get("stale", False)),
                )
            )
    if not states:
        raise ValueError(f"Replay file {file_path} contains no market states")
    return states
