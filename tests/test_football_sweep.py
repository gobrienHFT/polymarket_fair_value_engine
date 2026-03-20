from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymarket_fair_value_engine import cli
from polymarket_fair_value_engine.sports.pricing import load_named_football_pricing_config
from polymarket_fair_value_engine.sports.sweep import FootballStrategyResultRow, FootballSweepSelectionConfig, load_football_sweep_config, run_football_sweep, select_best_strategy


def _result_row(
    strategy_name: str,
    *,
    quoteable_snapshots: int,
    average_directional_next_capture: float | None,
    average_directional_2step_capture: float | None,
    positive_capture_rate: float | None,
    average_max_adverse_move: float | None,
) -> FootballStrategyResultRow:
    return FootballStrategyResultRow(
        strategy_name=strategy_name,
        strategy_description=f"{strategy_name} description",
        fixtures=4,
        snapshots=32,
        priced_snapshots=64,
        quoteable_snapshots=quoteable_snapshots,
        buy_decisions=quoteable_snapshots // 2,
        sell_decisions=quoteable_snapshots - (quoteable_snapshots // 2),
        no_trade_snapshots=64 - quoteable_snapshots,
        no_trade_ratio=round((64 - quoteable_snapshots) / 64, 6),
        average_absolute_edge=0.02,
        average_directional_next_capture=average_directional_next_capture,
        average_directional_2step_capture=average_directional_2step_capture,
        average_directional_eventual_capture=0.1,
        positive_capture_rate=positive_capture_rate,
        positive_2step_capture_rate=positive_capture_rate,
        average_max_favorable_move=0.08,
        average_max_adverse_move=average_max_adverse_move,
        average_uncertainty=0.03,
        average_source_overround=0.04,
        average_source_count=2.0,
        dominant_no_trade_reason="fair_inside_spread",
        notes=None,
    )


def test_load_named_football_pricing_config_reads_baseline_file() -> None:
    named_config = load_named_football_pricing_config("configs/football_strategy_baseline.json")

    assert named_config.name == "baseline"
    assert named_config.description == "Current default football replay config"
    assert named_config.pricing_config.high_disagreement_threshold == 0.08


def test_load_named_football_pricing_config_rejects_unknown_field(tmp_path: Path) -> None:
    bad_config = tmp_path / "bad_football_strategy.json"
    bad_config.write_text(
        json.dumps(
            {
                "name": "bad",
                "pricing_config": {
                    "quote_tick": 0.01,
                    "unknown_field": 123,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown football pricing config fields"):
        load_named_football_pricing_config(bad_config)


def test_select_best_strategy_is_deterministic_and_uses_tie_breakers() -> None:
    selection = FootballSweepSelectionConfig(
        min_quoteable_snapshots=8,
        primary_metric="average_directional_next_capture",
        tie_breakers=("average_directional_2step_capture", "positive_capture_rate", "-average_max_adverse_move"),
    )
    rows = (
        _result_row("alpha", quoteable_snapshots=10, average_directional_next_capture=0.02, average_directional_2step_capture=0.03, positive_capture_rate=0.6, average_max_adverse_move=0.03),
        _result_row("beta", quoteable_snapshots=10, average_directional_next_capture=0.02, average_directional_2step_capture=0.04, positive_capture_rate=0.5, average_max_adverse_move=0.02),
        _result_row("gamma", quoteable_snapshots=6, average_directional_next_capture=0.05, average_directional_2step_capture=0.05, positive_capture_rate=0.8, average_max_adverse_move=0.01),
    )

    winner = select_best_strategy(rows, selection)

    assert winner.winner.strategy_name == "beta"
    assert "Required at least 8 quoteable snapshots" in winner.reason
    assert winner.eligible_strategy_names == ("beta", "alpha")
    assert winner.disqualified_strategy_names == ("gamma",)


def test_select_best_strategy_ignores_min_quoteable_when_every_strategy_fails() -> None:
    selection = FootballSweepSelectionConfig(
        min_quoteable_snapshots=20,
        primary_metric="average_directional_next_capture",
        tie_breakers=(),
    )
    rows = (
        _result_row("alpha", quoteable_snapshots=6, average_directional_next_capture=0.01, average_directional_2step_capture=0.01, positive_capture_rate=0.5, average_max_adverse_move=0.05),
        _result_row("beta", quoteable_snapshots=7, average_directional_next_capture=0.02, average_directional_2step_capture=0.01, positive_capture_rate=0.5, average_max_adverse_move=0.05),
    )

    winner = select_best_strategy(rows, selection)

    assert winner.winner.strategy_name == "beta"
    assert winner.disqualified_strategy_names == ()
    assert "filter was ignored" in winner.reason


def test_load_football_sweep_config_rejects_bad_metric(tmp_path: Path) -> None:
    bad_sweep = tmp_path / "bad_football_sweep.json"
    bad_sweep.write_text(
        json.dumps(
            {
                "strategies": [
                    {
                        "name": "baseline",
                        "description": "bad metric",
                        "pricing_config": {
                            "quote_tick": 0.01,
                            "quote_base_half_spread": 0.02,
                            "minimum_bookmaker_sources": 2,
                            "stale_source_data_seconds": 180,
                            "wide_yes_spread_threshold": 0.12,
                            "high_uncertainty_threshold": 0.08,
                            "high_disagreement_threshold": 0.08,
                            "goal_cooldown_minutes": 3,
                            "red_card_cooldown_minutes": 5,
                            "goal_uncertainty_boost": 0.04,
                            "red_card_uncertainty_boost": 0.05,
                            "suspended_uncertainty_boost": 0.1,
                        },
                    }
                ],
                "selection": {
                    "min_quoteable_snapshots": 8,
                    "primary_metric": "not_a_metric",
                    "tie_breakers": [],
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unsupported selection metric"):
        load_football_sweep_config(bad_sweep)


def test_run_football_sweep_writes_expected_artifacts(tmp_path: Path) -> None:
    sweep_config = load_football_sweep_config("configs/football_sweep.json")

    run_id, output_dir, summary = run_football_sweep(
        input_path="data/sample_football_replay.jsonl",
        output_root=tmp_path / "runs",
        sweep_config=sweep_config,
        run_id="football-sweep-smoke",
        sample_mode=True,
        config_path="configs/football_sweep.json",
    )

    assert run_id == "football-sweep-smoke"
    assert summary["mode"] == "football-sweep"
    assert summary["strategies_compared"] == 4
    assert summary["winning_strategy"] == "more_aggressive"
    assert (output_dir / "football_strategy_results.csv").exists()
    assert (output_dir / "football_strategy_slices.csv").exists()
    assert (output_dir / "football_strategy_report.md").exists()
    assert (output_dir / "football_strategy_best.json").exists()
    assert (output_dir / "best_strategy" / "summary.json").exists()

    report_text = (output_dir / "football_strategy_report.md").read_text(encoding="utf-8")
    assert "directional capture metrics" in report_text
    assert "synthetic" in report_text


def test_cli_football_replay_with_config_override(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))

    assert cli.main(
        [
            "football-replay",
            "--sample",
            "--config",
            "configs/football_strategy_baseline.json",
            "--run-id",
            "football-replay-config",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["pricing_config_name"] == "baseline"
    assert payload["pricing_config"]["goal_cooldown_minutes"] == 3
    assert payload["artifacts"]["football_report_md"].endswith("football-replay-config/football_report.md") or payload["artifacts"]["football_report_md"].endswith("football-replay-config\\football_report.md")


def test_cli_football_sweep_happy_path_and_report(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))

    assert cli.main(
        [
            "football-sweep",
            "--sample",
            "--config",
            "configs/football_sweep.json",
            "--run-id",
            "football-sweep-cli",
        ]
    ) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "football-sweep"
    assert payload["winning_strategy"] == "more_aggressive"
    assert payload["artifacts"]["football_strategy_results_csv"].endswith("football-sweep-cli/football_strategy_results.csv") or payload["artifacts"]["football_strategy_results_csv"].endswith("football-sweep-cli\\football_strategy_results.csv")
    assert payload["artifacts"]["best_strategy_summary_json"].endswith("football-sweep-cli/best_strategy/summary.json") or payload["artifacts"]["best_strategy_summary_json"].endswith("football-sweep-cli\\best_strategy\\summary.json")

    assert cli.main(["report", "--run-id", "football-sweep-cli"]) == 0
    report_payload = json.loads(capsys.readouterr().out)
    assert report_payload["artifacts"]["football_strategy_report_md"].endswith("football-sweep-cli/football_strategy_report.md") or report_payload["artifacts"]["football_strategy_report_md"].endswith("football-sweep-cli\\football_strategy_report.md")
