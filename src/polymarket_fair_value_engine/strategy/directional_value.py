from __future__ import annotations

from polymarket_fair_value_engine.config import StrategyConfig
from polymarket_fair_value_engine.risk.inventory import InventoryPosition
from polymarket_fair_value_engine.strategy.base import Strategy
from polymarket_fair_value_engine.types import FairValueEstimate, MarketState, OrderSide, QuoteIntent, StrategyDecision, TokenSide


class DirectionalValueStrategy(Strategy):
    """Optional legacy-style directional buyer scaffold."""

    name = "directional_value"

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def evaluate(
        self,
        state: MarketState,
        fair_value: FairValueEstimate,
        inventory_position: InventoryPosition,
    ) -> StrategyDecision:
        _ = inventory_position
        quotes: list[QuoteIntent] = []
        if state.yes_mid is not None and fair_value.p_yes - state.yes_mid >= self.config.min_edge:
            size = max(self.config.size_tick, round(self.config.quote_notional / max(state.yes_mid, 0.01), 1))
            quotes.append(
                QuoteIntent(
                    market_id=state.market.market_id,
                    token_id=state.market.yes_token_id,
                    token_side=TokenSide.YES,
                    side=OrderSide.BUY,
                    price=state.yes_mid,
                    size=size,
                    fair_value=fair_value.p_yes,
                    reference_mid=state.yes_mid,
                    created_at=state.observed_at,
                    reason="directional_yes_buy",
                )
            )
        return StrategyDecision(market_id=state.market.market_id, fair_value=fair_value, quotes=tuple(quotes))

