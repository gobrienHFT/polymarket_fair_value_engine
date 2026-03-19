from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.analytics.pnl import mark_yes_price
from polymarket_fair_value_engine.analytics.reports import create_run_directory, load_summary, run_artifacts, write_run_report
from polymarket_fair_value_engine.backtest.replay import load_replay_file
from polymarket_fair_value_engine.backtest.simulator import ReplaySimulator
from polymarket_fair_value_engine.config import EngineConfig, load_config
from polymarket_fair_value_engine.data.clob_rest import ClobRestClient
from polymarket_fair_value_engine.data.external_prices import CoinbasePriceClient
from polymarket_fair_value_engine.data.gamma import GammaClient
from polymarket_fair_value_engine.execution.live import PolymarketLiveExecutor
from polymarket_fair_value_engine.execution.order_manager import OrderManager
from polymarket_fair_value_engine.execution.paper import PaperExecutionEngine
from polymarket_fair_value_engine.logging_utils import configure_logging
from polymarket_fair_value_engine.markets.discovery import MarketDiscoveryService
from polymarket_fair_value_engine.markets.filters import has_sane_binary_books, in_no_trade_window, is_state_stale
from polymarket_fair_value_engine.models.crypto_updown import CryptoUpDownFairValueModel
from polymarket_fair_value_engine.risk.checks import guard_live_mode, kill_switch_engaged
from polymarket_fair_value_engine.risk.inventory import InventoryLedger, InventoryPosition
from polymarket_fair_value_engine.risk.limits import RiskManager
from polymarket_fair_value_engine.sports.demo import run_football_demo
from polymarket_fair_value_engine.strategy.passive_mm import PassiveMarketMaker
from polymarket_fair_value_engine.types import ManagedOrder, MarketState, OrderStatus, StrategyDecision


LOGGER = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _bundled_sample_replay_path() -> Path:
    return _repo_root() / "data" / "sample_replay.jsonl"


def _bundled_sample_football_path() -> Path:
    return _repo_root() / "data" / "sample_football_markets.json"


def _build_stack(
    config: EngineConfig,
) -> tuple[MarketDiscoveryService, ClobRestClient, CryptoUpDownFairValueModel, PassiveMarketMaker, RiskManager, OrderManager]:
    discovery = MarketDiscoveryService(GammaClient(config.endpoints.gamma_url))
    clob_client = ClobRestClient(config.endpoints.clob_url)
    model = CryptoUpDownFairValueModel(config.model, CoinbasePriceClient())
    strategy = PassiveMarketMaker(config.strategy)
    risk_manager = RiskManager(config.risk)
    order_manager = OrderManager(config.strategy)
    return discovery, clob_client, model, strategy, risk_manager, order_manager


def _build_replay_simulator(config: EngineConfig) -> ReplaySimulator:
    _, _, model, strategy, risk_manager, order_manager = _build_stack(config)
    return ReplaySimulator(
        model=model,
        strategy=strategy,
        risk_manager=risk_manager,
        order_manager=order_manager,
        execution_engine=PaperExecutionEngine(
            starting_cash=config.paper.starting_cash,
            touch_fill_only=config.paper.touch_fill_only,
            replay_fill_slack=config.paper.replay_fill_slack,
        ),
        no_trade_window_seconds=config.market.no_trade_window_seconds,
        stale_data_seconds=config.risk.stale_data_seconds,
        output_root=config.output.root,
    )


def _discover_states(
    config: EngineConfig,
    series: str,
    discovery: MarketDiscoveryService,
    clob_client: ClobRestClient,
) -> list[MarketState]:
    markets = discovery.discover_crypto_updown(
        series=series,
        probe_intervals=config.market.target_probe_intervals,
        max_minutes_to_expiry=config.market.max_minutes_to_expiry,
    )
    now = datetime.now(timezone.utc)
    states: list[MarketState] = []
    for market in markets:
        try:
            states.append(
                MarketState(
                    market=market,
                    yes_book=clob_client.get_order_book(market.yes_token_id),
                    no_book=clob_client.get_order_book(market.no_token_id),
                    observed_at=now,
                )
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to fetch order book",
                extra={"context": {"market_id": market.market_id, "error": str(exc)}},
            )
    return states


