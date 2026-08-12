from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from polymarket_fair_value_engine.types import MarketFamily, NormalizedMarket


def _to_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def normalize_gamma_market(raw: dict[str, Any], tick_size: float = 0.01, size_tick: float = 0.1) -> NormalizedMarket | None:
    if not isinstance(raw, dict):
        return None

    slug_value = raw.get("slug")
    question_value = raw.get("question")
    slug = str(slug_value).strip() if slug_value is not None else ""
    question = str(question_value).strip() if question_value is not None else ""
    raw_market_id = raw.get("conditionId", raw.get("condition_id", raw.get("id", slug)))
    market_id = str(raw_market_id).strip() if raw_market_id is not None else ""
    outcomes = [str(item).strip().lower() for item in _to_list(raw.get("outcomes"))]
    token_ids = [str(item).strip() for item in _to_list(raw.get("clobTokenIds"))]
    try:
        prices = [float(item) for item in _to_list(raw.get("outcomePrices"))]
    except (TypeError, ValueError, OverflowError):
        return None
    if any(not math.isfinite(price) or not 0.0 <= price <= 1.0 for price in prices):
        return None

    if (
        not market_id
        or not slug
        or not question
        or len(outcomes) < 2
        or len(token_ids) < 2
        or any(not token_id for token_id in token_ids)
        or len(set(token_ids)) != len(token_ids)
    ):
        return None
    if "up" not in outcomes or "down" not in outcomes:
        return None

    up_index = outcomes.index("up")
    down_index = outcomes.index("down")
    end_value = raw.get("endDate") or raw.get("end_date") or raw.get("endDateIso")
    if not end_value:
        return None

    last_yes = prices[up_index] if len(prices) > up_index else None
    last_no = prices[down_index] if len(prices) > down_index else None
    series = slug.rsplit("-", 1)[0] if "-" in slug else slug

    try:
        end_ts = _parse_iso(str(end_value))
    except (TypeError, ValueError):
        return None
    if end_ts.tzinfo is None or end_ts.utcoffset() is None:
        return None

    try:
        return NormalizedMarket(
            market_id=market_id,
            slug=slug,
            question=question,
            series=series,
            family=MarketFamily.CRYPTO_UPDOWN,
            asset="BTC" if slug.startswith("btc-") else None,
            end_ts=end_ts,
            yes_token_id=token_ids[up_index],
            no_token_id=token_ids[down_index],
            last_yes_price=last_yes,
            last_no_price=last_no,
            tick_size=tick_size,
            size_tick=size_tick,
            metadata={"outcomes": outcomes},
        )
    except ValueError:
        return None
