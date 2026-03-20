from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cmp_to_key
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.analytics.fills import export_dataclasses
from polymarket_fair_value_engine.analytics.reports import create_run_directory
from polymarket_fair_value_engine.sports.normalize import FootballDecisionSide, FootballMarkoutRow, FootballReplayFrame, FootballReplayQuoteRow, load_football_replay_frames
from polymarket_fair_value_engine.sports.pricing import FootballPricingConfig, football_pricing_config_from_mapping, serialize_football_pricing_config
from polymarket_fair_value_engine.sports.replay import build_markout_rows, detect_state_changes, match_phase_label, price_replay_frames, run_football_replay


@dataclass(frozen=True)
class FootballSweepStrategyDefinition:
    name: str
    description: str
    pricing_config: FootballPricingConfig


@dataclass(frozen=True)
class FootballSweepSelectionConfig:
    min_quoteable_snapshots: int
    primary_metric: str
    tie_breakers: tuple[str, ...]


@dataclass(frozen=True)
class FootballSweepConfig:
    strategies: tuple[FootballSweepStrategyDefinition, ...]
    selection: FootballSweepSelectionConfig


@dataclass(frozen=True)
class FootballStrategyResultRow:
    strategy_name: str
    strategy_description: str
    fixtures: int
    snapshots: int
    priced_snapshots: int
    quoteable_snapshots: int
    buy_decisions: int
    sell_decisions: int
    no_trade_snapshots: int
    no_trade_ratio: float
    average_absolute_edge: float
    average_directional_next_capture: float | None
    average_directional_2step_capture: float | None
    average_directional_eventual_capture: float | None
    positive_capture_rate: float | None
    positive_2step_capture_rate: float | None
    average_max_favorable_move: float | None
    average_max_adverse_move: float | None
    average_uncertainty: float | None
    average_source_overround: float | None
    average_source_count: float | None
    dominant_no_trade_reason: str | None
    notes: str | None


@dataclass(frozen=True)
class FootballStrategySliceRow:
    strategy_name: str
    slice_type: str
    slice_value: str
    observations: int
    quoteable_snapshots: int
    average_directional_next_capture: float | None
    average_directional_2step_capture: float | None
    positive_capture_rate: float | None
    average_max_adverse_move: float | None
    average_uncertainty: float | None


@dataclass(frozen=True)
class FootballSweepWinner:
    winner: FootballStrategyResultRow
    reason: str
    eligible_strategy_names: tuple[str, ...]
    disqualified_strategy_names: tuple[str, ...]


_SELECTION_METRICS = {
    "quoteable_snapshots",
    "no_trade_ratio",
    "average_absolute_edge",
    "average_directional_next_capture",
    "average_directional_2step_capture",
    "average_directional_eventual_capture",
    "positive_capture_rate",
    "positive_2step_capture_rate",
    "average_max_favorable_move",
    "average_max_adverse_move",
    "average_uncertainty",
    "average_source_overround",
    "average_source_count",
}


