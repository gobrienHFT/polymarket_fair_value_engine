from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _pick(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


def _as_int(*names: str, default: int) -> int:
    return int(_pick(*names, default=str(default)))


def _as_float(*names: str, default: float) -> float:
    return float(_pick(*names, default=str(default)))


def _as_bool(*names: str, default: bool) -> bool:
    raw = _pick(*names, default="1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EndpointConfig:
    gamma_url: str
    clob_url: str
    polygon_rpc: str
    chain_id: int


@dataclass(frozen=True)
class AuthConfig:
    private_key: str
    funder: str
    signature_type: int
    api_key: str
    api_secret: str
    api_passphrase: str
    live_enabled: bool


@dataclass(frozen=True)
class MarketConfig:
    default_series: str
    target_probe_intervals: int
    max_minutes_to_expiry: int
    no_trade_window_seconds: int
    market_scan_pages: int


@dataclass(frozen=True)
class ModelConfig:
    price_source: str
    vol_lookback_minutes: int
    base_annual_vol: float
    vol_floor: float
    uncertainty_multiplier: float
    market_blend_weight: float


@dataclass(frozen=True)
class StrategyConfig:
    poll_seconds: int
    quote_half_spread: float
    min_edge: float
    inventory_skew_per_contract: float
    quote_notional: float
    min_order_usdc: float
    price_tick: float
    size_tick: float
    reprice_threshold: float
    reprice_cooldown_seconds: int


@dataclass(frozen=True)
class RiskConfig:
    max_notional_per_market: float
    max_gross_exposure: float
    max_net_exposure_per_series: float
    max_order_size: float
    max_open_orders: int
    stale_data_seconds: int


@dataclass(frozen=True)
class PaperConfig:
    starting_cash: float
    touch_fill_only: bool
    mark_source: str


@dataclass(frozen=True)
class OutputConfig:
    root: Path


@dataclass(frozen=True)
class EngineConfig:
    log_level: str
    endpoints: EndpointConfig
    auth: AuthConfig
    market: MarketConfig
    model: ModelConfig
    strategy: StrategyConfig
    risk: RiskConfig
    paper: PaperConfig
    output: OutputConfig

    def output_dir(self, run_id: str) -> Path:
        return self.output.root / run_id


def load_config(dotenv_path: str | None = None) -> EngineConfig:
    load_dotenv(dotenv_path=dotenv_path)

    bankroll = _as_float("BOT_BANKROLL_USDC", default=1000.0)
    legacy_fraction = _as_float("BOT_MAX_FRACTION_PER_TRADE", default=0.05)
    default_quote_notional = round(bankroll * legacy_fraction, 4)

    return EngineConfig(
        log_level=_pick("LOG_LEVEL", default="INFO"),
        endpoints=EndpointConfig(
            gamma_url=_pick("POLYMARKET_GAMMA_URL", default="https://gamma-api.polymarket.com"),
            clob_url=_pick("POLYMARKET_CLOB_URL", default="https://clob.polymarket.com"),
            polygon_rpc=_pick("POLYGON_RPC", default=""),
            chain_id=_as_int("POLYMARKET_CHAIN_ID", default=137),
        ),
        auth=AuthConfig(
            private_key=_pick("POLY_PRIVATE_KEY", "POLYMARKET_PRIVATE_KEY", default=""),
            funder=_pick("POLY_FUNDER", "POLYMARKET_FUNDER", default=""),
            signature_type=_as_int("POLY_SIGNATURE_TYPE", "POLYMARKET_SIGNATURE_TYPE", default=0),
            api_key=_pick("CLOB_API_KEY", default=""),
            api_secret=_pick("CLOB_SECRET", default=""),
            api_passphrase=_pick("CLOB_PASSPHRASE", default=""),
            live_enabled=_as_bool("PMFE_LIVE_ENABLED", default=False),
        ),
        market=MarketConfig(
            default_series=_pick("PMFE_DEFAULT_SERIES", "BOT_TARGET_SERIES_PREFIX", default="btc-updown-5m"),
            target_probe_intervals=_as_int("BOT_TARGET_PROBE_INTERVALS", default=6),
            max_minutes_to_expiry=_as_int("PMFE_MAX_MINUTES_TO_EXPIRY", "BOT_MAX_MIN_TO_EXPIRY", default=10),
            no_trade_window_seconds=_as_int("PMFE_NO_TRADE_WINDOW_SECONDS", default=45),
            market_scan_pages=_as_int("BOT_MARKET_SCAN_PAGES", default=20),
        ),
        model=ModelConfig(
            price_source=_pick("PMFE_PRICE_SOURCE", default="coinbase"),
            vol_lookback_minutes=_as_int("PMFE_VOL_LOOKBACK_MINUTES", "BOT_VOL_LOOKBACK", default=90),
            base_annual_vol=_as_float("BOT_BASE_ANNUAL_VOL", default=0.80),
            vol_floor=_as_float("PMFE_VOL_FLOOR", default=0.20),
            uncertainty_multiplier=_as_float("PMFE_UNCERTAINTY_MULTIPLIER", default=0.50),
            market_blend_weight=_as_float("PMFE_MARKET_BLEND_WEIGHT", default=0.20),
        ),
        strategy=StrategyConfig(
            poll_seconds=_as_int("BOT_POLL_SECONDS", default=15),
            quote_half_spread=_as_float("PMFE_QUOTE_HALF_SPREAD", default=0.02),
            min_edge=_as_float("PMFE_MIN_EDGE", default=0.015),
            inventory_skew_per_contract=_as_float("PMFE_INVENTORY_SKEW_PER_CONTRACT", default=0.003),
            quote_notional=_as_float("PMFE_QUOTE_NOTIONAL", default=default_quote_notional),
            min_order_usdc=_as_float("BOT_MIN_ORDER_USDC", default=5.0),
            price_tick=_as_float("BOT_PRICE_TICK", default=0.01),
            size_tick=_as_float("BOT_SIZE_TICK", default=0.1),
            reprice_threshold=_as_float("PMFE_REPRICE_THRESHOLD", default=0.01),
            reprice_cooldown_seconds=_as_int("PMFE_REPRICE_COOLDOWN_SECONDS", default=5),
        ),
        risk=RiskConfig(
            max_notional_per_market=_as_float("PMFE_MAX_NOTIONAL_PER_MARKET", default=75.0),
            max_gross_exposure=_as_float("PMFE_MAX_GROSS_EXPOSURE", default=250.0),
            max_net_exposure_per_series=_as_float("PMFE_MAX_NET_EXPOSURE_PER_SERIES", default=125.0),
            max_order_size=_as_float("PMFE_MAX_ORDER_SIZE", default=100.0),
            max_open_orders=_as_int("PMFE_MAX_OPEN_ORDERS", default=8),
            stale_data_seconds=_as_int("PMFE_STALE_DATA_SECONDS", default=20),
        ),
        paper=PaperConfig(
            starting_cash=bankroll,
            touch_fill_only=_as_bool("PMFE_TOUCH_FILL_ONLY", default=True),
            mark_source=_pick("PMFE_MARK_SOURCE", default="mid"),
        ),
        output=OutputConfig(
            root=Path(_pick("PMFE_OUTPUT_ROOT", default="runs")),
        ),
    )

