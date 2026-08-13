from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from polymarket_fair_value_engine import cli
from polymarket_fair_value_engine.execution_research.config import load_execution_research_config
from polymarket_fair_value_engine.execution_research.engine import run_execution_research
from polymarket_fair_value_engine.execution_research.replay import load_clob_replay
from polymarket_fair_value_engine.execution_research.types import LifecycleEventType, MarketValidity


REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_INPUT = REPO_ROOT / "data" / "sample_execution_replay.jsonl"
SAMPLE_CONFIG = REPO_ROOT / "configs" / "execution_research.json"


def _load_config():
    return load_execution_research_config(SAMPLE_CONFIG)


def test_execution_replay_classifies_fail_closed_states() -> None:
    config, _, _ = _load_config()
    frames = load_clob_replay(SAMPLE_INPUT, config)

    assert len(frames) == 19
    assert sum(frame.snapshot.validity is MarketValidity.VALID for frame in frames) == 15
    assert {frame.snapshot.validity for frame in frames} == {
        MarketValidity.VALID,
        MarketValidity.CROSSED,
        MarketValidity.STALE,
        MarketValidity.DISCONTINUOUS,
        MarketValidity.MALFORMED,
    }
    assert all(frame.snapshot.validity is not MarketValidity.VALID or frame.snapshot.mid is not None for frame in frames)


def test_execution_replay_fails_closed_on_source_identity_changes(tmp_path) -> None:
    rows = [
        {
            "timestamp_utc": "2026-01-01T12:00:00Z",
            "book_timestamp_utc": "2026-01-01T12:00:00Z",
            "sequence": 1,
            "market_id": "identity-market",
            "yes_token_id": "yes-a",
            "fair_yes": 0.60,
            "yes_bids": [[0.50, 5.0]],
            "yes_asks": [[0.55, 5.0]],
        },
        {
            "timestamp_utc": "2026-01-01T12:00:01Z",
            "sequence": 2,
            "market_id": "identity-market",
            "yes_token_id": "yes-b",
            "fair_yes": 0.60,
            "yes_bids": [[0.50, 5.0]],
            "yes_asks": [[0.55, 5.0]],
        },
    ]
    input_path = tmp_path / "identity.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    config, _, _ = _load_config()

    frames = load_clob_replay(input_path, config)

    assert frames[0].snapshot.validity is MarketValidity.VALID
    assert frames[1].snapshot.validity is MarketValidity.MALFORMED
    assert "malformed" in frames[1].snapshot.validity_reasons


def test_execution_research_writes_lifecycle_and_execution_artifacts(tmp_path) -> None:
    config, config_path, config_hash = _load_config()
    _, output_dir, summary = run_execution_research(
        SAMPLE_INPUT,
        tmp_path / "runs",
        config,
        config_path=config_path,
        config_hash=config_hash,
        run_id="execution-research-test",
    )

    assert summary["mode"] == "execution-research"
    assert summary["input_sha256"]
    assert summary["config_sha256"] == config_hash
    assert summary["code_sha256"]
    assert summary["validity_counts"] == {"crossed": 1, "discontinuous": 1, "malformed": 1, "stale": 1, "valid": 15}
    assert summary["claims"]["live_football_execution"] is False
    with (output_dir / "execution_experiment_matrix.csv").open(encoding="utf-8", newline="") as handle:
        dimensions = {row["dimension"] for row in csv.DictReader(handle)}
    assert dimensions >= {
        "baseline",
        "fair_value_edge_offset",
        "spread",
        "book_imbalance",
        "latency_ms",
        "execution_profile",
        "initial_inventory_yes",
        "fee_bps",
    }
    for filename in (
        "summary.json",
        "execution_replay_validity.csv",
        "execution_decisions.csv",
        "execution_orders.csv",
        "execution_lifecycle_events.csv",
        "execution_fills.csv",
        "execution_markouts.csv",
        "execution_account.csv",
        "execution_profile_results.csv",
        "execution_experiment_matrix.csv",
        "execution_report.md",
        "execution_casebook.md",
    ):
        assert (output_dir / filename).exists()

    lifecycle = (output_dir / "execution_lifecycle_events.csv").read_text(encoding="utf-8")
    for event_name in ("decision", "risk_check", "submit", "acknowledge", "rest", "partial_fill", "fill", "cancel_request", "cancel_acknowledge", "cancel_fill_race", "expire"):
        assert event_name in lifecycle
    assert "reject" in lifecycle
    with (output_dir / "execution_lifecycle_events.csv").open(encoding="utf-8", newline="") as handle:
        lifecycle_rows = list(csv.DictReader(handle))
    submit_row = next(row for row in lifecycle_rows if row["event_type"] == "submit")
    cancel_ack_row = next(row for row in lifecycle_rows if row["event_type"] == "cancel_acknowledge")
    assert submit_row["status_after"] == "SUBMITTED"
    assert cancel_ack_row["status_before"] == "CANCEL_REQUESTED"
    assert cancel_ack_row["status_after"] == "CANCELLED"
    decision_rows = list(csv.DictReader((output_dir / "execution_decisions.csv").open(encoding="utf-8", newline="")))
    assert any(row["risk_result"] == "max_position" and not row["order_id"] for row in decision_rows)
    assert "invalid_market_state" in (output_dir / "execution_decisions.csv").read_text(encoding="utf-8")
    account_rows = list(csv.DictReader((output_dir / "execution_account.csv").open(encoding="utf-8", newline="")))
    for row in account_rows:
        mark = float(row["mark_yes"]) if row["mark_yes"] else None
        marked_value = float(row["position_yes"]) * mark if mark is not None else 0.0
        expected_total_pnl = float(row["cash"]) + marked_value - 100.0
        assert float(row["total_pnl"]) == pytest.approx(expected_total_pnl)
    report = (output_dir / "execution_report.md").read_text(encoding="utf-8")
    assert "Resting ms" in report
    assert "Next adverse selection" in report
    assert "`fair_yes` is a replay input" in report
    casebook = (output_dir / "execution_casebook.md").read_text(encoding="utf-8")
    assert "Risk rejection:" in casebook
    assert "max_position" in casebook


