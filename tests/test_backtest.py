from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.backtest.replay import load_replay_file
from polymarket_fair_value_engine.backtest.simulator import ReplaySimulator
from polymarket_fair_value_engine.config import ModelConfig, RiskConfig, StrategyConfig
from polymarket_fair_value_engine.execution.order_manager import OrderManager
from polymarket_fair_value_engine.execution.paper import PaperExecutionEngine
from polymarket_fair_value_engine.models.crypto_updown import CryptoUpDownFairValueModel
from polymarket_fair_value_engine.risk.limits import RiskManager
from polymarket_fair_value_engine.strategy.passive_mm import PassiveMarketMaker


class FailPriceClient:
    def get_spot(self, asset: str) -> float:  # pragma: no cover
        raise AssertionError("unexpected external price call")

    def realized_vol_annualized(self, asset: str, lookback_minutes: int, fallback: float) -> tuple[float, list[float]]:  # pragma: no cover
        raise AssertionError("unexpected external vol call")


def test_replay_simulator_generates_outputs(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    replay_path = tmp_path / "sample_replay.jsonl"
    market_payload = {
        "market_id": "m1",
        "slug": "btc-updown-5m-1",
        "question": "Will Bitcoin be up in 5 minutes?",
        "series": "btc-updown-5m",
        "family": "crypto_updown",
        "asset": "BTC",
        "end_ts": (now + timedelta(minutes=5)).isoformat(),
        "start_ts": None,
        "yes_token_id": "yes-1",
        "no_token_id": "no-1",
        "last_yes_price": 0.50,
        "last_no_price": 0.50,
        "tick_size": 0.01,
        "size_tick": 0.1,
        "metadata": {
            "annualized_vol": 0.30,
            "minute_mu": 0.001,
            "reference_closes": [100000.0, 100100.0, 100200.0, 100300.0],
        },
    }
    row = {
        "market": market_payload,
        "yes_book": {
            "token_id": "yes-1",
            "bids": [[0.50, 100.0]],
            "asks": [[0.55, 100.0]],
            "timestamp": now.isoformat(),
        },
        "no_book": {
            "token_id": "no-1",
            "bids": [[0.45, 100.0]],
            "asks": [[0.50, 100.0]],
            "timestamp": now.isoformat(),
        },
        "observed_at": now.isoformat(),
        "reference_price": 100300.0,
    }
    replay_path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    simulator = ReplaySimulator(
        model=CryptoUpDownFairValueModel(
            config=ModelConfig(
                price_source="coinbase",
                vol_lookback_minutes=60,
                base_annual_vol=0.8,
                vol_floor=0.2,
                uncertainty_multiplier=0.5,
                market_blend_weight=0.0,
            ),
            price_client=FailPriceClient(),
        ),
        strategy=PassiveMarketMaker(
            StrategyConfig(
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
        ),
        risk_manager=RiskManager(
            RiskConfig(
                max_notional_per_market=100.0,
                max_gross_exposure=500.0,
                max_net_exposure_per_series=500.0,
                max_order_size=100.0,
                max_open_orders=10,
                stale_data_seconds=20,
            )
        ),
        order_manager=OrderManager(
            StrategyConfig(
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
        ),
        execution_engine=PaperExecutionEngine(starting_cash=100.0),
        no_trade_window_seconds=30,
        stale_data_seconds=20,
        output_root=tmp_path / "runs",
    )

    states = load_replay_file(replay_path)
    run_id, output_dir, summary = simulator.run(states)

    assert run_id
    assert summary["orders"] >= 1
    assert summary["fills"] >= 1
    assert (output_dir / "orders.csv").exists()
    assert (output_dir / "fills.csv").exists()
    assert (output_dir / "summary.json").exists()