def _scan_command(config: EngineConfig, series: str) -> int:
    discovery, clob_client, model, strategy, _, _ = _build_stack(config)
    rows: list[dict[str, Any]] = []
    for state in _discover_states(config, series, discovery, clob_client):
        try:
            fair_value = model.estimate(state)
            decision = strategy.evaluate(state, fair_value, InventoryPosition())
        except Exception as exc:
            rows.append({"market_id": state.market.market_id, "error": str(exc)})
            continue
        rows.append(
            {
                "market_id": state.market.market_id,
                "slug": state.market.slug,
                "question": state.market.question,
                "fair_value_yes": round(fair_value.p_yes, 4),
                "mid_yes": round(state.yes_mid, 4) if state.yes_mid is not None else None,
                "spread": round(state.spread, 4) if state.spread is not None else None,
                "uncertainty": round(fair_value.uncertainty, 4),
                "quote_targets": [
                    {
                        "reason": quote.reason,
                        "side": quote.side.value,
                        "token_side": quote.token_side.value,
                        "price": quote.price,
                        "size": quote.size,
                    }
                    for quote in decision.quotes
                ],
                "diagnostics": fair_value.diagnostics,
            }
        )
    print(json.dumps(rows, indent=2))
    return 0


def _paper_quote_command(config: EngineConfig, series: str, iterations: int, run_id: str | None = None) -> int:
    discovery, clob_client, model, strategy, risk_manager, order_manager = _build_stack(config)
    execution_engine = PaperExecutionEngine(
        starting_cash=config.paper.starting_cash,
        touch_fill_only=config.paper.touch_fill_only,
        replay_fill_slack=config.paper.replay_fill_slack,
    )
    run_id, output_dir = create_run_directory(config.output.root, run_id=run_id)
    latest_marks: dict[str, float] = {}
    market_series_map: dict[str, str] = {}
    inventory_rows: list[dict[str, Any]] = []

    for iteration in range(iterations):
        if kill_switch_engaged():
            LOGGER.warning("Kill switch engaged; stopping paper quote loop")
            break

        for state in _discover_states(config, series, discovery, clob_client):
            market_series_map[state.market.market_id] = state.market.series
            stale = is_state_stale(state, stale_data_seconds=config.risk.stale_data_seconds, now=state.observed_at)
            current_state = replace(state, stale=stale)
            current_orders = execution_engine.open_orders_for_market(current_state.market.market_id)

            if stale or in_no_trade_window(current_state.market, current_state.observed_at, config.market.no_trade_window_seconds) or not has_sane_binary_books(current_state):
                execution_engine.apply_actions(
                    order_manager.reconcile((), current_orders, current_state.observed_at),
                    current_state.observed_at,
                )
                continue

            fair_value = model.estimate(current_state)
            decision = strategy.evaluate(
                current_state,
                fair_value,
                execution_engine.inventory.position(current_state.market.market_id),
            )
            filtered = risk_manager.filter_quotes(
                quotes=decision.quotes,
                inventory=execution_engine.inventory,
                market_id=current_state.market.market_id,
                market_series=current_state.market.series,
                mark_yes=mark_yes_price(current_state, fair_value),
                market_series_map=market_series_map,
                open_orders=execution_engine.open_orders,
            )
            safe_decision = StrategyDecision(
                market_id=decision.market_id,
                fair_value=decision.fair_value,
                quotes=filtered.approved_quotes,
                diagnostics={**decision.diagnostics, "risk_rejections": list(filtered.rejected_reasons)},
            )
            actions = order_manager.reconcile(
                desired_quotes=safe_decision.quotes,
                open_orders=current_orders,
                now=current_state.observed_at,
            )
            execution_engine.apply_actions(actions, current_state.observed_at)
            fills = execution_engine.process_market_state(current_state)
            latest_marks[current_state.market.market_id] = mark_yes_price(current_state, fair_value)
            pnl = execution_engine.mark_to_market(current_state.observed_at, latest_marks)
            for position in execution_engine.inventory.position_snapshots(latest_marks):
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
            LOGGER.info(
                "Paper quote cycle",
                extra={
                    "context": {
                        "market_id": current_state.market.market_id,
                        "fills": len(fills),
                        "open_orders": len(execution_engine.open_orders),
                        "total_pnl": pnl.total_pnl,
                    }
                },
            )
        if iteration < iterations - 1:
            time.sleep(config.strategy.poll_seconds)

    summary = {
        "run_id": run_id,
        "mode": "paper",
        "series": series,
        "orders": len(execution_engine.order_history),
        "fills": len(execution_engine.fill_history),
        "final_total_pnl": execution_engine.pnl_history[-1].total_pnl if execution_engine.pnl_history else 0.0,
        "final_cash": execution_engine.inventory.cash,
    }
    write_run_report(
        output_dir=output_dir,
        orders=execution_engine.order_history,
        fills=execution_engine.fill_history,
        inventory_rows=inventory_rows,
        pnl_rows=execution_engine.pnl_history,
        summary=summary,
    )
    print(json.dumps(_run_payload(output_dir, summary, mode="paper", series=series), indent=2))
    return 0


