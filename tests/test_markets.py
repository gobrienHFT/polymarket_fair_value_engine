from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_fair_value_engine.data.clob_rest import _parse_levels
from polymarket_fair_value_engine.markets.discovery import MarketDiscoveryService
from polymarket_fair_value_engine.markets.filters import has_sane_binary_books
from polymarket_fair_value_engine.markets.normalize import normalize_gamma_market
from polymarket_fair_value_engine.types import BookLevel, MarketFamily, MarketState, NormalizedMarket, TokenOrderBook


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


def test_normalize_gamma_market_skips_malformed_external_fields() -> None:
    raw = _raw_market("btc-updown-5m-bad", datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc))

    raw["outcomePrices"] = ["not-a-number", "0.48"]
    assert normalize_gamma_market(raw) is None

    raw = _raw_market("btc-updown-5m-bad-price", datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc))
    raw["outcomePrices"] = ["nan", "0.48"]
    assert normalize_gamma_market(raw) is None

    raw = _raw_market("btc-updown-5m-out-of-range", datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc))
    raw["outcomePrices"] = [1.2, 0.48]
    assert normalize_gamma_market(raw) is None

    raw = _raw_market("btc-updown-5m-bad-id", datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc))
    raw["clobTokenIds"] = ["same-token", "same-token"]
    assert normalize_gamma_market(raw) is None

    raw = _raw_market("btc-updown-5m-bad-date", datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc))
    raw["endDate"] = "not-a-datetime"
    assert normalize_gamma_market(raw) is None

    raw = _raw_market("btc-updown-5m-naive-date", datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc))
    raw["endDate"] = "2026-01-01T12:05:00"
    assert normalize_gamma_market(raw) is None

    assert normalize_gamma_market([]) is None  # type: ignore[arg-type]


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


def test_clob_level_parser_skips_malformed_or_non_binary_levels() -> None:
    levels = _parse_levels(
        [
            {"price": "not-a-number", "size": 10},
            [0.40, 2.0],
            [1.20, 5.0],
            ["nan", 5.0],
            {"price": 0.55, "quantity": 3.0},
        ]
    )

    assert [(level.price, level.size) for level in levels] == [(0.40, 2.0), (0.55, 3.0)]


def test_crossed_yes_book_is_not_sane() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    market = NormalizedMarket(
        market_id="m1",
        slug="btc-updown-5m-1",
        question="Will Bitcoin be up?",
        series="btc-updown-5m",
        family=MarketFamily.CRYPTO_UPDOWN,
        asset="BTC",
        end_ts=now + timedelta(minutes=5),
        yes_token_id="yes-1",
        no_token_id="no-1",
    )
    state = MarketState(
        market=market,
        yes_book=TokenOrderBook(
            token_id="yes-1",
            bids=(BookLevel(price=0.60, size=1.0),),
            asks=(BookLevel(price=0.50, size=1.0),),
            timestamp=now,
        ),
        no_book=None,
        observed_at=now,
    )

    assert not has_sane_binary_books(state)
