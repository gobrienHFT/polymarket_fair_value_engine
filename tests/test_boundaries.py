from datetime import datetime, timezone
from math import nan

import pytest

from polymarket_fair_value_engine.analytics.reports import RunDecisionStats, create_run_directory, load_summary
from polymarket_fair_value_engine.config import load_config
from polymarket_fair_value_engine.types import BookLevel, FairValueEstimate, MarketFamily, NormalizedMarket, QuoteIntent, TokenOrderBook, TokenSide, OrderSide


def test_token_order_book_normalizes_best_level_order() -> None:
    book = TokenOrderBook(
        token_id="yes-token",
        bids=(BookLevel(price=0.42, size=1.0), BookLevel(price=0.48, size=2.0)),
        asks=(BookLevel(price=0.61, size=1.0), BookLevel(price=0.55, size=2.0)),
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert [level.price for level in book.bids] == [0.48, 0.42]
    assert [level.price for level in book.asks] == [0.55, 0.61]
    assert book.best_bid is not None and book.best_bid.price == 0.48
    assert book.best_ask is not None and book.best_ask.price == 0.55


@pytest.mark.parametrize(
    ("price", "size"),
    [
        (nan, 1.0),
        (1.01, 1.0),
        (0.50, 0.0),
        (0.50, nan),
    ],
)
def test_book_level_rejects_non_tradeable_values(price: float, size: float) -> None:
    with pytest.raises(ValueError):
        BookLevel(price=price, size=size)


def test_token_order_book_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TokenOrderBook(
            token_id="yes-token",
            bids=(BookLevel(price=0.50, size=1.0),),
            timestamp=datetime(2026, 1, 1),
        )


def test_run_directory_rejects_path_traversal_and_reserved_ids(tmp_path) -> None:
    root = tmp_path / "runs"

    for run_id in ("../outside", "nested/run"):
        with pytest.raises(ValueError):
            create_run_directory(root, run_id=run_id)
        with pytest.raises(ValueError):
            load_summary(root, run_id)

    with pytest.raises(ValueError):
        create_run_directory(root, run_id="latest")
    with pytest.raises(FileNotFoundError):
        load_summary(root, "latest")

    assert not (tmp_path / "outside").exists()


def test_run_decision_stats_are_reason_coded() -> None:
    stats = RunDecisionStats()
    stats.observe()
    stats.record_skip("stale_data")
    stats.observe()
    stats.record_priced(generated=2, approved=1, rejected_reasons=("quote_a:market_notional",))

    assert stats.as_dict() == {
        "observations": 2,
        "priced_observations": 1,
        "skipped_observations": 1,
        "quoteable_observations": 1,
        "skip_reasons": {"stale_data": 1},
        "quotes_generated": 2,
        "quotes_approved": 1,
        "quotes_rejected": 1,
        "risk_rejection_reasons": {"market_notional": 1},
    }


def test_config_rejects_invalid_safety_environment_values(tmp_path, monkeypatch) -> None:
    empty_dotenv = tmp_path / "empty.env"
    empty_dotenv.write_text("", encoding="utf-8")

    monkeypatch.setenv("PMFE_LIVE_ENABLED", "maybe")
    with pytest.raises(ValueError, match="PMFE_LIVE_ENABLED must be boolean"):
        load_config(dotenv_path=str(empty_dotenv))

    monkeypatch.setenv("PMFE_LIVE_ENABLED", "0")
    monkeypatch.setenv("PMFE_REPLAY_FILL_SLACK", "nan")
    with pytest.raises(ValueError, match="PMFE_REPLAY_FILL_SLACK must be finite"):
        load_config(dotenv_path=str(empty_dotenv))


def test_domain_objects_reject_malformed_market_and_quote_contracts() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="yes_token_id must be non-empty"):
        NormalizedMarket(
            market_id="m1",
            slug="m1",
            question="Question",
            series="series",
            family=MarketFamily.CRYPTO_UPDOWN,
            asset="BTC",
            end_ts=now,
            yes_token_id="",
            no_token_id="no",
        )

    with pytest.raises(ValueError, match="must sum to 1"):
        FairValueEstimate(
            market_id="m1",
            p_yes=0.6,
            p_no=0.5,
            model_name="test",
            uncertainty=0.01,
            reference_price=100.0,
            market_mid=0.5,
        )

    with pytest.raises(ValueError, match="price must be <= 1.0"):
        QuoteIntent(
            market_id="m1",
            token_id="yes",
            token_side=TokenSide.YES,
            side=OrderSide.BUY,
            price=1.1,
            size=1.0,
            fair_value=0.5,
            reference_mid=0.5,
            created_at=now,
            reason="test",
        )