def _live_quote_command(config: EngineConfig, series: str, iterations: int) -> int:
    discovery, clob_client, model, strategy, risk_manager, order_manager = _build_stack(config)
    executor = PolymarketLiveExecutor(config.endpoints, config.auth)
    session_orders: list[ManagedOrder] = []
    inventory = InventoryLedger(starting_cash=0.0)
    market_series_map: dict[str, str] = {}

    for iteration in range(iterations):
        if kill_switch_engaged():
            LOGGER.warning("Kill switch engaged; cancelling all live orders")
            executor.cancel_all()
            return 1

        for state in _discover_states(config, series, discovery, clob_client):
            market_series_map[state.market.market_id] = state.market.series
            if is_state_stale(state, config.risk.stale_data_seconds, state.observed_at):
                continue
            if in_no_trade_window(state.market, state.observed_at, config.market.no_trade_window_seconds):
                continue

            fair_value = model.estimate(state)
            decision = strategy.evaluate(state, fair_value, InventoryPosition())
            filtered = risk_manager.filter_quotes(
                quotes=decision.quotes,
                inventory=inventory,
                market_id=state.market.market_id,
                market_series=state.market.series,
                mark_yes=mark_yes_price(state, fair_value),
                market_series_map=market_series_map,
                open_orders=session_orders,
            )
            current_orders = [order for order in session_orders if order.market_id == state.market.market_id]
            actions = order_manager.reconcile(filtered.approved_quotes, current_orders, state.observed_at)
            cancel_ids = [action.existing_order_id for action in actions if action.action == "cancel" and action.existing_order_id]
            if cancel_ids:
                executor.cancel_orders(cancel_ids)
                cancelled = set(cancel_ids)
                session_orders = [order for order in session_orders if order.order_id not in cancelled]
            for action in actions:
                if action.action != "place" or action.desired is None:
                    continue
                response = executor.place_order(action.desired)
                session_orders.append(
                    ManagedOrder(
                        order_id=str(response.get("orderID", response.get("id", action.desired.reason))),
                        market_id=action.desired.market_id,
                        token_id=action.desired.token_id,
                        token_side=action.desired.token_side,
                        side=action.desired.side,
                        price=action.desired.price,
                        size=action.desired.size,
                        remaining_size=action.desired.size,
                        status=OrderStatus.OPEN,
                        created_at=state.observed_at,
                        updated_at=state.observed_at,
                        fair_value_at_entry=action.desired.fair_value,
                        mid_at_entry=action.desired.reference_mid,
                        reason=action.desired.reason,
                    )
                )
                LOGGER.info(
                    "Posted live order",
                    extra={"context": {"market_id": state.market.market_id, "response": response}},
                )
        if iteration < iterations - 1:
            time.sleep(config.strategy.poll_seconds)
    return 0


def _run_payload(output_dir: Path, summary: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        **extra,
        "output_dir": str(output_dir),
        "artifacts": run_artifacts(output_dir),
        **summary,
    }


def _run_replay(config: EngineConfig, input_path: Path, run_id: str | None = None, mode: str = "backtest") -> dict[str, Any]:
    simulator = _build_replay_simulator(config)
    actual_run_id, output_dir, summary = simulator.run(load_replay_file(input_path), run_id=run_id)
    return _run_payload(output_dir, summary, mode=mode, input=str(input_path), run_id=actual_run_id)


