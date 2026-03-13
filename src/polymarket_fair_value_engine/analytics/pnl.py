from __future__ import annotations

from polymarket_fair_value_engine.types import FairValueEstimate, MarketState


def mark_yes_price(state: MarketState, fair_value: FairValueEstimate) -> float:
    return state.yes_mid if state.yes_mid is not None else fair_value.p_yes

