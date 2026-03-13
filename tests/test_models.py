from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.config import ModelConfig
from polymarket_fair_value_engine.models.crypto_updown import CryptoUpDownFairValueModel
from polymarket_fair_value_engine.types import BookLevel, MarketFamily, MarketState, NormalizedMarket, TokenOrderBook


class FailPriceClient:
    def get_spot(self, asset: str) -> float:  # pragma: no cover - defensive in case the test regresses
        raise AssertionError(f"unexpected spot fetch for {asset}")

    def realized_vol_annualized(self, asset: str, lookback_minutes: int, fallback: float) -> tuple[float, list[float]]:  # pragma: no cover
        raise AssertionError("unexpected vol fetch")


def _make_state(mid_yes: float = 0.40) -> MarketState:
    now = datetime.now(timezone.utc)
    market = NormalizedMarket(
        market_id="m1",
        slug="btc-updown-5m-1",
        question="Will Bitcoin be up in 5 minutes?",
        series="btc-updown-5m",
        family=MarketFamily.CRYPTO_UPDOWN,
        asset="BTC",
        end_ts=now + timedelta(minutes=5),
        yes_token_id="yes-1",
        no_token_id="no-1",
        metadata={
            "annualized_vol": 0.50,
            "minute_mu": 0.0004,
            "reference_closes": [100000.0, 100040.0, 100080.0, 100120.0],
        },
    )
    yes_book = TokenOrderBook(
        token_id="yes-1",
        bids=(BookLevel(price=mid_yes - 0.02, size=100.0),),
        asks=(BookLevel(price=mid_yes + 0.02, size=100.0),),
        timestamp=now,
    )
    no_book = TokenOrderBook(
        token_id="no-1",
        bids=(BookLevel(price=0.56, size=100.0),),
        asks=(BookLevel(price=0.60, size=100.0),),
        timestamp=now,
    )
    return MarketState(market=market, yes_book=yes_book, no_book=no_book, observed_at=now, reference_price=100120.0)


def test_crypto_updown_model_uses_replay_metadata_without_external_calls() -> None:
    model = CryptoUpDownFairValueModel(
        config=ModelConfig(
            price_source="coinbase",
            vol_lookback_minutes=60,
            base_annual_vol=0.8,
            vol_floor=0.2,
            uncertainty_multiplier=0.5,
            market_blend_weight=0.0,
        ),
        price_client=FailPriceClient(),
    )

    fair_value = model.estimate(_make_state())

    assert fair_value.reference_price == 100120.0
    assert 0.5 < fair_value.p_yes < 1.0
    assert fair_value.uncertainty >= 0.005
    assert fair_value.diagnostics["close_count"] == 4


def test_crypto_updown_model_blends_with_market_midpoint() -> None:
    state = _make_state(mid_yes=0.20)
    model = CryptoUpDownFairValueModel(
        config=ModelConfig(
            price_source="coinbase",
            vol_lookback_minutes=60,
            base_annual_vol=0.8,
            vol_floor=0.2,
            uncertainty_multiplier=0.5,
            market_blend_weight=0.5,
        ),
        price_client=FailPriceClient(),
    )

    fair_value = model.estimate(state)

    assert fair_value.market_mid == 0.20
    assert 0.20 < fair_value.p_yes < 0.99

