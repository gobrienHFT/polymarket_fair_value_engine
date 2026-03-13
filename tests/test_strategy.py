from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.config import StrategyConfig
from polymarket_fair_value_engine.risk.inventory import InventoryPosition
from polymarket_fair_value_engine.strategy.passive_mm import PassiveMarketMaker
from polymarket_fair_value_engine.types import BookLevel, FairValueEstimate, MarketFamily, MarketState, NormalizedMarket, OrderSide, TokenOrderBook, TokenSide


def _state() -> MarketState:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    market = NormalizedMarket(
        market_id="m1",
        slug="btc-updown-5m-1767268800",
        question="Will Bitcoin be up in 5 minutes?",
        series="btc-updown-5m",
        family=MarketFamily.CRYPTO_UPDOWN,
        asset="BTC",
        end_ts=now + timedelta(minutes=5),
        yes_token_id="yes-1",
        no_token_id="no-1",
    )
    return MarketState(
        market=market,
        yes_book=TokenOrderBook(
            token_id="yes-1",
            bids=(BookLevel(price=0.48, size=100.0),),
            asks=(BookLevel(price=0.52, size=100.0),),
            timestamp=now,
        ),
        no_book=TokenOrderBook(
            token_id="no-1",
            bids=(BookLevel(price=0.48, size=100.0),),
            asks=(BookLevel(price=0.52, size=100.0),),
            timestamp=now,
        ),
        observed_at=now,
        reference_price=100000.0,
    )


def _fair_value() -> FairValueEstimate:
    return FairValueEstimate(
        market_id="m1",
        p_yes=0.50,
        p_no=0.50,
        model_name="baseline",
        uncertainty=0.01,
        reference_price=100000.0,
        market_mid=0.50,
    )


def _strategy() -> PassiveMarketMaker:
    return PassiveMarketMaker(
        StrategyConfig(
            poll_seconds=1,
            quote_half_spread=0.02,
            min_edge=0.01,
            inventory_skew_per_contract=0.003,
            quote_notional=20.0,
            min_order_usdc=5.0,
            price_tick=0.01,
            size_tick=0.1,
            reprice_threshold=0.01,
            reprice_cooldown_seconds=5,
        )
    )


def test_passive_strategy_quotes_both_sides_when_inventory_is_flat() -> None:
    decision = _strategy().evaluate(_state(), _fair_value(), InventoryPosition())

    reasons = {quote.reason for quote in decision.quotes}
    assert reasons == {"bid_side_buy_yes", "ask_side_buy_no"}
    assert all(quote.created_at == _state().observed_at for quote in decision.quotes)


def test_passive_strategy_sells_yes_when_inventory_is_long_yes() -> None:
    decision = _strategy().evaluate(_state(), _fair_value(), InventoryPosition(yes_contracts=8.0))

    assert any(quote.reason == "ask_side_sell_yes" and quote.side is OrderSide.SELL and quote.token_side is TokenSide.YES for quote in decision.quotes)


def test_passive_strategy_sells_no_on_bid_side_when_inventory_is_long_no() -> None:
    decision = _strategy().evaluate(_state(), _fair_value(), InventoryPosition(no_contracts=3.0))

    assert any(quote.reason == "bid_side_sell_no" and quote.side is OrderSide.SELL and quote.token_side is TokenSide.NO for quote in decision.quotes)