def test_execution_research_is_deterministic_for_same_inputs(tmp_path) -> None:
    config, config_path, config_hash = _load_config()
    _, first_dir, first_summary = run_execution_research(
        SAMPLE_INPUT,
        tmp_path / "first",
        config,
        config_path=config_path,
        config_hash=config_hash,
        run_id="same-run",
    )
    _, second_dir, second_summary = run_execution_research(
        SAMPLE_INPUT,
        tmp_path / "second",
        config,
        config_path=config_path,
        config_hash=config_hash,
        run_id="same-run",
    )

    assert first_summary["input_sha256"] == second_summary["input_sha256"]
    assert first_summary["config_sha256"] == second_summary["config_sha256"]
    assert first_summary["profile_results"] == second_summary["profile_results"]
    assert (first_dir / "execution_profile_results.csv").read_bytes() == (second_dir / "execution_profile_results.csv").read_bytes()
    assert (first_dir / "execution_lifecycle_events.csv").read_bytes() == (second_dir / "execution_lifecycle_events.csv").read_bytes()


def test_execution_research_cli_and_report_happy_path(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("PMFE_OUTPUT_ROOT", str(tmp_path / "runs"))

    assert cli.main(["execution-research", "--sample", "--config", str(SAMPLE_CONFIG), "--run-id", "execution-cli"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "execution-research"
    assert payload["input_sha256"]
    assert payload["artifacts"]["execution_lifecycle_events_csv"].endswith("execution-cli\\execution_lifecycle_events.csv") or payload["artifacts"]["execution_lifecycle_events_csv"].endswith("execution-cli/execution_lifecycle_events.csv")

    assert cli.main(["report", "--run-id", "execution-cli"]) == 0
    report_payload = json.loads(capsys.readouterr().out)
    assert "execution_profile_results_csv" in report_payload["artifacts"]


def test_cancel_fill_race_is_audited(tmp_path) -> None:
    rows = [
        {
            "timestamp_utc": "2026-01-01T12:00:00Z",
            "book_timestamp_utc": "2026-01-01T12:00:00Z",
            "sequence": 1,
            "market_id": "race-market",
            "yes_token_id": "race-yes",
            "fair_yes": 0.70,
            "yes_bids": [[0.50, 10.0]],
            "yes_asks": [[0.60, 5.0]],
        },
        {
            "timestamp_utc": "2026-01-01T12:00:01Z",
            "book_timestamp_utc": "2026-01-01T12:00:01Z",
            "sequence": 2,
            "market_id": "race-market",
            "yes_token_id": "race-yes",
            "fair_yes": 0.40,
            "yes_bids": [[0.40, 5.0]],
            "yes_asks": [[0.60, 5.0]],
        },
        {
            "timestamp_utc": "2026-01-01T12:00:02Z",
            "book_timestamp_utc": "2026-01-01T12:00:02Z",
            "sequence": 3,
            "market_id": "race-market",
            "yes_token_id": "race-yes",
            "fair_yes": 0.40,
            "yes_bids": [[0.48, 5.0]],
            "yes_asks": [[0.49, 5.0]],
        },
    ]
    input_path = tmp_path / "race.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    config, config_path, config_hash = _load_config()
    from dataclasses import replace

    config = replace(config, cancel_latency_ms=2000)
    _, output_dir, _ = run_execution_research(
        input_path,
        tmp_path / "runs",
        config,
        config_path=config_path,
        config_hash=config_hash,
        run_id="race-run",
    )

    lifecycle = (output_dir / "execution_lifecycle_events.csv").read_text(encoding="utf-8")
    assert LifecycleEventType.CANCEL_FILL_RACE.value in lifecycle


def test_execution_replay_rejects_empty_or_all_invalid_input(tmp_path) -> None:
    config, _, _ = _load_config()
    empty_path = tmp_path / "empty.jsonl"
    empty_path.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="contains no rows"):
        load_clob_replay(empty_path, config)

    invalid_path = tmp_path / "invalid.jsonl"
    invalid_path.write_text(json.dumps({"market_id": "bad"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="contains no valid market states"):
        load_clob_replay(invalid_path, config)


def test_execution_config_rejects_invalid_profiles(tmp_path) -> None:
    invalid_config = tmp_path / "invalid-config.json"
    invalid_config.write_text(json.dumps({"profiles": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="profiles must be a non-empty array"):
        load_execution_research_config(invalid_config)


def test_unfilled_order_expires_after_replay_end(tmp_path) -> None:
    row = {
        "timestamp_utc": "2026-01-01T12:00:00Z",
        "book_timestamp_utc": "2026-01-01T12:00:00Z",
        "sequence": 1,
        "market_id": "expiry-market",
        "yes_token_id": "expiry-yes",
        "fair_yes": 0.70,
        "yes_bids": [[0.50, 10.0]],
        "yes_asks": [[0.60, 5.0]],
    }
    input_path = tmp_path / "expiry.jsonl"
    input_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    config, config_path, config_hash = _load_config()
    _, output_dir, _ = run_execution_research(
        input_path,
        tmp_path / "runs",
        config,
        config_path=config_path,
        config_hash=config_hash,
        run_id="expiry-run",
    )

    assert "expire" in (output_dir / "execution_lifecycle_events.csv").read_text(encoding="utf-8")


def test_cancel_acknowledgement_blocks_late_fill(tmp_path) -> None:
    rows = [
        {
            "timestamp_utc": "2026-01-01T12:00:00Z",
            "book_timestamp_utc": "2026-01-01T12:00:00Z",
            "sequence": 1,
            "market_id": "cancel-market",
            "yes_token_id": "cancel-yes",
            "fair_yes": 0.70,
            "yes_bids": [[0.50, 10.0]],
            "yes_asks": [[0.60, 5.0]],
        },
        {
            "timestamp_utc": "2026-01-01T12:00:01Z",
            "book_timestamp_utc": "2026-01-01T12:00:01Z",
            "sequence": 2,
            "market_id": "cancel-market",
            "yes_token_id": "cancel-yes",
            "fair_yes": 0.40,
            "yes_bids": [[0.40, 5.0]],
            "yes_asks": [[0.60, 5.0]],
        },
        {
            "timestamp_utc": "2026-01-01T12:00:04Z",
            "book_timestamp_utc": "2026-01-01T12:00:04Z",
            "sequence": 3,
            "market_id": "cancel-market",
            "yes_token_id": "cancel-yes",
            "fair_yes": 0.40,
            "yes_bids": [[0.48, 5.0]],
            "yes_asks": [[0.49, 5.0]],
        },
    ]
    input_path = tmp_path / "cancel-late-fill.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    config, config_path, config_hash = _load_config()
    from dataclasses import replace

    config = replace(config, cancel_latency_ms=1000)
    _, output_dir, _ = run_execution_research(
        input_path,
        tmp_path / "runs",
        config,
        config_path=config_path,
        config_hash=config_hash,
        run_id="cancel-late-fill",
    )

    fills = (output_dir / "execution_fills.csv").read_text(encoding="utf-8")
    lifecycle = (output_dir / "execution_lifecycle_events.csv").read_text(encoding="utf-8")
    assert "cancel_acknowledge" in lifecycle
    assert "cancel_fill_race" not in lifecycle
    assert fills.count("cancel-market") == 0
