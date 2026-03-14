from __future__ import annotations

from dataclasses import dataclass

from polymarket_fair_value_engine.config import RiskConfig
from polymarket_fair_value_engine.risk.inventory import InventoryLedger
from polymarket_fair_value_engine.types import ManagedOrder, OrderSide, QuoteIntent, TokenSide


@dataclass(frozen=True)
class QuoteCheckResult:
    approved_quotes: tuple[QuoteIntent, ...]
    rejected_reasons: tuple[str, ...]


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config

    @staticmethod
    def _is_open(order: ManagedOrder) -> bool:
        return order.status.name == "OPEN"

    @staticmethod
    def _quote_notional_addition(quote: QuoteIntent) -> float:
        return 0.0 if quote.side is OrderSide.SELL else quote.price * quote.size

    @classmethod
    def _order_notional_addition(cls, order: ManagedOrder) -> float:
        if order.side is OrderSide.SELL:
            return 0.0
        return order.price * order.remaining_size

    @staticmethod
    def _signed_contracts(token_side: TokenSide, side: OrderSide, size: float) -> float:
        signed = size if token_side is TokenSide.YES else -size
        if side is OrderSide.SELL:
            signed *= -1.0
        return signed

    def filter_quotes(
        self,
        quotes: tuple[QuoteIntent, ...],
        inventory: InventoryLedger,
        market_id: str,
        market_series: str,
        mark_yes: float,
        market_series_map: dict[str, str],
        open_orders: list[ManagedOrder],
    ) -> QuoteCheckResult:
        approved: list[QuoteIntent] = []
        rejected: list[str] = []
        mark_prices = {key: mark_yes if key == market_id else 0.5 for key in inventory.positions.keys()}
        current_market_notional = inventory.market_notional(market_id, mark_yes)
        current_market_notional += sum(
            self._order_notional_addition(order)
            for order in open_orders
            if self._is_open(order) and order.market_id == market_id
        )
        gross_exposure = inventory.gross_exposure(mark_prices)
        gross_exposure += sum(
            self._order_notional_addition(order)
            for order in open_orders
            if self._is_open(order)
        )
        series_exposure = inventory.series_net_exposure(market_series_map).get(market_series, 0.0)
        series_exposure += sum(
            self._signed_contracts(order.token_side, order.side, order.remaining_size)
            for order in open_orders
            if self._is_open(order) and market_series_map.get(order.market_id) == market_series
        )
        open_order_count = sum(1 for order in open_orders if self._is_open(order))

        for quote in quotes:
            # Batch filtering is sequential: every approved quote changes the projected
            # exposure for the next candidate in the same decision set.
            notional_addition = self._quote_notional_addition(quote)
            signed_contracts = self._signed_contracts(quote.token_side, quote.side, quote.size)
            projected_notional = current_market_notional + notional_addition
            projected_gross = gross_exposure + notional_addition
            projected_series = abs(series_exposure + signed_contracts)
            projected_open_order_count = open_order_count + 1

            if quote.size > self.config.max_order_size:
                rejected.append(f"{quote.reason}:order_size")
                continue
            if projected_notional > self.config.max_notional_per_market:
                rejected.append(f"{quote.reason}:market_notional")
                continue
            if projected_gross > self.config.max_gross_exposure:
                rejected.append(f"{quote.reason}:gross_exposure")
                continue
            if projected_series > self.config.max_net_exposure_per_series:
                rejected.append(f"{quote.reason}:series_net_exposure")
                continue
            if projected_open_order_count > self.config.max_open_orders:
                rejected.append(f"{quote.reason}:max_open_orders")
                continue
            approved.append(quote)
            current_market_notional = projected_notional
            gross_exposure = projected_gross
            series_exposure += signed_contracts
            open_order_count = projected_open_order_count

        return QuoteCheckResult(approved_quotes=tuple(approved), rejected_reasons=tuple(rejected))
