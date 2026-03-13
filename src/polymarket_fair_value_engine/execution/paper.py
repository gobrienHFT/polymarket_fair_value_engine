from __future__ import annotations

import itertools
from datetime import datetime

from polymarket_fair_value_engine.risk.inventory import InventoryLedger
from polymarket_fair_value_engine.types import FillEvent, ManagedOrder, MarketState, OrderAction, OrderSide, OrderStatus, PnLSnapshot, QuoteIntent, TokenSide


class PaperExecutionEngine:
    """Simple paper engine with deterministic fill rules.

    When ``touch_fill_only`` is true, an order fills when the market touches or crosses
    the quoted price. When it is false, the simulator requires a strict cross.
    """

    def __init__(self, starting_cash: float, touch_fill_only: bool = True) -> None:
        self.inventory = InventoryLedger(starting_cash=starting_cash)
        self.touch_fill_only = touch_fill_only
        self.order_history: list[ManagedOrder] = []
        self.fill_history: list[FillEvent] = []
        self.pnl_history: list[PnLSnapshot] = []
        self._open_orders: dict[str, ManagedOrder] = {}
        self._order_ids = itertools.count(1)
        self._fill_ids = itertools.count(1)

    @property
    def open_orders(self) -> list[ManagedOrder]:
        return list(self._open_orders.values())

    def open_orders_for_market(self, market_id: str) -> list[ManagedOrder]:
        return [order for order in self._open_orders.values() if order.market_id == market_id]

    def apply_actions(self, actions: list[OrderAction], now: datetime) -> None:
        for action in actions:
            if action.action == "cancel" and action.existing_order_id:
                self._cancel_order(action.existing_order_id, now)
            if action.action == "place" and action.desired is not None:
                self._place_order(action.desired, now)

    def _place_order(self, quote: QuoteIntent, now: datetime) -> ManagedOrder:
        order = ManagedOrder(
            order_id=f"paper-{next(self._order_ids):06d}",
            market_id=quote.market_id,
            token_id=quote.token_id,
            token_side=quote.token_side,
            side=quote.side,
            price=quote.price,
            size=quote.size,
            remaining_size=quote.size,
            status=OrderStatus.OPEN,
            created_at=now,
            updated_at=now,
            fair_value_at_entry=quote.fair_value,
            mid_at_entry=quote.reference_mid,
            reason=quote.reason,
        )
        self._open_orders[order.order_id] = order
        self.order_history.append(order)
        return order

    def _cancel_order(self, order_id: str, now: datetime) -> None:
        order = self._open_orders.pop(order_id, None)
        if order is None:
            return
        order.status = OrderStatus.CANCELLED
        order.updated_at = now

    def process_market_state(self, state: MarketState) -> list[FillEvent]:
        fills: list[FillEvent] = []
        for order in list(self._open_orders.values()):
            if order.market_id != state.market.market_id:
                continue
            if not self._should_fill(order=order, state=state):
                continue
            fill = FillEvent(
                fill_id=f"fill-{next(self._fill_ids):06d}",
                order_id=order.order_id,
                market_id=order.market_id,
                token_id=order.token_id,
                token_side=order.token_side,
                side=order.side,
                price=order.price,
                size=order.remaining_size,
                timestamp=state.observed_at,
                fair_value_at_order=order.fair_value_at_entry,
                mid_at_order=order.mid_at_entry,
            )
            order.status = OrderStatus.FILLED
            order.updated_at = state.observed_at
            order.remaining_size = 0.0
            self._open_orders.pop(order.order_id, None)
            self.inventory.apply_fill(fill)
            self.fill_history.append(fill)
            fills.append(fill)
        return fills

    def _should_fill(self, order: ManagedOrder, state: MarketState) -> bool:
        book = state.yes_book if order.token_side is TokenSide.YES else state.no_book
        if book is None:
            return False
        if order.side is OrderSide.BUY:
            best_ask = book.best_ask.price if book.best_ask else None
            if best_ask is None:
                return False
            return best_ask <= order.price if self.touch_fill_only else best_ask < order.price
        best_bid = book.best_bid.price if book.best_bid else None
        if best_bid is None:
            return False
        return best_bid >= order.price if self.touch_fill_only else best_bid > order.price

    def mark_to_market(self, timestamp: datetime, mark_prices: dict[str, float]) -> PnLSnapshot:
        snapshot = self.inventory.pnl_snapshot(timestamp=timestamp, mark_prices=mark_prices)
        self.pnl_history.append(snapshot)
        return snapshot
