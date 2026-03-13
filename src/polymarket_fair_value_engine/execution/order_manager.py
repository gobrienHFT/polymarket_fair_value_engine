from __future__ import annotations

from datetime import datetime

from polymarket_fair_value_engine.config import StrategyConfig
from polymarket_fair_value_engine.types import ManagedOrder, OrderAction, OrderStatus, QuoteIntent


class OrderManager:
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    def reconcile(
        self,
        desired_quotes: tuple[QuoteIntent, ...],
        open_orders: list[ManagedOrder],
        now: datetime,
    ) -> list[OrderAction]:
        actions: list[OrderAction] = []
        existing_by_reason = {order.reason: order for order in open_orders if order.status is OrderStatus.OPEN}
        desired_by_reason = {quote.reason: quote for quote in desired_quotes}

        for reason, order in existing_by_reason.items():
            if reason not in desired_by_reason:
                actions.append(OrderAction(action="cancel", existing_order_id=order.order_id, reason=f"{reason}:stale"))

        for reason, quote in desired_by_reason.items():
            existing = existing_by_reason.get(reason)
            if existing is None:
                actions.append(OrderAction(action="place", desired=quote, reason=f"{reason}:new"))
                continue
            if self._material_change(existing=existing, desired=quote):
                cooldown = (now - existing.updated_at).total_seconds()
                if cooldown >= self.config.reprice_cooldown_seconds:
                    actions.append(OrderAction(action="cancel", existing_order_id=existing.order_id, reason=f"{reason}:replace"))
                    actions.append(OrderAction(action="place", desired=quote, reason=f"{reason}:replace"))
        return actions

    def _material_change(self, existing: ManagedOrder, desired: QuoteIntent) -> bool:
        if existing.side is not desired.side or existing.token_id != desired.token_id:
            return True
        if abs(existing.price - desired.price) >= self.config.reprice_threshold:
            return True
        return abs(existing.size - desired.size) >= self.config.size_tick

