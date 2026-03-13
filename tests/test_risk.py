from __future__ import annotations

from datetime import datetime, timezone

from polymarket_fair_value_engine.config import RiskConfig
from polymarket_fair_value_engine.risk.inventory import InventoryLedger
from polymarket_fair_value_engine.risk.limits import RiskManager
from polymarket_fair_value_engine.types import FillEvent, ManagedOrder, OrderSide, OrderStatus, QuoteIntent, TokenSide


def test_inventory_ledger_tracks_realized_and_unrealized_pnl() -> None:
    ledger = InventoryLedger(starting_cash=100.0)
    now = datetime.now(timezone.utc)

    ledger.apply_fill(
        FillEvent(
            fill_id="f1",
            order_id="o1",
            market_id="m1",
            token_id="yes-1",
            token_side=TokenSide.YES,
            side=OrderSide.BUY,
            price=0.40,
            size=10.0,
            timestamp=now,
            fair_value_at_order=0.50,
            mid_at_order=0.40,
        )
    )
    ledger.apply_fill(
        FillEvent(
            fill_id="f2",
            order_id="o2",
            market_id="m1",
            token_id="yes-1",
            token_side=TokenSide.YES,
            side=OrderSide.SELL,
            price=0.60,
            size=4.0,
            timestamp=now,
            fair_value_at_order=0.55,
            mid_at_order=0.55,
        )
    )

    snapshot = ledger.pnl_snapshot(timestamp=now, mark_prices={"m1": 0.50})

    assert ledger.position("m1").yes_contracts == 6.0
    assert round(snapshot.realized_pnl, 6) == 0.8
    assert round(snapshot.unrealized_pnl, 6) == 0.6
    assert round(snapshot.total_pnl, 6) == 1.4


def test_risk_manager_rejects_quotes_that_exceed_market_notional_limit() -> None:
    risk_manager = RiskManager(
        RiskConfig(
            max_notional_per_market=5.0,
            max_gross_exposure=10.0,
            max_net_exposure_per_series=10.0,
            max_order_size=100.0,
            max_open_orders=5,
            stale_data_seconds=20,
        )
    )
    ledger = InventoryLedger(starting_cash=100.0)
    now = datetime.now(timezone.utc)
    quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.60,
        size=10.0,
        fair_value=0.70,
        reference_mid=0.55,
        created_at=now,
        reason="oversized_yes_bid",
    )

    result = risk_manager.filter_quotes(
        quotes=(quote,),
        inventory=ledger,
        market_id="m1",
        market_series="btc-updown-5m",
        mark_yes=0.60,
        market_series_map={"m1": "btc-updown-5m"},
        open_orders=[],
    )

    assert result.approved_quotes == ()
    assert result.rejected_reasons == ("oversized_yes_bid:market_notional",)


def test_risk_manager_accumulates_market_notional_and_gross_across_approved_quotes() -> None:
    risk_manager = RiskManager(
        RiskConfig(
            max_notional_per_market=7.5,
            max_gross_exposure=7.5,
            max_net_exposure_per_series=100.0,
            max_order_size=100.0,
            max_open_orders=5,
            stale_data_seconds=20,
        )
    )
    ledger = InventoryLedger(starting_cash=100.0)
    now = datetime.now(timezone.utc)
    first_quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.40,
        size=10.0,
        fair_value=0.50,
        reference_mid=0.40,
        created_at=now,
        reason="first_yes_bid",
    )
    second_quote = QuoteIntent(
        market_id="m1",
        token_id="no-1",
        token_side=TokenSide.NO,
        side=OrderSide.BUY,
        price=0.40,
        size=10.0,
        fair_value=0.50,
        reference_mid=0.60,
        created_at=now,
        reason="second_no_bid",
    )

    result = risk_manager.filter_quotes(
        quotes=(first_quote, second_quote),
        inventory=ledger,
        market_id="m1",
        market_series="btc-updown-5m",
        mark_yes=0.50,
        market_series_map={"m1": "btc-updown-5m"},
        open_orders=[],
    )

    assert result.approved_quotes == (first_quote,)
    assert result.rejected_reasons == ("second_no_bid:market_notional",)


def test_risk_manager_accumulates_series_exposure_and_open_orders() -> None:
    risk_manager = RiskManager(
        RiskConfig(
            max_notional_per_market=100.0,
            max_gross_exposure=100.0,
            max_net_exposure_per_series=12.0,
            max_order_size=100.0,
            max_open_orders=2,
            stale_data_seconds=20,
        )
    )
    ledger = InventoryLedger(starting_cash=100.0)
    now = datetime.now(timezone.utc)
    first_quote = QuoteIntent(
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.30,
        size=6.0,
        fair_value=0.50,
        reference_mid=0.50,
        created_at=now,
        reason="series_yes_1",
    )
    second_quote = QuoteIntent(
        market_id="m1",
        token_id="yes-2",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.30,
        size=6.0,
        fair_value=0.50,
        reference_mid=0.50,
        created_at=now,
        reason="series_yes_2",
    )
    third_quote = QuoteIntent(
        market_id="m1",
        token_id="yes-3",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.30,
        size=1.0,
        fair_value=0.50,
        reference_mid=0.50,
        created_at=now,
        reason="series_yes_3",
    )

    result = risk_manager.filter_quotes(
        quotes=(first_quote, second_quote, third_quote),
        inventory=ledger,
        market_id="m1",
        market_series="btc-updown-5m",
        mark_yes=0.50,
        market_series_map={"m1": "btc-updown-5m"},
        open_orders=[],
    )

    assert result.approved_quotes == (first_quote, second_quote)
    assert result.rejected_reasons == ("series_yes_3:series_net_exposure",)

    open_order = ManagedOrder(
        order_id="o1",
        market_id="m1",
        token_id="yes-1",
        token_side=TokenSide.YES,
        side=OrderSide.BUY,
        price=0.30,
        size=1.0,
        remaining_size=1.0,
        status=OrderStatus.OPEN,
        created_at=now,
        updated_at=now,
        reason="existing_order",
    )

    open_order_risk_manager = RiskManager(
        RiskConfig(
            max_notional_per_market=100.0,
            max_gross_exposure=100.0,
            max_net_exposure_per_series=100.0,
            max_order_size=100.0,
            max_open_orders=2,
            stale_data_seconds=20,
        )
    )

    open_order_result = open_order_risk_manager.filter_quotes(
        quotes=(first_quote, second_quote),
        inventory=ledger,
        market_id="m1",
        market_series="btc-updown-5m",
        mark_yes=0.50,
        market_series_map={"m1": "btc-updown-5m"},
        open_orders=[open_order],
    )

    assert open_order_result.approved_quotes == (first_quote,)
    assert open_order_result.rejected_reasons == ("series_yes_2:max_open_orders",)
