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
        current_market_notional = inventory.market_notional(market_id, mark_yes)
        pending_notional = sum(order.notional for order in open_orders if order.market_id == market_id and order.status.name == "OPEN")
        gross_exposure = inventory.gross_exposure({key: mark_yes if key == market_id else 0.5 for key in inventory.positions.keys()})
        series_exposure = inventory.series_net_exposure(market_series_map).get(market_series, 0.0)
        open_order_count = sum(1 for order in open_orders if order.status.name == "OPEN")

        for quote in quotes:
            reducing_inventory = quote.side is OrderSide.SELL
            projected_notional = current_market_notional + pending_notional + (0.0 if reducing_inventory else quote.price * quote.size)
            projected_gross = gross_exposure + (0.0 if reducing_inventory else quote.price * quote.size)
            signed_contracts = quote.size if quote.token_side is TokenSide.YES else -quote.size
            if reducing_inventory:
                signed_contracts *= -1.0
            projected_series = abs(series_exposure + signed_contracts)

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
            if open_order_count + len(approved) + 1 > self.config.max_open_orders:
                rejected.append(f"{quote.reason}:max_open_orders")
                continue
            approved.append(quote)

        return QuoteCheckResult(approved_quotes=tuple(approved), rejected_reasons=tuple(rejected))

