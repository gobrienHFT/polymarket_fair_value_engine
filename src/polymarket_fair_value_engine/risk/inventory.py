from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from polymarket_fair_value_engine.types import FillEvent, OrderSide, PnLSnapshot, PositionSnapshot, TokenSide


@dataclass
class InventoryPosition:
    yes_contracts: float = 0.0
    no_contracts: float = 0.0
    yes_cost: float = 0.0
    no_cost: float = 0.0

    @property
    def net_yes_exposure(self) -> float:
        return self.yes_contracts - self.no_contracts


class InventoryLedger:
    def __init__(self, starting_cash: float) -> None:
        self.starting_cash = starting_cash
        self.cash = starting_cash
        self.realized_pnl = 0.0
        self.positions: dict[str, InventoryPosition] = {}

    def position(self, market_id: str) -> InventoryPosition:
        return self.positions.setdefault(market_id, InventoryPosition())

    def apply_fill(self, fill: FillEvent) -> None:
        position = self.position(fill.market_id)
        if fill.token_side is TokenSide.YES:
            self._apply_leg(fill=fill, contracts_attr="yes_contracts", cost_attr="yes_cost", position=position)
        else:
            self._apply_leg(fill=fill, contracts_attr="no_contracts", cost_attr="no_cost", position=position)

    def _apply_leg(self, fill: FillEvent, contracts_attr: str, cost_attr: str, position: InventoryPosition) -> None:
        contracts = getattr(position, contracts_attr)
        cost = getattr(position, cost_attr)
        if fill.side is OrderSide.BUY:
            setattr(position, contracts_attr, contracts + fill.size)
            setattr(position, cost_attr, cost + fill.notional)
            self.cash -= fill.notional
            return

        if fill.size > contracts + 1e-9:
            raise ValueError(f"Cannot sell {fill.size} contracts from {contracts} inventory")
        average_cost = (cost / contracts) if contracts > 0.0 else 0.0
        realized = fill.notional - (average_cost * fill.size)
        setattr(position, contracts_attr, max(0.0, contracts - fill.size))
        setattr(position, cost_attr, max(0.0, cost - (average_cost * fill.size)))
        self.cash += fill.notional
        self.realized_pnl += realized

    def market_notional(self, market_id: str, yes_mark: float) -> float:
        position = self.position(market_id)
        return (position.yes_contracts * yes_mark) + (position.no_contracts * (1.0 - yes_mark))

    def gross_exposure(self, mark_prices: dict[str, float]) -> float:
        total = 0.0
        for market_id, yes_mark in mark_prices.items():
            total += self.market_notional(market_id, yes_mark)
        return total

    def series_net_exposure(self, market_series: dict[str, str]) -> dict[str, float]:
        totals: dict[str, float] = {}
        for market_id, position in self.positions.items():
            series = market_series.get(market_id, market_id)
            totals[series] = totals.get(series, 0.0) + position.net_yes_exposure
        return totals

    def position_snapshots(self, mark_prices: dict[str, float]) -> list[PositionSnapshot]:
        rows: list[PositionSnapshot] = []
        for market_id, position in sorted(self.positions.items()):
            yes_mark = mark_prices.get(market_id)
            if yes_mark is None:
                yes_mark = 0.5
            mark_value = (position.yes_contracts * yes_mark) + (position.no_contracts * (1.0 - yes_mark))
            unrealized = mark_value - (position.yes_cost + position.no_cost)
            rows.append(
                PositionSnapshot(
                    market_id=market_id,
                    yes_contracts=position.yes_contracts,
                    no_contracts=position.no_contracts,
                    net_yes_exposure=position.net_yes_exposure,
                    gross_contracts=position.yes_contracts + position.no_contracts,
                    mark_price_yes=yes_mark,
                    unrealized_pnl=unrealized,
                )
            )
        return rows

    def pnl_snapshot(self, timestamp: datetime, mark_prices: dict[str, float]) -> PnLSnapshot:
        positions = self.position_snapshots(mark_prices)
        unrealized = sum(item.unrealized_pnl for item in positions)
        gross_exposure = self.gross_exposure(mark_prices)
        net_exposure = sum(item.net_yes_exposure for item in positions)
        return PnLSnapshot(
            timestamp=timestamp,
            cash=self.cash,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized,
            total_pnl=self.realized_pnl + unrealized,
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
        )

