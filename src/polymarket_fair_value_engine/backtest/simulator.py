from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.analytics.pnl import mark_yes_price
from polymarket_fair_value_engine.analytics.reports import create_run_directory, write_run_report
from polymarket_fair_value_engine.execution.order_manager import OrderManager
from polymarket_fair_value_engine.execution.paper import PaperExecutionEngine
from polymarket_fair_value_engine.markets.filters import has_sane_binary_books, in_no_trade_window, is_state_stale
from polymarket_fair_value_engine.models.base import FairValueModel
from polymarket_fair_value_engine.risk.limits import RiskManager
from polymarket_fair_value_engine.strategy.base import Strategy
from polymarket_fair_value_engine.types import MarketState, StrategyDecision


class ReplaySimulator:
    def __init__(
        self,
        model: FairValueModel,
        strategy: Strategy,
        risk_manager: RiskManager,
        order_manager: OrderManager,
        execution_engine: PaperExecutionEngine,
        no_trade_window_seconds: int,
        stale_data_seconds: int,
        output_root: Path,
    ) -> None:
        self.model = model
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.order_manager = order_manager
        self.execution_engine = execution_engine
        self.no_trade_window_seconds = no_trade_window_seconds
        self.stale_data_seconds = stale_data_seconds
        self.output_root = output_root

    def run(self, states: list[MarketState], run_id: str | None = None) -> tuple[str, Path, dict[str, Any]]:
        run_id, output_dir = create_run_directory(self.output_root, run_id=run_id)
        latest_marks: dict[str, float] = {}
        market_series_map = {state.market.market_id: state.market.series for state in states}
        inventory_rows: list[dict[str, Any]] = []

        for state in states:
            stale = is_state_stale(state, stale_data_seconds=self.stale_data_seconds, now=state.observed_at)
            current_state = replace(state, stale=stale)
            current_orders = self.execution_engine.open_orders_for_market(current_state.market.market_id)
            if stale or in_no_trade_window(current_state.market, current_state.observed_at, self.no_trade_window_seconds) or not has_sane_binary_books(current_state):
                self.execution_engine.apply_actions(
                    self.order_manager.reconcile((), current_orders, current_state.observed_at),
                    current_state.observed_at,
                )
                continue

            fair_value = self.model.estimate(current_state)
            decision = self.strategy.evaluate(
                state=current_state,
                fair_value=fair_value,
                inventory_position=self.execution_engine.inventory.position(current_state.market.market_id),
            )
            filtered = self.risk_manager.filter_quotes(
                quotes=decision.quotes,
                inventory=self.execution_engine.inventory,
                market_id=current_state.market.market_id,
                market_series=current_state.market.series,
                mark_yes=mark_yes_price(current_state, fair_value),
                market_series_map=market_series_map,
                open_orders=self.execution_engine.open_orders,
            )
            safe_decision = StrategyDecision(
                market_id=decision.market_id,
                fair_value=decision.fair_value,
                quotes=filtered.approved_quotes,
                diagnostics={**decision.diagnostics, "risk_rejections": list(filtered.rejected_reasons)},
            )
            actions = self.order_manager.reconcile(
                desired_quotes=safe_decision.quotes,
                open_orders=current_orders,
                now=current_state.observed_at,
            )
            self.execution_engine.apply_actions(actions, current_state.observed_at)
            self.execution_engine.process_market_state(current_state)
            latest_marks[current_state.market.market_id] = mark_yes_price(current_state, fair_value)
            self.execution_engine.mark_to_market(current_state.observed_at, latest_marks)
            for position in self.execution_engine.inventory.position_snapshots(latest_marks):
                inventory_rows.append(
                    {
                        "timestamp": current_state.observed_at.isoformat(),
                        "market_id": position.market_id,
                        "yes_contracts": position.yes_contracts,
                        "no_contracts": position.no_contracts,
                        "net_yes_exposure": position.net_yes_exposure,
                        "gross_contracts": position.gross_contracts,
                        "mark_price_yes": position.mark_price_yes,
                        "unrealized_pnl": position.unrealized_pnl,
                    }
                )

        final_pnl = self.execution_engine.pnl_history[-1].total_pnl if self.execution_engine.pnl_history else 0.0
        summary = {
            "run_id": run_id,
            "orders": len(self.execution_engine.order_history),
            "fills": len(self.execution_engine.fill_history),
            "final_total_pnl": final_pnl,
            "final_cash": self.execution_engine.inventory.cash,
            "markets_seen": len({state.market.market_id for state in states}),
        }
        write_run_report(
            output_dir=output_dir,
            orders=self.execution_engine.order_history,
            fills=self.execution_engine.fill_history,
            inventory_rows=inventory_rows,
            pnl_rows=self.execution_engine.pnl_history,
            summary=summary,
        )
        return run_id, output_dir, summary

