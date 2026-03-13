from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.markets.discovery import MarketDiscoveryService
from polymarket_fair_value_engine.markets.normalize import normalize_gamma_market


class StubGammaClient:
    def __init__(self, payloads: dict[str, list[dict[str, object]]]) -> None:
        self.payloads = payloads

    def get_market_by_slug(self, slug: str) -> list[dict[str, object]]:
        return self.payloads.get(slug, [])


def _raw_market(slug: str, end_dt: datetime) -> dict[str, object]:
    return {
        "conditionId": f"cond-{slug}",
        "slug": slug,
        "question": "Will Bitcoin be up in 5 minutes?",
        "outcomes": ["Up", "Down"],
        "outcomePrices": [0.52, 0.48],
        "clobTokenIds": ["yes-token", "no-token"],
        "endDate": end_dt.isoformat(),
    }


def test_normalize_gamma_market_parses_btc_updown_contract() -> None:
    end_dt = datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc)
    market = normalize_gamma_market(_raw_market("btc-updown-5m-1767268800", end_dt))

    assert market is not None
    assert market.series == "btc-updown-5m"
    assert market.asset == "BTC"
    assert market.yes_token_id == "yes-token"
    assert market.no_token_id == "no-token"


def test_market_discovery_filters_to_active_expiry_window() -> None:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    target_slug = "btc-updown-5m-1767268800"
    payloads = {
        target_slug: [
            _raw_market(target_slug, now + timedelta(minutes=5)),
            _raw_market(target_slug, now + timedelta(minutes=5)),
            _raw_market("btc-updown-5m-older", now + timedelta(minutes=30)),
        ]
    }
    service = MarketDiscoveryService(StubGammaClient(payloads))

    markets = service.discover_crypto_updown(
        series="btc-updown-5m",
        probe_intervals=0,
        max_minutes_to_expiry=10,
        now=now,
    )

    assert len(markets) == 1
    assert markets[0].slug == target_slug
