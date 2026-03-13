from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine import cli
from polymarket_fair_value_engine.config import AuthConfig, EndpointConfig, EngineConfig, MarketConfig, ModelConfig, OutputConfig, PaperConfig, RiskConfig, StrategyConfig
from polymarket_fair_value_engine.data.external_prices import CoinbasePriceClient
from polymarket_fair_value_engine.models.base import FairValueModel
from polymarket_fair_value_engine.risk.inventory import InventoryPosition
from polymarket_fair_value_engine.strategy.base import Strategy
from polymarket_fair_value_engine.types import BookLevel, FairValueEstimate, MarketFamily, MarketState, NormalizedMarket, OrderSide, QuoteIntent, StrategyDecision, TokenOrderBook, TokenSide


def _state() -> MarketState:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    market = NormalizedMarket(
        market_id="m1",
        slug="btc-updown-5m-1767268800",
        question="Will Bitcoin be up in 5 minutes?",
        series="btc-updown-5m",
        family=MarketFamily.CRYPTO_UPDOWN,
        asset="BTC",
        end_ts=now + timedelta(minutes=5),
        yes_token_id="yes-1",
        no_token_id="no-1",
    )
    return MarketState(
        market=market,
        yes_book=TokenOrderBook(
            token_id="yes-1",
            bids=(BookLevel(price=0.50, size=100.0),),
            asks=(BookLevel(price=0.54, size=100.0),),
            timestamp=now,
        ),
        no_book=TokenOrderBook(
            token_id="no-1",
            bids=(BookLevel(price=0.46, size=100.0),),
            asks=(BookLevel(price=0.50, size=100.0),),
            timestamp=now,
        ),
        observed_at=now,
        reference_price=100000.0,
    )


def _config(tmp_path) -> EngineConfig:
    return EngineConfig(
        log_level="WARNING",
        endpoints=EndpointConfig(
            gamma_url="https://gamma-api.polymarket.com",
            clob_url="https://clob.polymarket.com",
            polygon_rpc="",
            chain_id=137,
        ),
        auth=AuthConfig(
            private_key="",
            funder="",
            signature_type=0,
            api_key="",
            api_secret="",
            api_passphrase="",
            live_enabled=False,
        ),
        market=MarketConfig(
            default_series="btc-updown-5m",
            target_probe_intervals=0,
            max_minutes_to_expiry=10,
            no_trade_window_seconds=45,
            market_scan_pages=20,
        ),
        model=ModelConfig(
            price_source="coinbase",
            vol_lookback_minutes=90,
            base_annual_vol=0.8,
            vol_floor=0.2,
            uncertainty_multiplier=0.5,
            market_blend_weight=0.2,
        ),
        strategy=StrategyConfig(
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
        ),
        risk=RiskConfig(
            max_notional_per_market=100.0,
            max_gross_exposure=250.0,
            max_net_exposure_per_series=125.0,
            max_order_size=100.0,
            max_open_orders=8,
            stale_data_seconds=20,
        ),
        paper=PaperConfig(starting_cash=100.0, touch_fill_only=True, mark_source="mid"),
        output=OutputConfig(root=tmp_path / "runs"),
    )


class DummyModel(FairValueModel):
    def estimate(self, state: MarketState) -> FairValueEstimate:
        return FairValueEstimate(
            market_id=state.market.market_id,
            p_yes=0.58,
            p_no=0.42,
            model_name="dummy",
            uncertainty=0.01,
            reference_price=state.reference_price,
            market_mid=state.yes_mid,
        )


class DummyStrategy(Strategy):
    def evaluate(self, state: MarketState, fair_value: FairValueEstimate, inventory_position: InventoryPosition) -> StrategyDecision:
        _ = inventory_position
        return StrategyDecision(
            market_id=state.market.market_id,
            fair_value=fair_value,
            quotes=(
                QuoteIntent(
                    market_id=state.market.market_id,
                    token_id=state.market.yes_token_id,
                    token_side=TokenSide.YES,
                    side=OrderSide.BUY,
                    price=0.55,
                    size=10.0,
                    fair_value=fair_value.p_yes,
                    reference_mid=state.yes_mid,
                    created_at=state.observed_at,
                    reason="bid_side_buy_yes",
                ),
            ),
        )


def test_cli_backtest_and_report_smoke(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))

    assert cli.main(["backtest", "--input", "data/sample_replay.jsonl", "--run-id", "cli-smoke"]) == 0
    backtest_output = json.loads(capsys.readouterr().out)
    assert backtest_output["run_id"] == "cli-smoke"

    assert cli.main(["report", "--run-id", "cli-smoke"]) == 0
    report_output = json.loads(capsys.readouterr().out)
    assert report_output["run_id"] == "cli-smoke"
    assert report_output["output_dir"].endswith("cli-smoke")


def test_cli_demo_runs_offline_with_bundled_replay(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))
    monkeypatch.setattr(
        CoinbasePriceClient,
        "get_spot",
        lambda self, asset: (_ for _ in ()).throw(AssertionError(f"unexpected spot fetch for {asset}")),
    )
    monkeypatch.setattr(
        CoinbasePriceClient,
        "realized_vol_annualized",
        lambda self, asset, lookback_minutes, fallback: (_ for _ in ()).throw(AssertionError("unexpected vol fetch")),
    )

    assert cli.main(["demo"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "demo"
    assert payload["run_id"].startswith("demo-")
    assert payload["input"].endswith("data\\sample_replay.jsonl") or payload["input"].endswith("data/sample_replay.jsonl")


def test_cli_scan_smoke(monkeypatch, tmp_path, capsys) -> None:
    config = _config(tmp_path)
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli, "_build_stack", lambda cfg: (object(), object(), DummyModel(), DummyStrategy(), object(), object()))
    monkeypatch.setattr(cli, "_discover_states", lambda cfg, series, discovery, clob_client: [_state()])

    assert cli.main(["scan", "--series", "btc-updown-5m"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["market_id"] == "m1"
