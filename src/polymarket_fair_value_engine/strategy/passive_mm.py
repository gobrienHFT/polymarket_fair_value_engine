from __future__ import annotations

import math

from polymarket_fair_value_engine.config import StrategyConfig
from polymarket_fair_value_engine.risk.inventory import InventoryPosition
from polymarket_fair_value_engine.strategy.base import Strategy
from polymarket_fair_value_engine.types import FairValueEstimate, MarketState, OrderSide, QuoteIntent, StrategyDecision, TokenSide


def _clip_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def _floor_to_tick(value: float, tick: float) -> float:
    return math.floor(value / tick) * tick


def _size_for_notional(notional: float, price: float, size_tick: float) -> float:
    if price <= 0.0:
        return 0.0
    raw = notional / price
    return max(0.0, _floor_to_tick(raw, size_tick))


class PassiveMarketMaker(Strategy):
    name = "passive_mm"

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def evaluate(
        self,
        state: MarketState,
        fair_value: FairValueEstimate,
        inventory_position: InventoryPosition,
    ) -> StrategyDecision:
        spread_half = max(self.config.quote_half_spread, (state.spread or 0.0) / 2.0)
        inventory_skew = inventory_position.net_yes_exposure * self.config.inventory_skew_per_contract

        target_yes_bid = _clip_probability(fair_value.p_yes - spread_half - fair_value.uncertainty - inventory_skew)
        target_yes_ask = _clip_probability(fair_value.p_yes + spread_half + fair_value.uncertainty + inventory_skew)

        quotes: list[QuoteIntent] = []
        bid_size = _size_for_notional(self.config.quote_notional, target_yes_bid, self.config.size_tick)
        yes_edge = fair_value.p_yes - target_yes_bid
        if bid_size > 0.0 and bid_size * target_yes_bid >= self.config.min_order_usdc and yes_edge >= self.config.min_edge:
            if inventory_position.no_contracts > 0.0:
                no_sell_price = _clip_probability(1.0 - target_yes_bid)
                quotes.append(
                    QuoteIntent(
                        market_id=state.market.market_id,
                        token_id=state.market.no_token_id,
                        token_side=TokenSide.NO,
                        side=OrderSide.SELL,
                        price=round(_floor_to_tick(no_sell_price, self.config.price_tick), 4),
                        size=min(inventory_position.no_contracts, bid_size),
                        fair_value=fair_value.p_no,
                        reference_mid=state.yes_mid,
                        created_at=state.observed_at,
                        reason="bid_side_sell_no",
                    )
                )
            else:
                quotes.append(
                    QuoteIntent(
                        market_id=state.market.market_id,
                        token_id=state.market.yes_token_id,
                        token_side=TokenSide.YES,
                        side=OrderSide.BUY,
                        price=round(_floor_to_tick(target_yes_bid, self.config.price_tick), 4),
                        size=bid_size,
                        fair_value=fair_value.p_yes,
                        reference_mid=state.yes_mid,
                        created_at=state.observed_at,
                        reason="bid_side_buy_yes",
                    )
                )

        ask_size = _size_for_notional(self.config.quote_notional, max(1.0 - target_yes_ask, 0.01), self.config.size_tick)
        ask_edge = target_yes_ask - fair_value.p_yes
        if ask_size > 0.0 and ask_edge >= self.config.min_edge:
            if inventory_position.yes_contracts > 0.0:
                quotes.append(
                    QuoteIntent(
                        market_id=state.market.market_id,
                        token_id=state.market.yes_token_id,
                        token_side=TokenSide.YES,
                        side=OrderSide.SELL,
                        price=round(_floor_to_tick(target_yes_ask, self.config.price_tick), 4),
                        size=min(inventory_position.yes_contracts, ask_size),
                        fair_value=fair_value.p_yes,
                        reference_mid=state.yes_mid,
                        created_at=state.observed_at,
                        reason="ask_side_sell_yes",
                    )
                )
            else:
                target_no_bid = _clip_probability(1.0 - target_yes_ask)
                no_edge = fair_value.p_no - target_no_bid
                no_size = _size_for_notional(self.config.quote_notional, target_no_bid, self.config.size_tick)
                if no_size > 0.0 and no_size * target_no_bid >= self.config.min_order_usdc and no_edge >= self.config.min_edge:
                    quotes.append(
                        QuoteIntent(
                            market_id=state.market.market_id,
                            token_id=state.market.no_token_id,
                            token_side=TokenSide.NO,
                            side=OrderSide.BUY,
                            price=round(_floor_to_tick(target_no_bid, self.config.price_tick), 4),
                            size=no_size,
                            fair_value=fair_value.p_no,
                            reference_mid=state.yes_mid,
                            created_at=state.observed_at,
                            reason="ask_side_buy_no",
                        )
                    )

        return StrategyDecision(
            market_id=state.market.market_id,
            fair_value=fair_value,
            quotes=tuple(quotes),
            diagnostics={
                "strategy": self.name,
                "inventory_skew": round(inventory_skew, 6),
                "target_yes_bid": round(target_yes_bid, 6),
                "target_yes_ask": round(target_yes_ask, 6),
                "observed_mid": state.yes_mid,
                "observed_spread": state.spread,
            },
        )
