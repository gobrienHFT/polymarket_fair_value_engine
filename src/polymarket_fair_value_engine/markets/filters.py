from __future__ import annotations

from datetime import datetime, timezone

from polymarket_fair_value_engine.types import MarketState, NormalizedMarket


def market_within_expiry_window(market: NormalizedMarket, now: datetime, max_minutes_to_expiry: int) -> bool:
    seconds = market.seconds_to_expiry(now)
    return seconds > 0 and seconds <= max_minutes_to_expiry * 60


def in_no_trade_window(market: NormalizedMarket, now: datetime, no_trade_window_seconds: int) -> bool:
    return market.seconds_to_expiry(now) <= no_trade_window_seconds


def is_state_stale(state: MarketState, stale_data_seconds: int, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    latest_ts = state.observed_at
    if state.yes_book is not None:
        latest_ts = max(latest_ts, state.yes_book.timestamp)
    if state.no_book is not None:
        latest_ts = max(latest_ts, state.no_book.timestamp)
    return (now - latest_ts).total_seconds() > stale_data_seconds


def has_sane_binary_books(state: MarketState) -> bool:
    yes_mid = state.yes_mid
    spread = state.spread
    return yes_mid is not None and 0.0 < yes_mid < 1.0 and spread is not None and spread >= 0.0

