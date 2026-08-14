from __future__ import annotations

import csv
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from datetime import timedelta

import pytest

from polymarket_fair_value_engine import cli
from polymarket_fair_value_engine.execution_research.config import load_execution_research_config
from polymarket_fair_value_engine.execution_research.engine import _Account, _fill_order, _risk_check, _validate_order_fill, run_execution_research
from polymarket_fair_value_engine.execution_research.replay import load_clob_replay
from polymarket_fair_value_engine.execution_research.types import (
    DecisionSide,
    ExecutionStyle,
    LifecycleEventType,
    LifecycleStatus,
    MarketValidity,
    ResearchOrder,
)


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
    assert summary["claims"]["recorded_public_evidence"] is False
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
        "visible_depth_multiplier",
        "queue_ahead_fraction",
        "passive_fill_fraction",
    }
    for filename in (
        "summary.json",
        "execution_replay_validity.csv",
        "execution_decisions.csv",
        "execution_orders.csv",
        "execution_lifecycle_events.csv",
        "execution_fills.csv",
        "execution_markouts.csv",
        "execution_attribution.csv",
        "execution_markout_slices.csv",
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
    for event_type in ("acknowledge", "cancel_request", "cancel_acknowledge", "expire"):
        event_counts = Counter(row["order_id"] for row in lifecycle_rows if row["event_type"] == event_type)
        assert all(count == 1 for count in event_counts.values())
    order_rows = list(csv.DictReader((output_dir / "execution_orders.csv").open(encoding="utf-8", newline="")))
    assert all(float(row["remaining_size"]) >= -1e-9 for row in order_rows)
    assert all(float(row["filled_size"]) <= float(row["size"]) + 1e-9 for row in order_rows)
    decision_rows = list(csv.DictReader((output_dir / "execution_decisions.csv").open(encoding="utf-8", newline="")))
    assert any(row["risk_result"] == "max_position" and not row["order_id"] for row in decision_rows)
    assert "invalid_market_state" in (output_dir / "execution_decisions.csv").read_text(encoding="utf-8")
    with (output_dir / "execution_attribution.csv").open(encoding="utf-8", newline="") as handle:
        attribution_rows = list(csv.DictReader(handle))
    assert attribution_rows
    assert {
        "raw_model_edge",
        "latency_mid_impact",
        "queue_depth_adjustment",
        "fill_quantity",
        "unfilled_quantity",
        "inventory_after",
        "net_realized_edge",
    } <= set(attribution_rows[0])
    first_filled = next(row for row in attribution_rows if row["opportunity_type"] == "filled")
    assert float(first_filled["decision_mid_yes"]) != float(first_filled["fill_mid_yes"])
    assert float(first_filled["spread_paid_or_captured"]) < 0.0
    with (output_dir / "execution_markout_slices.csv").open(encoding="utf-8", newline="") as handle:
        slice_rows = list(csv.DictReader(handle))
    assert {row["slice_type"] for row in slice_rows} == {
        "edge_bucket",
        "spread_bucket",
        "inventory_bucket",
        "latency_bucket",
    }
    assert all("markout_coverage" in row for row in slice_rows)
    for artifact_key, artifact_path in summary["artifacts"].items():
        assert summary["artifact_sha256"][artifact_key] == sha256(Path(artifact_path).read_bytes()).hexdigest()
    account_rows = list(csv.DictReader((output_dir / "execution_account.csv").open(encoding="utf-8", newline="")))
    for row in account_rows:
        mark = float(row["mark_yes"]) if row["mark_yes"] else None
        marked_value = float(row["position_yes"]) * mark if mark is not None else 0.0
        expected_total_pnl = float(row["cash"]) + marked_value - 100.0
        assert float(row["total_pnl"]) == pytest.approx(expected_total_pnl)
        if mark is None:
            assert float(row["unrealized_pnl"]) == 0.0
    report = (output_dir / "execution_report.md").read_text(encoding="utf-8")
    assert "Resting ms" in report
    assert "Next adverse selection" in report
    assert "`fair_yes` is a replay input" in report
    casebook = (output_dir / "execution_casebook.md").read_text(encoding="utf-8")
    for section in (
        "Case A: Passive Edge Survives",
        "Case B: Passive Edge Disappears",
        "Case C: Aggressive Execution Is Justified",
        "Case D: Apparent Edge Is Not Tradeable",
        "Case E: Cancel/Fill Race",
    ):
        assert section in casebook
    assert "Observed input" in casebook
    assert "Modeling assumption" in casebook
    assert "Execution outcome" in casebook
    assert "Limitation" in casebook
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


def test_account_partial_close_and_reversal_preserve_pnl_identity() -> None:
    partial = _Account(100.0)
    partial.apply_fill(DecisionSide.BUY_YES, 0.40, 10.0, 0.10)
    partial.apply_fill(DecisionSide.SELL_YES, 0.60, 4.0, 0.04)

    assert partial.position == pytest.approx(6.0)
    assert partial.average_cost == pytest.approx(0.41)
    assert partial.realized_pnl == pytest.approx(0.72)
    assert partial.total_pnl(0.50) == pytest.approx(partial.realized_pnl + partial.unrealized_pnl(0.50))

    reversal = _Account(100.0)
    reversal.apply_fill(DecisionSide.BUY_YES, 0.40, 10.0, 0.10)
    reversal.apply_fill(DecisionSide.SELL_YES, 0.60, 15.0, 0.15)

    assert reversal.position == pytest.approx(-5.0)
    assert reversal.average_cost == pytest.approx(0.59)
    assert reversal.realized_pnl == pytest.approx(1.80)
    assert reversal.unrealized_pnl(0.50) == pytest.approx(0.45)
    assert reversal.total_pnl(0.50) == pytest.approx(2.25)
    assert reversal.total_pnl(0.50) == pytest.approx(reversal.realized_pnl + reversal.unrealized_pnl(0.50))
    assert reversal.unrealized_pnl(None) == 0.0
    assert reversal.total_pnl(None) == pytest.approx(reversal.cash - reversal.starting_equity)


def test_risk_limits_and_invalid_fill_sizes_fail_loudly() -> None:
    config, _, _ = _load_config()
    account = _Account(config.starting_cash)

    assert _risk_check(account, DecisionSide.BUY_YES, 0.90, 20.0, config) == "max_order_notional"
    account.position = config.max_position - 1.0
    assert _risk_check(account, DecisionSide.BUY_YES, 0.50, 2.0, config) == "max_position"
    with pytest.raises(ValueError, match="fill size must be positive"):
        account.apply_fill(DecisionSide.BUY_YES, 0.50, -1.0, 0.0)

    frame = load_clob_replay(SAMPLE_INPUT, config)[0]
    assert frame.snapshot.timestamp is not None
    order = ResearchOrder(
        order_id="overfill",
        decision_id="overfill-decision",
        market_id=frame.snapshot.market_id,
        profile_name="base",
        style=ExecutionStyle.PASSIVE,
        side=DecisionSide.BUY_YES,
        price=0.50,
        size=1.0,
        remaining_size=0.25,
        status=LifecycleStatus.RESTING,
        decision_timestamp=frame.snapshot.timestamp,
        submit_timestamp=frame.snapshot.timestamp,
        acknowledge_timestamp=frame.snapshot.timestamp,
        expiry_timestamp=frame.snapshot.timestamp + timedelta(seconds=1),
        fair_yes=frame.fair_yes or 0.0,
        mid_yes=frame.snapshot.mid or 0.0,
        edge_after_fee=0.0,
        raw_model_edge=0.0,
    )
    with pytest.raises(RuntimeError, match="overfilled"):
        _validate_order_fill(order, 0.50)


def test_negative_order_remaining_fails_before_fill() -> None:
    config, _, _ = _load_config()
    frame = load_clob_replay(SAMPLE_INPUT, config)[0]
    assert frame.snapshot.timestamp is not None
    timestamp = frame.snapshot.timestamp
    order = ResearchOrder(
        order_id="negative-remaining",
        decision_id="negative-decision",
        market_id=frame.snapshot.market_id,
        profile_name="base",
        style=ExecutionStyle.PASSIVE,
        side=DecisionSide.BUY_YES,
        price=0.50,
        size=1.0,
        remaining_size=-0.1,
        status=LifecycleStatus.RESTING,
        decision_timestamp=timestamp,
        submit_timestamp=timestamp,
        acknowledge_timestamp=timestamp,
        expiry_timestamp=timestamp + timedelta(seconds=1),
        fair_yes=frame.fair_yes or 0.0,
        mid_yes=frame.snapshot.mid or 0.0,
        edge_after_fee=0.0,
        raw_model_edge=0.0,
    )

    with pytest.raises(RuntimeError, match="negative remaining size"):
        _fill_order(
            order,
            frame,
            config.profiles[1],
            config,
            _Account(config.starting_cash),
            [],
            [],
            [0],
            [0],
            race=False,
        )