def _resolve_backtest_input(input_path: str | None, sample: bool) -> Path:
    if sample:
        return _bundled_sample_replay_path()
    if input_path is None:
        raise RuntimeError("backtest requires either --input or --sample.")
    return Path(input_path)


def _backtest_command(config: EngineConfig, input_path: str | None = None, sample: bool = False, run_id: str | None = None) -> int:
    payload = _run_replay(config, input_path=_resolve_backtest_input(input_path, sample=sample), run_id=run_id, mode="backtest")
    print(json.dumps(payload, indent=2))
    return 0


def _demo_command(config: EngineConfig, run_id: str | None = None) -> int:
    run_id = run_id or datetime.now(timezone.utc).strftime("demo-%Y%m%dT%H%M%SZ")
    payload = _run_replay(config, input_path=_bundled_sample_replay_path(), run_id=run_id, mode="demo")
    print(json.dumps(payload, indent=2))
    return 0


def _report_command(config: EngineConfig, run_id: str) -> int:
    output_dir, summary = load_summary(config.output.root, run_id)
    print(json.dumps(_run_payload(output_dir, summary), indent=2))
    return 0


def _football_demo_command(config: EngineConfig, input_path: str | None = None, run_id: str | None = None) -> int:
    _, _, summary = run_football_demo(
        input_path=input_path or _bundled_sample_football_path(),
        output_root=config.output.root,
        run_id=run_id,
    )
    print(json.dumps(summary, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pmfe")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan")
    scan.add_argument("--series", default=None)

    quote = subparsers.add_parser("quote")
    quote.add_argument("--series", default=None)
    quote.add_argument("--paper", action="store_true", default=False)
    quote.add_argument("--live", action="store_true", default=False)
    quote.add_argument("--ack-live-risk", action="store_true", default=False)
    quote.add_argument("--iterations", type=int, default=10)
    quote.add_argument("--run-id", default=None)

    backtest = subparsers.add_parser("backtest")
    backtest_input = backtest.add_mutually_exclusive_group(required=True)
    backtest_input.add_argument("--input", default=None)
    backtest_input.add_argument("--sample", action="store_true", default=False)
    backtest.add_argument("--run-id", default=None)

    demo = subparsers.add_parser("demo")
    demo.add_argument("--run-id", default=None)

    football_demo = subparsers.add_parser("football-demo")
    football_demo.add_argument("--input", default=None)
    football_demo.add_argument("--run-id", default=None)

    cancel_all = subparsers.add_parser("cancel-all")
    cancel_all.add_argument("--live", action="store_true", default=False)
    cancel_all.add_argument("--ack-live-risk", action="store_true", default=False)

    report = subparsers.add_parser("report")
    report.add_argument("--run-id", default="latest")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    configure_logging(config.log_level)
    series = getattr(args, "series", None) or config.market.default_series

    if args.command == "scan":
        return _scan_command(config, series)
    if args.command == "quote":
        if args.live and args.paper:
            raise RuntimeError("Choose either paper mode or live mode, not both.")
        live = bool(args.live)
        paper = bool(args.paper) or not live
        guard_live_mode(live=live, ack_live_risk=bool(args.ack_live_risk), live_enabled=config.auth.live_enabled)
        if live:
            return _live_quote_command(config, series=series, iterations=args.iterations)
        if not paper:
            raise RuntimeError("Paper mode is the default. Use --live to opt in to live execution.")
        return _paper_quote_command(config, series=series, iterations=args.iterations, run_id=args.run_id)
    if args.command == "backtest":
        return _backtest_command(config, input_path=args.input, sample=bool(args.sample), run_id=args.run_id)
    if args.command == "demo":
        return _demo_command(config, run_id=args.run_id)
    if args.command == "football-demo":
        return _football_demo_command(config, input_path=args.input, run_id=args.run_id)
    if args.command == "cancel-all":
        guard_live_mode(live=bool(args.live), ack_live_risk=bool(args.ack_live_risk), live_enabled=config.auth.live_enabled)
        if not args.live:
            raise RuntimeError("cancel-all requires --live.")
        executor = PolymarketLiveExecutor(config.endpoints, config.auth)
        print(json.dumps({"response": executor.cancel_all()}, indent=2, default=str))
        return 0
    if args.command == "report":
        return _report_command(config, args.run_id)
    parser.error(f"Unknown command: {args.command}")
    return 2
