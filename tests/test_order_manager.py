from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.config import StrategyConfig
from polymarket_fair_value_engine.execution.order_manager import OrderManager
from polymarket_fair_value_engine.types import ManagedOrder, OrderSide, OrderStatus, QuoteIntent, TokenSide


def _strategy_config() -> StrategyConfig:
    return StrategyConfig(
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


def test_order_manager_replaces_materially_changed_quotes_and_cancels_stale_ones() -> None:
    now = datetime.now(timezone.utc)
    manager = OrderManager(_strategy_config())
    existing_bid = ManagedOrder(
        order_id="o1",
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.45,
        size=10.0,
        remaining_size=10.0,
        status=OrderStatus.OPEN,
        created_at=now - timedelta(seconds=30),
        updated_at=now - timedelta(seconds=30),
        reason="bid_side_buy_yes",
    )
    stale_ask = ManagedOrder(
        order_id="o2",
        market_id="m1",
        token_id="no-1",
        token_side=TokenSide.NO,
        side=OrderSide.BUY,
        price=0.30,
        size=10.0,
        remaining_size=10.0,
        status=OrderStatus.OPEN,
        created_at=now - timedelta(seconds=30),
        updated_at=now - timedelta(seconds=30),
        reason="ask_side_buy_no",
    )
    desired_bid = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.47,
        size=10.0,
        fair_value=0.60,
        reference_mid=0.50,
        created_at=now,
        reason="bid_side_buy_yes",
    )

    actions = manager.reconcile((desired_bid,), [existing_bid, stale_ask], now)

    assert [action.action for action in actions] == ["cancel", "cancel", "place"]
    assert actions[0].existing_order_id == "o2"
    assert actions[1].existing_order_id == "o1"
    assert actions[2].desired == desired_bid


def test_order_manager_keeps_quotes_inside_reprice_threshold() -> None:
    now = datetime.now(timezone.utc)
    manager = OrderManager(_strategy_config())
    existing_bid = ManagedOrder(
        order_id="o1",
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.45,
        size=10.0,
        remaining_size=10.0,
        status=OrderStatus.OPEN,
        created_at=now - timedelta(seconds=30),
        updated_at=now - timedelta(seconds=30),
        reason="bid_side_buy_yes",
    )
    desired_bid = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.455,
        size=10.0,
        fair_value=0.60,
        reference_mid=0.50,
        created_at=now,
        reason="bid_side_buy_yes",
    )

    assert manager.reconcile((desired_bid,), [existing_bid], now) == []

