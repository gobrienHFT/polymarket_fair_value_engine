from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.execution.paper import PaperExecutionEngine
from polymarket_fair_value_engine.types import BookLevel, MarketFamily, MarketState, NormalizedMarket, OrderAction, OrderSide, QuoteIntent, TokenOrderBook, TokenSide


def _market_state(now: datetime, ask: float, bid: float) -> MarketState:
    market = NormalizedMarket(
        market_id="m1",
        slug="btc-updown-5m-1",
        question="Will Bitcoin be up in 5 minutes?",
        series="btc-updown-5m",
        family=MarketFamily.CRYPTO_UPDOWN,
        asset="BTC",
        end_ts=now + timedelta(minutes=5),
        yes_token_id="yes-1",
        no_token_id="no-1",
    )
    yes_book = TokenOrderBook(
        token_id="yes-1",
        bids=(BookLevel(price=bid, size=100.0),),
        asks=(BookLevel(price=ask, size=100.0),),
        timestamp=now,
    )
    no_book = TokenOrderBook(
        token_id="no-1",
        bids=(BookLevel(price=1.0 - ask, size=100.0),),
        asks=(BookLevel(price=1.0 - bid, size=100.0),),
        timestamp=now,
    )
    return MarketState(market=market, yes_book=yes_book, no_book=no_book, observed_at=now, reference_price=100000.0)


def test_paper_execution_fills_buy_orders_on_touch() -> None:
    now = datetime.now(timezone.utc)
    engine = PaperExecutionEngine(starting_cash=100.0)
    quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.55,
        size=10.0,
        fair_value=0.60,
        reference_mid=0.50,
        created_at=now,
        reason="bid_side_buy_yes",
    )

    engine.apply_actions([OrderAction(action="place", desired=quote)], now)
    fills = engine.process_market_state(_market_state(now, ask=0.54, bid=0.52))

    assert len(fills) == 1
    assert engine.inventory.position("m1").yes_contracts == 10.0
    assert round(engine.inventory.cash, 6) == 94.5


def test_paper_execution_realizes_pnl_on_sell_fill() -> None:
    now = datetime.now(timezone.utc)
    engine = PaperExecutionEngine(starting_cash=100.0)
    buy_quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.55,
        size=10.0,
        fair_value=0.60,
        reference_mid=0.50,
        created_at=now,
        reason="bid_side_buy_yes",
    )
    sell_quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.SELL,
        price=0.65,
        size=4.0,
        fair_value=0.60,
        reference_mid=0.60,
        created_at=now,
        reason="ask_side_sell_yes",
    )

    engine.apply_actions([OrderAction(action="place", desired=buy_quote)], now)
    engine.process_market_state(_market_state(now, ask=0.54, bid=0.52))
    engine.apply_actions([OrderAction(action="place", desired=sell_quote)], now)
    fills = engine.process_market_state(_market_state(now, ask=0.66, bid=0.65))

    assert len(fills) == 1
    assert engine.inventory.position("m1").yes_contracts == 6.0
    assert round(engine.inventory.realized_pnl, 6) == 0.4


def test_paper_execution_can_require_strict_cross() -> None:
    now = datetime.now(timezone.utc)
    engine = PaperExecutionEngine(starting_cash=100.0, touch_fill_only=False)
    quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.55,
        size=10.0,
        fair_value=0.60,
        reference_mid=0.50,
        created_at=now,
        reason="bid_side_buy_yes",
    )

    engine.apply_actions([OrderAction(action="place", desired=quote)], now)
    no_fill = engine.process_market_state(_market_state(now, ask=0.55, bid=0.53))
    yes_fill = engine.process_market_state(_market_state(now, ask=0.54, bid=0.53))

    assert no_fill == []
    assert len(yes_fill) == 1
