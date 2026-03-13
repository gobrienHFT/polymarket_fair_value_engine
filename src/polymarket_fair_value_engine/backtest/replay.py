from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.types import BookLevel, MarketFamily, MarketState, NormalizedMarket, TokenOrderBook


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _book_from_dict(payload: dict[str, Any] | None) -> TokenOrderBook | None:
    if not payload:
        return None
    bids = tuple(BookLevel(price=float(level[0]), size=float(level[1])) for level in payload.get("bids", []))
    asks = tuple(BookLevel(price=float(level[0]), size=float(level[1])) for level in payload.get("asks", []))
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
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            market_payload = payload["market"]
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
    return states

