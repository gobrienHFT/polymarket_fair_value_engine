from __future__ import annotations

from polymarket_fair_value_engine.types import MarketState


def market_mid_probability(state: MarketState) -> float | None:
    return state.yes_mid


def market_spread(state: MarketState) -> float:
    return state.spread or 0.0

