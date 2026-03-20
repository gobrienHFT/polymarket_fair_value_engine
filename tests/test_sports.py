from __future__ import annotations

import csv
import json

import pytest

from polymarket_fair_value_engine import cli
from polymarket_fair_value_engine.sports.demo import price_football_markets
from polymarket_fair_value_engine.sports.normalize import load_football_sample
from polymarket_fair_value_engine.sports.odds import FootballBinaryMarketType, OneXTwoProbabilities, binary_yes_probability, decimal_odds_to_implied_probabilities, overround, remove_overround_proportionally


def test_remove_overround_proportionally_normalizes_one_x_two_market() -> None:
    implied = decimal_odds_to_implied_probabilities(2.0, 3.2, 4.0)

    fair = remove_overround_proportionally(implied)

    assert round(overround(implied), 6) == 0.0625
    assert round(fair.total, 6) == 1.0
    assert round(fair.home, 6) == 0.470588
    assert round(fair.draw, 6) == 0.294118
    assert round(fair.away, 6) == 0.235294


def test_binary_yes_probability_maps_one_x_two_probs_to_supported_market_types() -> None:
    fair = OneXTwoProbabilities(home=0.5, draw=0.25, away=0.25)

    assert binary_yes_probability(fair, FootballBinaryMarketType.HOME_WIN) == 0.5
    assert binary_yes_probability(fair, FootballBinaryMarketType.AWAY_WIN) == 0.25
    assert binary_yes_probability(fair, FootballBinaryMarketType.DRAW) == 0.25
    assert binary_yes_probability(fair, FootballBinaryMarketType.HOME_OR_DRAW) == 0.75
    assert binary_yes_probability(fair, FootballBinaryMarketType.AWAY_OR_DRAW) == 0.5
    assert binary_yes_probability(fair, FootballBinaryMarketType.EITHER_TEAM_WINS) == 0.75


def test_load_football_sample_normalizes_fixture_bookmakers_and_markets() -> None:
    events = load_football_sample("data/sample_football_markets.json")

    assert len(events) == 4
    first_event = events[0]
    assert first_event.fixture.home_team == "Arsenal"
    assert first_event.fixture.away_team == "Chelsea"
    assert len(first_event.bookmaker_snapshots) == 2
    assert len(first_event.markets) == 3
    assert round(first_event.markets[0].market_mid_yes or 0.0, 6) == 0.445


def test_price_football_markets_surfaces_honest_no_trade_rows() -> None:
    rows = price_football_markets(load_football_sample("data/sample_football_markets.json"))

    assert any(row.no_trade_reason == "fair_inside_spread" for row in rows)
    assert any(row.no_trade_reason == "wide_yes_spread" for row in rows)


def test_load_football_sample_rejects_invalid_yes_book(tmp_path) -> None:
    invalid_sample = [
        {
            "fixture": {
                "event_id": "bad-event",
                "league": "Test League",
                "kickoff_utc": "2026-03-22T12:00:00Z",
                "home_team": "Home",
                "away_team": "Away",
            },
            "bookmakers": [
                {
                    "source_name": "test-book",
                    "home_decimal": 2.0,
                    "draw_decimal": 3.2,
                    "away_decimal": 4.0,
                }
            ],
            "markets": [
                {
                    "market_id": "bad-market",
                    "market_slug": "bad-market",
                    "market_question": "Bad market",
                    "market_type": "home_win",
                    "best_bid_yes": 0.7,
                    "best_ask_yes": 0.6,
                }
            ],
        }
    ]
    sample_path = tmp_path / "invalid_football.json"
    sample_path.write_text(json.dumps(invalid_sample), encoding="utf-8")

    with pytest.raises(ValueError, match="best_bid_yes cannot exceed best_ask_yes"):
        load_football_sample(sample_path)


def test_cli_football_demo_writes_artifacts_and_report(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))

    assert cli.main(["football-demo", "--run-id", "football-smoke"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "football-demo"
    assert payload["fixtures"] == 4
    assert payload["markets"] == 12
    assert payload["priced_markets"] == 12
    assert payload["artifacts"]["football_fair_values_csv"].endswith("football-smoke/football_fair_values.csv") or payload["artifacts"]["football_fair_values_csv"].endswith("football-smoke\\football_fair_values.csv")

    fair_values_path = tmp_path / "runs" / "football-smoke" / "football_fair_values.csv"
    edges_path = tmp_path / "runs" / "football-smoke" / "football_edges.csv"
    summary_path = tmp_path / "runs" / "football-smoke" / "summary.json"
    assert fair_values_path.exists()
    assert edges_path.exists()
    assert summary_path.exists()

    with fair_values_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert rows[0]["market_type"]
    assert rows[0]["fair_yes"]
    assert "buy_edge_vs_ask" in rows[0]
    assert "sell_edge_vs_bid" in rows[0]
    assert "max_actionable_edge" in rows[0]
    assert rows[0]["no_trade_reason"] in {"", "fair_inside_spread", "wide_yes_spread", "missing_yes_book"}

    assert cli.main(["report", "--run-id", "football-smoke"]) == 0
    report_payload = json.loads(capsys.readouterr().out)
    assert report_payload["artifacts"]["football_edges_csv"].endswith("football-smoke/football_edges.csv") or report_payload["artifacts"]["football_edges_csv"].endswith("football-smoke\\football_edges.csv")
