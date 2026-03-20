from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymarket_fair_value_engine import cli
from polymarket_fair_value_engine.sports.normalize import BookmakerOneXTwoOddsSnapshot, PolymarketBinaryMarketDefinition, load_football_replay_frames
from polymarket_fair_value_engine.sports.odds import FootballBinaryMarketType
from polymarket_fair_value_engine.sports.pricing import price_binary_market
from polymarket_fair_value_engine.sports.replay import build_calibration_rows, build_markout_rows, detect_state_changes, price_replay_frames, run_football_replay


def _sample_frames():
    return load_football_replay_frames("data/sample_football_replay.jsonl")


def _sample_quotes_and_markouts():
    frames = _sample_frames()
    changes = detect_state_changes(frames)
    quotes = price_replay_frames(frames, changes)
    markouts = build_markout_rows(frames, quotes)
    return frames, changes, quotes, markouts


def _quote_map():
    _, _, quotes, _ = _sample_quotes_and_markouts()
    return {(row.frame_id, row.market_id): row for row in quotes}


def _markout_map():
    _, _, _, markouts = _sample_quotes_and_markouts()
    return {(row.frame_id, row.market_id): row for row in markouts}


def test_price_binary_market_exposes_directional_edges_and_decision_side() -> None:
    bookmaker_snapshots = (
        BookmakerOneXTwoOddsSnapshot(source_name="sharp_a", home_decimal=1.55, draw_decimal=4.2, away_decimal=6.0),
        BookmakerOneXTwoOddsSnapshot(source_name="sharp_b", home_decimal=1.58, draw_decimal=4.0, away_decimal=5.8),
    )

    buy_market = PolymarketBinaryMarketDefinition(
        event_id="demo-event",
        market_id="buy-home-win",
        market_slug="buy-home-win",
        market_question="Will the home team win?",
        market_type=FootballBinaryMarketType.HOME_WIN,
        raw_market_type="home_win",
        best_bid_yes=0.55,
        best_ask_yes=0.59,
    )
    sell_market = PolymarketBinaryMarketDefinition(
        event_id="demo-event",
        market_id="sell-home-win",
        market_slug="sell-home-win",
        market_question="Will the home team win?",
        market_type=FootballBinaryMarketType.HOME_WIN,
        raw_market_type="home_win",
        best_bid_yes=0.63,
        best_ask_yes=0.67,
    )

    buy_priced = price_binary_market(buy_market, bookmaker_snapshots)
    sell_priced = price_binary_market(sell_market, bookmaker_snapshots)

    assert buy_priced.buy_edge_vs_ask is not None
    assert buy_priced.sell_edge_vs_bid is not None
    assert buy_priced.buy_edge_vs_ask > 0.0
    assert buy_priced.sell_edge_vs_bid < 0.0
    assert buy_priced.max_actionable_edge == buy_priced.buy_edge_vs_ask
    assert buy_priced.decision_side.value == "buy_yes"
    assert buy_priced.edge_vs_best_ask == buy_priced.buy_edge_vs_ask
    assert buy_priced.edge_vs_best_bid == round((buy_priced.fair_yes or 0.0) - buy_market.best_bid_yes, 6)

    assert sell_priced.buy_edge_vs_ask is not None
    assert sell_priced.sell_edge_vs_bid is not None
    assert sell_priced.buy_edge_vs_ask < 0.0
    assert sell_priced.sell_edge_vs_bid > 0.0
    assert sell_priced.max_actionable_edge == sell_priced.sell_edge_vs_bid
    assert sell_priced.decision_side.value == "sell_yes"


def test_load_football_replay_frames_reads_bundled_sample() -> None:
    frames = _sample_frames()

    assert len(frames) == 32
    assert len({frame.fixture.event_id for frame in frames}) == 4
    assert frames[0].fixture.home_team == "Arsenal"
    assert len(frames[0].bookmaker_snapshots) == 2
    assert len(frames[0].markets) == 2


def test_detect_state_changes_finds_expected_transition_types() -> None:
    changes = detect_state_changes(_sample_frames())
    change_types = {change.change_type.value for change in changes}

    assert "kickoff" in change_types
    assert "goal_home" in change_types
    assert "goal_away" in change_types
    assert "equalizer" in change_types
    assert "lead_change" in change_types
    assert "red_card_home" in change_types
    assert "finish" in change_types


def test_price_replay_frames_applies_state_aware_no_trade_rules() -> None:
    quotes = _quote_map()

    assert quotes[("liv-tot-20260412-02", "liv-tot-home-win")].no_trade_reason == "wide_yes_spread"
    assert quotes[("ars-che-20260412-04", "ars-che-draw")].no_trade_reason == "missing_yes_book"
    assert quotes[("ars-che-20260412-05", "ars-che-home-win")].no_trade_reason == "cooldown_after_goal"
    assert quotes[("int-juv-20260413-04", "int-juv-away-win")].no_trade_reason == "cooldown_after_red_card"
    assert quotes[("int-juv-20260413-05", "int-juv-away-win")].no_trade_reason == "insufficient_bookmaker_sources"
    assert quotes[("liv-tot-20260412-07", "liv-tot-home-win")].no_trade_reason == "stale_source_data"
    assert quotes[("rm-bar-20260414-06", "rm-bar-draw")].no_trade_reason == "suspended_match_state"
    assert quotes[("ars-che-20260412-08", "ars-che-home-win")].no_trade_reason == "finished_match_state"
    assert quotes[("ars-che-20260412-07", "ars-che-home-win")].no_trade_reason == "high_uncertainty"