def _average(values: list[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return round(sum(filtered) / len(filtered), 6)


def _positive_rate(values: list[float | None]) -> float | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return round(sum(1 for value in filtered if value > 0.0) / len(filtered), 6)


def _dominant_no_trade_reason(quote_rows: tuple[FootballReplayQuoteRow, ...]) -> str | None:
    counts: dict[str, int] = {}
    for row in quote_rows:
        if row.no_trade_reason is None:
            continue
        counts[row.no_trade_reason] = counts.get(row.no_trade_reason, 0) + 1
    if not counts:
        return None
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _result_note(quoteable_snapshots: int, min_quoteable_snapshots: int) -> str | None:
    if quoteable_snapshots < min_quoteable_snapshots:
        return f"Below min_quoteable_snapshots={min_quoteable_snapshots}"
    return None


def load_football_sweep_config(path: str | Path) -> FootballSweepConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Football sweep config file must contain a JSON object")
    unexpected_top_level = sorted(key for key in payload.keys() if key not in {"strategies", "selection"})
    if unexpected_top_level:
        raise ValueError(f"Unknown football sweep config fields: {', '.join(unexpected_top_level)}")

    strategies_payload = payload.get("strategies")
    selection_payload = payload.get("selection")
    if not isinstance(strategies_payload, list) or not strategies_payload:
        raise ValueError("strategies must be a non-empty JSON array")
    if not isinstance(selection_payload, dict):
        raise ValueError("selection must be a JSON object")

    strategies: list[FootballSweepStrategyDefinition] = []
    seen_names: set[str] = set()
    for item in strategies_payload:
        if not isinstance(item, dict):
            raise ValueError("Each strategy entry must be a JSON object")
        unexpected_strategy_fields = sorted(key for key in item.keys() if key not in {"name", "description", "pricing_config"})
        if unexpected_strategy_fields:
            raise ValueError(f"Unknown strategy fields: {', '.join(unexpected_strategy_fields)}")
        name = item.get("name")
        description = item.get("description", "")
        pricing_payload = item.get("pricing_config")
        if not isinstance(name, str) or not name:
            raise ValueError("Each strategy requires a non-empty string name")
        if name in seen_names:
            raise ValueError(f"Duplicate strategy name: {name}")
        if not isinstance(description, str):
            raise ValueError(f"Strategy description for {name} must be a string")
        if not isinstance(pricing_payload, dict):
            raise ValueError(f"Strategy {name} requires a pricing_config object")
        strategies.append(
            FootballSweepStrategyDefinition(
                name=name,
                description=description,
                pricing_config=football_pricing_config_from_mapping(pricing_payload),
            )
        )
        seen_names.add(name)

    min_quoteable_snapshots = selection_payload.get("min_quoteable_snapshots", 0)
    primary_metric = selection_payload.get("primary_metric")
    tie_breakers = selection_payload.get("tie_breakers", [])
    unexpected_selection_fields = sorted(key for key in selection_payload.keys() if key not in {"min_quoteable_snapshots", "primary_metric", "tie_breakers"})
    if unexpected_selection_fields:
        raise ValueError(f"Unknown selection fields: {', '.join(unexpected_selection_fields)}")
    if not isinstance(min_quoteable_snapshots, int) or min_quoteable_snapshots < 0:
        raise ValueError("selection.min_quoteable_snapshots must be an integer >= 0")
    if not isinstance(primary_metric, str) or not primary_metric:
        raise ValueError("selection.primary_metric must be a non-empty string")
    if not isinstance(tie_breakers, list) or not all(isinstance(item, str) and item for item in tie_breakers):
        raise ValueError("selection.tie_breakers must be an array of non-empty strings")

    for metric_spec in [primary_metric, *tie_breakers]:
        metric_name = metric_spec[1:] if metric_spec.startswith("-") else metric_spec
        if metric_name not in _SELECTION_METRICS:
            raise ValueError(f"Unsupported selection metric: {metric_spec}")

    return FootballSweepConfig(
        strategies=tuple(strategies),
        selection=FootballSweepSelectionConfig(
            min_quoteable_snapshots=min_quoteable_snapshots,
            primary_metric=primary_metric,
            tie_breakers=tuple(tie_breakers),
        ),
    )


def build_strategy_result_row(
    strategy: FootballSweepStrategyDefinition,
    frames: tuple[FootballReplayFrame, ...],
    quote_rows: tuple[FootballReplayQuoteRow, ...],
    markout_rows: tuple[FootballMarkoutRow, ...],
    min_quoteable_snapshots: int,
) -> FootballStrategyResultRow:
    quoteable_rows = [row for row in quote_rows if row.no_trade_reason is None]
    buy_decisions = sum(1 for row in quoteable_rows if row.decision_side is FootballDecisionSide.BUY_YES)
    sell_decisions = sum(1 for row in quoteable_rows if row.decision_side is FootballDecisionSide.SELL_YES)
    no_trade_snapshots = sum(1 for row in quote_rows if row.decision_side is FootballDecisionSide.NO_TRADE)
    mid_edges = [abs(row.edge_vs_mid) for row in quote_rows if row.edge_vs_mid is not None]
    directional_next = [row.directional_next_capture for row in markout_rows if row.directional_next_capture is not None]
    directional_2step = [row.directional_2step_capture for row in markout_rows if row.directional_2step_capture is not None]
    directional_eventual = [row.directional_eventual_capture for row in markout_rows if row.directional_eventual_capture is not None]
    favorable_moves = [row.max_favorable_move for row in markout_rows if row.max_favorable_move is not None]
    adverse_moves = [row.max_adverse_move for row in markout_rows if row.max_adverse_move is not None]
    uncertainties = [row.uncertainty for row in quote_rows if row.uncertainty is not None]
    source_overrounds = [row.source_overround for row in quote_rows]
    source_counts = [float(row.source_count) for row in quote_rows]

    return FootballStrategyResultRow(
        strategy_name=strategy.name,
        strategy_description=strategy.description,
        fixtures=len({frame.fixture.event_id for frame in frames}),
        snapshots=len(frames),
        priced_snapshots=len(quote_rows),
        quoteable_snapshots=len(quoteable_rows),
        buy_decisions=buy_decisions,
        sell_decisions=sell_decisions,
        no_trade_snapshots=no_trade_snapshots,
        no_trade_ratio=round(no_trade_snapshots / max(1, len(quote_rows)), 6),
        average_absolute_edge=round(sum(mid_edges) / max(1, len(mid_edges)), 6),
        average_directional_next_capture=_average(directional_next),
        average_directional_2step_capture=_average(directional_2step),
        average_directional_eventual_capture=_average(directional_eventual),
        positive_capture_rate=_positive_rate(directional_next),
        positive_2step_capture_rate=_positive_rate(directional_2step),
        average_max_favorable_move=_average(favorable_moves),
        average_max_adverse_move=_average(adverse_moves),
        average_uncertainty=_average(uncertainties),
        average_source_overround=_average(source_overrounds),
        average_source_count=_average(source_counts),
        dominant_no_trade_reason=_dominant_no_trade_reason(quote_rows),
        notes=_result_note(len(quoteable_rows), min_quoteable_snapshots),
    )


def build_strategy_slice_rows(
    strategy_name: str,
    quote_rows: tuple[FootballReplayQuoteRow, ...],
    markout_rows: tuple[FootballMarkoutRow, ...],
) -> tuple[FootballStrategySliceRow, ...]:
    markout_map = {(row.frame_id, row.market_id): row for row in markout_rows}
    groups: dict[tuple[str, str], list[FootballReplayQuoteRow]] = {}

    def add_group(slice_type: str, slice_value: str, row: FootballReplayQuoteRow) -> None:
        groups.setdefault((slice_type, slice_value), []).append(row)

    for row in quote_rows:
        add_group("match_phase", match_phase_label(row.match_status), row)
        add_group("market_type", row.market_type, row)
        add_group("state_regime", row.state_regime, row)
        add_group("source_quality", row.source_quality, row)
        if row.decision_side in {FootballDecisionSide.BUY_YES, FootballDecisionSide.SELL_YES}:
            add_group("decision_side", row.decision_side.value, row)

    slice_rows: list[FootballStrategySliceRow] = []
    for (slice_type, slice_value), grouped_quotes in sorted(groups.items()):
        quoteable = [row for row in grouped_quotes if row.no_trade_reason is None]
        grouped_markouts = [markout_map[(row.frame_id, row.market_id)] for row in quoteable if (row.frame_id, row.market_id) in markout_map]
        slice_rows.append(
            FootballStrategySliceRow(
                strategy_name=strategy_name,
                slice_type=slice_type,
                slice_value=slice_value,
                observations=len(grouped_quotes),
                quoteable_snapshots=len(quoteable),
                average_directional_next_capture=_average([row.directional_next_capture for row in grouped_markouts]),
                average_directional_2step_capture=_average([row.directional_2step_capture for row in grouped_markouts]),
                positive_capture_rate=_positive_rate([row.directional_next_capture for row in grouped_markouts]),
                average_max_adverse_move=_average([row.max_adverse_move for row in grouped_markouts]),
                average_uncertainty=_average([row.uncertainty for row in grouped_quotes if row.uncertainty is not None]),
            )
        )
    return tuple(slice_rows)


def _metric_value(row: FootballStrategyResultRow, metric_spec: str) -> float | None:
    metric_name = metric_spec[1:] if metric_spec.startswith("-") else metric_spec
    value = getattr(row, metric_name)
    return float(value) if value is not None else None


def _compare_rows(a: FootballStrategyResultRow, b: FootballStrategyResultRow, metric_specs: tuple[str, ...]) -> int:
    for metric_spec in metric_specs:
        smaller_is_better = metric_spec.startswith("-")
        a_value = _metric_value(a, metric_spec)
        b_value = _metric_value(b, metric_spec)
        if a_value is None and b_value is None:
            continue
        if a_value is None:
            return 1
        if b_value is None:
            return -1
        if smaller_is_better:
            if a_value < b_value:
                return -1
            if a_value > b_value:
                return 1
        else:
            if a_value > b_value:
                return -1
            if a_value < b_value:
                return 1
    if a.strategy_name < b.strategy_name:
        return -1
    if a.strategy_name > b.strategy_name:
        return 1
    return 0


def select_best_strategy(
    result_rows: tuple[FootballStrategyResultRow, ...],
    selection: FootballSweepSelectionConfig,
) -> FootballSweepWinner:
    eligible = [row for row in result_rows if row.quoteable_snapshots >= selection.min_quoteable_snapshots]
    if eligible:
        disqualified = [row.strategy_name for row in result_rows if row not in eligible]
        eligibility_reason = f"Required at least {selection.min_quoteable_snapshots} quoteable snapshots."
    else:
        eligible = list(result_rows)
        disqualified = []
        eligibility_reason = "All strategies fell below the min_quoteable_snapshots filter, so the filter was ignored."

    metric_specs = (selection.primary_metric, *selection.tie_breakers)
    ranked = tuple(sorted(eligible, key=cmp_to_key(lambda a, b: _compare_rows(a, b, metric_specs))))
    winner = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else None
    deciding_metric = selection.primary_metric
    if runner_up is not None:
        for metric_spec in metric_specs:
            if _metric_value(winner, metric_spec) != _metric_value(runner_up, metric_spec):
                deciding_metric = metric_spec
                break
    reason = (
        f"{eligibility_reason} Winner `{winner.strategy_name}` ranked first on `{deciding_metric}` "
        f"with tie-breakers `{', '.join(selection.tie_breakers) or 'none'}`."
    )
    return FootballSweepWinner(
        winner=winner,
        reason=reason,
        eligible_strategy_names=tuple(row.strategy_name for row in ranked),
        disqualified_strategy_names=tuple(disqualified),
    )


def write_football_strategy_report(
    output_path: Path,
    result_rows: tuple[FootballStrategyResultRow, ...],
    slice_rows: tuple[FootballStrategySliceRow, ...],
    winner: FootballSweepWinner,
    selection: FootballSweepSelectionConfig,
) -> None:
    top_rows = result_rows[:3]
    winner_slices = [row for row in slice_rows if row.strategy_name == winner.winner.strategy_name]
    lines = [
        "# Football Strategy Sweep Report",
        "",
        "## Overview",
        "- This sweep compares multiple offline football quote/no-trade configurations on the same bundled synthetic replay dataset.",
        "- The ranking uses directional capture metrics, not raw midpoint drift alone.",
        "",
        "## Compared Strategies",
    ]
    for row in result_rows:
        lines.append(f"- `{row.strategy_name}`: {row.strategy_description}")

    lines.extend(
        [
            "",
            "## Selection Rule",
            f"- Minimum quoteable snapshots: `{selection.min_quoteable_snapshots}`",
            f"- Primary metric: `{selection.primary_metric}`",
            f"- Tie-breakers: `{', '.join(selection.tie_breakers) or 'none'}`",
            "",
            "## Leaderboard",
        ]
    )
    for row in result_rows:
        lines.append(
            f"- `{row.strategy_name}`: quoteable={row.quoteable_snapshots}, avg_dir_next={row.average_directional_next_capture}, avg_dir_2step={row.average_directional_2step_capture}, hit_rate={row.positive_capture_rate}, note={row.notes}"
        )

    lines.extend(["", "## Regime Breakdowns"])
    for row in winner_slices[:8]:
        lines.append(
            f"- `{row.slice_type}` `{row.slice_value}`: n={row.observations}, quoteable={row.quoteable_snapshots}, avg_dir_next={row.average_directional_next_capture}, avg_dir_2step={row.average_directional_2step_capture}"
        )

    lines.extend(
        [
            "",
            "## Best Strategy",
            f"- Winner: `{winner.winner.strategy_name}`",
            "",
            "## Why It Won",
            f"- {winner.reason}",
            "",
            "## Important Caveats",
            "- The replay sample is synthetic and small.",
            "- This is a tooling/evaluation exercise, not production validation or proof of alpha.",
            "- The sweep compares quote-decision quality metrics and does not claim realistic live fill behavior.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_football_sweep(
    input_path: str | Path,
    output_root: Path,
    sweep_config: FootballSweepConfig,
    run_id: str | None = None,
    sample_mode: bool = False,
    config_path: str | None = None,
) -> tuple[str, Path, dict[str, object]]:
    frames = load_football_replay_frames(input_path)
    changes = detect_state_changes(frames)
    actual_run_id, output_dir = create_run_directory(output_root, run_id=run_id)

    result_rows_unsorted: list[FootballStrategyResultRow] = []
    slice_rows: list[FootballStrategySliceRow] = []
    strategy_map: dict[str, FootballSweepStrategyDefinition] = {}

    for strategy in sweep_config.strategies:
        quote_rows = price_replay_frames(frames, changes, config=strategy.pricing_config)
        markout_rows = build_markout_rows(frames, quote_rows)
        result_rows_unsorted.append(
            build_strategy_result_row(
                strategy=strategy,
                frames=frames,
                quote_rows=quote_rows,
                markout_rows=markout_rows,
                min_quoteable_snapshots=sweep_config.selection.min_quoteable_snapshots,
            )
        )
        slice_rows.extend(build_strategy_slice_rows(strategy.name, quote_rows, markout_rows))
        strategy_map[strategy.name] = strategy

    winner = select_best_strategy(tuple(result_rows_unsorted), sweep_config.selection)
    ranked_rows = tuple(sorted(result_rows_unsorted, key=cmp_to_key(lambda a, b: _compare_rows(a, b, (sweep_config.selection.primary_metric, *sweep_config.selection.tie_breakers)))))
    best_strategy_definition = strategy_map[winner.winner.strategy_name]
    _, best_output_dir, best_summary = run_football_replay(
        input_path=input_path,
        output_root=output_dir,
        run_id="best_strategy",
        sample_mode=sample_mode,
        config=best_strategy_definition.pricing_config,
        config_name=best_strategy_definition.name,
        config_description=best_strategy_definition.description,
        config_path=config_path,
    )

    export_dataclasses(output_dir / "football_strategy_results.csv", list(ranked_rows))
    export_dataclasses(output_dir / "football_strategy_slices.csv", list(slice_rows))

    best_strategy_payload = {
        "winner": winner.winner.strategy_name,
        "reason": winner.reason,
        "eligible_strategy_names": list(winner.eligible_strategy_names),
        "disqualified_strategy_names": list(winner.disqualified_strategy_names),
        "winning_pricing_config": serialize_football_pricing_config(best_strategy_definition.pricing_config),
        "best_strategy_output_dir": str(best_output_dir),
    }
    (output_dir / "football_strategy_best.json").write_text(json.dumps(best_strategy_payload, indent=2), encoding="utf-8")
    write_football_strategy_report(
        output_path=output_dir / "football_strategy_report.md",
        result_rows=ranked_rows,
        slice_rows=tuple(slice_rows),
        winner=winner,
        selection=sweep_config.selection,
    )

    artifacts = {
        "summary_json": str(output_dir / "summary.json"),
        "football_strategy_results_csv": str(output_dir / "football_strategy_results.csv"),
        "football_strategy_slices_csv": str(output_dir / "football_strategy_slices.csv"),
        "football_strategy_report_md": str(output_dir / "football_strategy_report.md"),
        "football_strategy_best_json": str(output_dir / "football_strategy_best.json"),
        "best_strategy_summary_json": str(best_output_dir / "summary.json"),
    }
    summary = {
        "run_id": actual_run_id,
        "mode": "football-sweep",
        "strategies_compared": len(ranked_rows),
        "fixtures": len({frame.fixture.event_id for frame in frames}),
        "snapshots": len(frames),
        "winning_strategy": winner.winner.strategy_name,
        "selection_reason": winner.reason,
        "best_strategy_output_dir": str(best_output_dir),
        "selection": {
            "min_quoteable_snapshots": sweep_config.selection.min_quoteable_snapshots,
            "primary_metric": sweep_config.selection.primary_metric,
            "tie_breakers": list(sweep_config.selection.tie_breakers),
        },
        "config_path": config_path,
        "sample_data_is_synthetic": sample_mode,
        "artifacts": artifacts,
        "output_dir": str(output_dir),
        "top_strategies": [
            {
                "strategy_name": row.strategy_name,
                "quoteable_snapshots": row.quoteable_snapshots,
                "average_directional_next_capture": row.average_directional_next_capture,
                "average_directional_2step_capture": row.average_directional_2step_capture,
                "positive_capture_rate": row.positive_capture_rate,
            }
            for row in ranked_rows[:3]
        ],
        "best_strategy_replay_summary": best_summary,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return actual_run_id, output_dir, summary