def test_build_markout_rows_computes_markouts_and_settlement() -> None:
    markouts = _markout_map()

    buy_row = markouts[("liv-tot-20260412-01", "liv-tot-home-win")]
    assert buy_row.next_snapshot_mid_yes == 0.56
    assert buy_row.raw_next_mid_change == 0.05
    assert buy_row.directional_next_capture == 0.05
    assert buy_row.next_snapshot_markout == 0.05
    assert buy_row.next_snapshot_edge_capture == 0.05
    assert buy_row.raw_2step_mid_change == 0.06
    assert buy_row.directional_2step_capture == 0.06
    assert buy_row.markout_2_steps == 0.06
    assert buy_row.eventual_settlement_yes == 1.0
    assert buy_row.raw_eventual_resolution_change == 0.49
    assert buy_row.directional_eventual_capture == 0.49
    assert buy_row.eventual_resolution_markout == 0.49

    sell_row = markouts[("int-juv-20260413-07", "int-juv-away-win")]
    assert sell_row.next_snapshot_mid_yes == 0.96
    assert sell_row.raw_next_mid_change == 0.05
    assert sell_row.directional_next_capture == -0.05
    assert sell_row.next_snapshot_markout == 0.05
    assert sell_row.next_snapshot_edge_capture == -0.05
    assert sell_row.max_favorable_move == 0.0
    assert sell_row.max_adverse_move == 0.05


def test_build_calibration_rows_groups_by_edge_bucket_market_type_and_phase() -> None:
    _, _, quotes, markouts = _sample_quotes_and_markouts()

    rows = build_calibration_rows(quotes, markouts)
    row_keys = {(row.bucket_type, row.bucket_value) for row in rows}

    assert ("edge_bucket", "0.01-0.02") in row_keys
    assert ("edge_bucket", "0.02-0.05") in row_keys
    assert ("market_type", "home_win") in row_keys
    assert ("match_phase", "pregame") in row_keys
    assert ("match_phase", "inplay") in row_keys
    assert all(row.sign_hit_rate is None or 0.0 <= row.sign_hit_rate <= 1.0 for row in rows)


def test_run_football_replay_writes_expected_artifacts(tmp_path) -> None:
    run_id, output_dir, summary = run_football_replay(
        input_path="data/sample_football_replay.jsonl",
        output_root=tmp_path / "runs",
        run_id="football-replay-smoke",
        sample_mode=True,
    )

    assert run_id == "football-replay-smoke"
    assert summary["mode"] == "football-replay"
    assert summary["fixtures"] == 4
    assert summary["snapshots"] == 32
    assert summary["priced_snapshots"] == 64
    assert summary["sample_data_is_synthetic"] is True

    expected_artifacts = {
        "summary.json",
        "football_replay_quotes.csv",
        "football_markouts.csv",
        "football_calibration.csv",
        "football_state_changes.csv",
        "football_no_trade_reasons.csv",
        "football_report.md",
    }
    assert expected_artifacts.issubset({path.name for path in output_dir.iterdir()})
    report_text = (output_dir / "football_report.md").read_text(encoding="utf-8")
    assert "## Markout Definitions" in report_text
    assert "## Quote Decision Fields" in report_text
    assert "## Limitations" in report_text


def test_cli_football_replay_sample_flag_writes_artifacts_and_report(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))

    assert cli.main(["football-replay", "--sample", "--run-id", "football-replay-cli"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "football-replay"
    assert payload["snapshots"] == 32
    assert payload["artifacts"]["football_markouts_csv"].endswith("football-replay-cli/football_markouts.csv") or payload["artifacts"]["football_markouts_csv"].endswith("football-replay-cli\\football_markouts.csv")

    assert cli.main(["report", "--run-id", "football-replay-cli"]) == 0
    report_payload = json.loads(capsys.readouterr().out)
    assert report_payload["artifacts"]["football_report_md"].endswith("football-replay-cli/football_report.md") or report_payload["artifacts"]["football_report_md"].endswith("football-replay-cli\\football_report.md")


def test_load_football_replay_frames_rejects_missing_bookmakers(tmp_path: Path) -> None:
    bad_path = tmp_path / "bad_football_replay.jsonl"
    fixture = {
        "event_id": "bad-replay",
        "league": "Test League",
        "kickoff_utc": "2026-04-20T18:00:00Z",
        "home_team": "Home",
        "away_team": "Away",
    }
    frame = {
        "frame_id": "bad-replay-01",
        "timestamp_utc": "2026-04-20T18:00:00Z",
        "fixture": fixture,
        "match_state": {
            "status": "pregame",
            "minute": 0,
            "added_time": 0,
            "home_goals": 0,
            "away_goals": 0,
            "home_red_cards": 0,
            "away_red_cards": 0,
        },
        "bookmakers": [],
        "markets": [
            {
                "market_id": "bad-market",
                "market_slug": "bad-market",
                "market_question": "Bad market",
                "market_type": "home_win",
                "best_bid_yes": 0.45,
                "best_ask_yes": 0.49,
            }
        ],
    }
    bad_path.write_text(json.dumps(frame) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="requires at least one bookmaker snapshot"):
        load_football_replay_frames(bad_path)
