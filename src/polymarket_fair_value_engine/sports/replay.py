from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from polymarket_fair_value_engine.analytics.fills import export_dataclasses, write_rows
from polymarket_fair_value_engine.analytics.reports import create_run_directory
from polymarket_fair_value_engine.sports.normalize import FootballCalibrationRow, FootballDecisionSide, FootballMarkoutRow, FootballReplayFrame, FootballReplayQuoteRow, FootballStateChange, FootballStateChangeType, FootballMatchStatus, load_football_replay_frames
from polymarket_fair_value_engine.sports.odds import FootballBinaryMarketType
from polymarket_fair_value_engine.sports.pricing import DEFAULT_FOOTBALL_PRICING_CONFIG, FootballPricingConfig, price_binary_market


def _leader(home_goals: int, away_goals: int) -> str | None:
    if home_goals > away_goals:
        return "home"
    if away_goals > home_goals:
        return "away"
    return None


def detect_state_changes(frames: tuple[FootballReplayFrame, ...]) -> tuple[FootballStateChange, ...]:
    ordered_frames = sorted(frames, key=lambda frame: (frame.fixture.event_id, frame.timestamp_utc))
    changes: list[FootballStateChange] = []
    previous_by_event: dict[str, FootballReplayFrame] = {}

    for frame in ordered_frames:
        previous = previous_by_event.get(frame.fixture.event_id)
        if previous is not None:
            prev_state = previous.match_state
            current_state = frame.match_state

            if prev_state.status is FootballMatchStatus.PREGAME and current_state.status is FootballMatchStatus.INPLAY:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.KICKOFF,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )

            if current_state.home_goals > prev_state.home_goals:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.GOAL_HOME,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )
            if current_state.away_goals > prev_state.away_goals:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.GOAL_AWAY,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )

            previous_leader = _leader(prev_state.home_goals, prev_state.away_goals)
            current_leader = _leader(current_state.home_goals, current_state.away_goals)
            if current_state.home_goals == current_state.away_goals and prev_state.home_goals != prev_state.away_goals:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.EQUALIZER,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )
            if previous_leader is not None and current_leader is not None and previous_leader != current_leader:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.LEAD_CHANGE,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )

            if current_state.home_red_cards > prev_state.home_red_cards:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.RED_CARD_HOME,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )
            if current_state.away_red_cards > prev_state.away_red_cards:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.RED_CARD_AWAY,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )

            if prev_state.status is not FootballMatchStatus.FINISHED and current_state.status is FootballMatchStatus.FINISHED:
                changes.append(
                    FootballStateChange(
                        frame_id=frame.frame_id,
                        event_id=frame.fixture.event_id,
                        timestamp_utc=frame.timestamp_utc,
                        change_type=FootballStateChangeType.FINISH,
                        minute=current_state.minute,
                        home_goals=current_state.home_goals,
                        away_goals=current_state.away_goals,
                        home_red_cards=current_state.home_red_cards,
                        away_red_cards=current_state.away_red_cards,
                    )
                )

        previous_by_event[frame.fixture.event_id] = frame
    return tuple(changes)


def _group_state_changes(changes: tuple[FootballStateChange, ...]) -> dict[str, list[FootballStateChange]]:
    grouped: dict[str, list[FootballStateChange]] = defaultdict(list)
    for change in changes:
        grouped[change.event_id].append(change)
    return grouped


def _active_state_changes(
    frame: FootballReplayFrame,
    changes_by_event: dict[str, list[FootballStateChange]],
    config: FootballPricingConfig,
) -> tuple[FootballStateChangeType, ...]:
    active: list[FootballStateChangeType] = []
    for change in changes_by_event.get(frame.fixture.event_id, []):
        if change.timestamp_utc > frame.timestamp_utc:
            continue
        age_seconds = (frame.timestamp_utc - change.timestamp_utc).total_seconds()
        if change.change_type in {
            FootballStateChangeType.GOAL_HOME,
            FootballStateChangeType.GOAL_AWAY,
            FootballStateChangeType.EQUALIZER,
            FootballStateChangeType.LEAD_CHANGE,
        } and age_seconds <= config.goal_cooldown_minutes * 60:
            active.append(change.change_type)
        if change.change_type in {
            FootballStateChangeType.RED_CARD_HOME,
            FootballStateChangeType.RED_CARD_AWAY,
        } and age_seconds <= config.red_card_cooldown_minutes * 60:
            active.append(change.change_type)
    return tuple(dict.fromkeys(active))


def price_replay_frames(
    frames: tuple[FootballReplayFrame, ...],
    changes: tuple[FootballStateChange, ...],
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> tuple[FootballReplayQuoteRow, ...]:
    changes_by_event = _group_state_changes(changes)
    quote_rows: list[FootballReplayQuoteRow] = []

    for frame in sorted(frames, key=lambda item: (item.timestamp_utc, item.fixture.event_id, item.frame_id)):
        active_tags = _active_state_changes(frame, changes_by_event, config)
        for market in frame.markets:
            priced = price_binary_market(
                market=market,
                bookmaker_snapshots=frame.bookmaker_snapshots,
                timestamp_utc=frame.timestamp_utc,
                match_state=frame.match_state,
                recent_state_changes=active_tags,
                config=config,
            )
            quote_rows.append(
                FootballReplayQuoteRow(
                    frame_id=frame.frame_id,
                    timestamp_utc=frame.timestamp_utc,
                    event_id=frame.fixture.event_id,
                    league=frame.fixture.league,
                    kickoff_utc=frame.fixture.kickoff_utc,
                    home_team=frame.fixture.home_team,
                    away_team=frame.fixture.away_team,
                    match_status=frame.match_state.status,
                    minute=frame.match_state.minute,
                    added_time=frame.match_state.added_time,
                    home_goals=frame.match_state.home_goals,
                    away_goals=frame.match_state.away_goals,
                    home_red_cards=frame.match_state.home_red_cards,
                    away_red_cards=frame.match_state.away_red_cards,
                    state_change_tags=active_tags,
                    market_id=market.market_id,
                    market_slug=market.market_slug,
                    market_question=market.market_question,
                    market_type=priced.market_type,
                    fair_yes=priced.fair_yes,
                    fair_no=priced.fair_no,
                    uncertainty=priced.uncertainty,
                    market_mid_yes=priced.market_mid_yes,
                    best_bid_yes=priced.best_bid_yes,
                    best_ask_yes=priced.best_ask_yes,
                    source_overround=priced.source_overround,
                    source_name=priced.source_name,
                    source_count=priced.source_count,
                    quote_bid_yes=priced.quote_bid_yes,
                    quote_ask_yes=priced.quote_ask_yes,
                    buy_edge_vs_ask=priced.buy_edge_vs_ask,
                    sell_edge_vs_bid=priced.sell_edge_vs_bid,
                    edge_vs_mid=priced.edge_vs_mid,
                    max_actionable_edge=priced.max_actionable_edge,
                    decision_side=priced.decision_side,
                    edge_vs_best_ask=priced.edge_vs_best_ask,
                    edge_vs_best_bid=priced.edge_vs_best_bid,
                    no_trade_reason=priced.no_trade_reason,
                )
            )
    return tuple(quote_rows)


def _decision_sign(decision_side: FootballDecisionSide) -> int:
    if decision_side is FootballDecisionSide.BUY_YES:
        return 1
    if decision_side is FootballDecisionSide.SELL_YES:
        return -1
    return 0


def _settlement_yes(final_home_goals: int, final_away_goals: int, market_type: str) -> float | None:
    try:
        binary_market_type = FootballBinaryMarketType(market_type)
    except ValueError:
        return None

    if binary_market_type is FootballBinaryMarketType.HOME_WIN:
        return 1.0 if final_home_goals > final_away_goals else 0.0
    if binary_market_type is FootballBinaryMarketType.AWAY_WIN:
        return 1.0 if final_away_goals > final_home_goals else 0.0
    if binary_market_type is FootballBinaryMarketType.DRAW:
        return 1.0 if final_home_goals == final_away_goals else 0.0
    if binary_market_type is FootballBinaryMarketType.HOME_OR_DRAW:
        return 1.0 if final_home_goals >= final_away_goals else 0.0
    if binary_market_type is FootballBinaryMarketType.AWAY_OR_DRAW:
        return 1.0 if final_away_goals >= final_home_goals else 0.0
    if binary_market_type is FootballBinaryMarketType.EITHER_TEAM_WINS:
        return 1.0 if final_home_goals != final_away_goals else 0.0
    return None


def build_markout_rows(
    frames: tuple[FootballReplayFrame, ...],
    quote_rows: tuple[FootballReplayQuoteRow, ...],
) -> tuple[FootballMarkoutRow, ...]:
    final_states: dict[str, FootballReplayFrame] = {}
    for frame in frames:
        if frame.match_state.status is FootballMatchStatus.FINISHED:
            final_states[frame.fixture.event_id] = frame

    rows_by_market: dict[tuple[str, str], list[FootballReplayQuoteRow]] = defaultdict(list)
    for row in sorted(quote_rows, key=lambda item: (item.event_id, item.market_id, item.timestamp_utc)):
        rows_by_market[(row.event_id, row.market_id)].append(row)

    markouts: list[FootballMarkoutRow] = []
    for market_rows in rows_by_market.values():
        for index, row in enumerate(market_rows):
            next_row = market_rows[index + 1] if index + 1 < len(market_rows) else None
            next_row_2 = market_rows[index + 2] if index + 2 < len(market_rows) else None
            future_rows = market_rows[index + 1 :]
            current_mid = row.market_mid_yes
            next_mid = next_row.market_mid_yes if next_row is not None else None
            mid_2_steps = next_row_2.market_mid_yes if next_row_2 is not None else None
            sign = _decision_sign(row.decision_side)

            next_snapshot_markout = None
            if current_mid is not None and next_mid is not None:
                next_snapshot_markout = round(next_mid - current_mid, 6)

            next_snapshot_edge_capture = None
            if sign != 0 and next_snapshot_markout is not None:
                next_snapshot_edge_capture = round(sign * next_snapshot_markout, 6)

            markout_2_steps = None
            if current_mid is not None and mid_2_steps is not None:
                markout_2_steps = round(mid_2_steps - current_mid, 6)

            max_favorable_move = None
            max_adverse_move = None
            if sign != 0 and current_mid is not None:
                directional_moves = [
                    round(sign * ((future.market_mid_yes or current_mid) - current_mid), 6)
                    for future in future_rows
                    if future.market_mid_yes is not None
                ]
                if directional_moves:
                    max_favorable_move = round(max(max(move, 0.0) for move in directional_moves), 6)
                    max_adverse_move = round(max(max(-move, 0.0) for move in directional_moves), 6)

            final_frame = final_states.get(row.event_id)
            eventual_settlement = None
            eventual_resolution_markout = None
            if final_frame is not None:
                eventual_settlement = _settlement_yes(
                    final_frame.match_state.home_goals,
                    final_frame.match_state.away_goals,
                    row.market_type,
                )
                if eventual_settlement is not None and current_mid is not None:
                    eventual_resolution_markout = round(eventual_settlement - current_mid, 6)

            markouts.append(
                FootballMarkoutRow(
                    frame_id=row.frame_id,
                    timestamp_utc=row.timestamp_utc,
                    event_id=row.event_id,
                    market_id=row.market_id,
                    market_type=row.market_type,
                    match_status=row.match_status,
                    minute=row.minute,
                    decision_side=row.decision_side,
                    no_trade_reason=row.no_trade_reason,
                    fair_yes=row.fair_yes,
                    current_mid_yes=current_mid,
                    next_snapshot_mid_yes=next_mid,
                    next_snapshot_markout=next_snapshot_markout,
                    next_snapshot_edge_capture=next_snapshot_edge_capture,
                    mid_yes_2_steps=mid_2_steps,
                    markout_2_steps=markout_2_steps,
                    max_favorable_move=max_favorable_move,
                    max_adverse_move=max_adverse_move,
                    eventual_settlement_yes=eventual_settlement,
                    eventual_resolution_markout=eventual_resolution_markout,
                )
            )
    return tuple(markouts)


def _edge_bucket(max_actionable_edge: float) -> str:
    if max_actionable_edge < 0.01:
        return "0.00-0.01"
    if max_actionable_edge < 0.02:
        return "0.01-0.02"
    if max_actionable_edge < 0.05:
        return "0.02-0.05"
    return "0.05+"


def build_calibration_rows(
    quote_rows: tuple[FootballReplayQuoteRow, ...],
    markout_rows: tuple[FootballMarkoutRow, ...],
) -> tuple[FootballCalibrationRow, ...]:
    quote_map = {(row.frame_id, row.market_id): row for row in quote_rows}
    calibration_groups: dict[tuple[str, str], list[FootballMarkoutRow]] = defaultdict(list)

    for markout in markout_rows:
        quote = quote_map[(markout.frame_id, markout.market_id)]
        if quote.decision_side is FootballDecisionSide.NO_TRADE:
            continue
        calibration_groups[("edge_bucket", _edge_bucket(quote.max_actionable_edge))].append(markout)
        calibration_groups[("market_type", quote.market_type)].append(markout)
        phase = "pregame" if quote.match_status is FootballMatchStatus.PREGAME else "inplay"
        calibration_groups[("match_phase", phase)].append(markout)

    rows: list[FootballCalibrationRow] = []
    for (bucket_type, bucket_value), grouped_rows in sorted(calibration_groups.items()):
        next_markouts = [row.next_snapshot_markout for row in grouped_rows if row.next_snapshot_markout is not None]
        markout_2_steps = [row.markout_2_steps for row in grouped_rows if row.markout_2_steps is not None]
        edge_captures = [row.next_snapshot_edge_capture for row in grouped_rows if row.next_snapshot_edge_capture is not None]
        sign_hit_rate = None
        if edge_captures:
            sign_hit_rate = round(sum(1 for value in edge_captures if value > 0.0) / len(edge_captures), 6)
        rows.append(
            FootballCalibrationRow(
                bucket_type=bucket_type,
                bucket_value=bucket_value,
                observations=len(grouped_rows),
                average_next_snapshot_markout=round(sum(next_markouts) / len(next_markouts), 6) if next_markouts else None,
                average_markout_2_steps=round(sum(markout_2_steps) / len(markout_2_steps), 6) if markout_2_steps else None,
                sign_hit_rate=sign_hit_rate,
            )
        )
    return tuple(rows)


def build_no_trade_rows(quote_rows: tuple[FootballReplayQuoteRow, ...]) -> list[dict[str, object]]:
    counts: dict[str, int] = defaultdict(int)
    for row in quote_rows:
        if row.no_trade_reason:
            counts[row.no_trade_reason] += 1
    return [
        {"no_trade_reason": reason, "count": count}
        for reason, count in sorted(counts.items())
    ]


def _report_markout_definition() -> list[str]:
    return [
        "- `next_snapshot_markout`: next midpoint minus current midpoint.",
        "- `next_snapshot_edge_capture`: next midpoint move expressed in the chosen decision direction.",
        "- `markout_2_steps`: midpoint change two frames forward versus the current midpoint.",
        "- `eventual_resolution_markout`: final binary settlement minus the current midpoint.",
    ]


def _report_quote_definition() -> list[str]:
    return [
        "- `buy_edge_vs_ask`: fair YES minus the current best ask.",
        "- `sell_edge_vs_bid`: current best bid minus fair YES.",
        "- `max_actionable_edge`: `max(buy_edge_vs_ask, sell_edge_vs_bid, 0.0)`.",
    ]


def write_football_report(
    output_path: Path,
    summary: dict[str, object],
    state_changes: tuple[FootballStateChange, ...],
    calibration_rows: tuple[FootballCalibrationRow, ...],
    no_trade_rows: list[dict[str, object]],
) -> None:
    lines = [
        "# Football Replay Report",
        "",
        "## Summary",
        f"- Run ID: `{summary['run_id']}`",
        f"- Fixtures: `{summary['fixtures']}`",
        f"- Frame snapshots: `{summary['snapshots']}`",
        f"- Priced market snapshots: `{summary['priced_snapshots']}`",
        f"- Quoteable market snapshots: `{summary['quoteable_snapshots']}`",
        f"- Positive-edge market snapshots: `{summary['positive_edge_snapshots']}`",
        f"- Average next-snapshot markout: `{summary['average_next_snapshot_markout']}`",
        f"- Average 2-step markout: `{summary['average_markout_2_steps']}`",
        "",
        "## Markout Definitions",
        *_report_markout_definition(),
        "",
        "## Quote Decision Fields",
        *_report_quote_definition(),
        "",
        "## State Changes",
    ]
    if state_changes:
        for change in state_changes:
            lines.append(
                f"- `{change.timestamp_utc.isoformat()}` `{change.event_id}` `{change.change_type.value}` at minute `{change.minute}`"
            )
    else:
        lines.append("- No state changes detected.")

    lines.extend(["", "## Calibration Snapshot"])
    if calibration_rows:
        for row in calibration_rows:
            lines.append(
                f"- `{row.bucket_type}` `{row.bucket_value}`: n={row.observations}, avg_next={row.average_next_snapshot_markout}, avg_2_step={row.average_markout_2_steps}, hit_rate={row.sign_hit_rate}"
            )
    else:
        lines.append("- No calibration rows available.")

    lines.extend(["", "## No-Trade Counts"])
    if no_trade_rows:
        for row in no_trade_rows:
            lines.append(f"- `{row['no_trade_reason']}`: `{row['count']}`")
    else:
        lines.append("- No no-trade reasons recorded.")

    lines.extend(
        [
            "",
            "## Limitations",
            "- Replay frames are bundled offline sample data.",
            "- In-play fair value still comes directly from bundled bookmaker 1X2 updates rather than an independent in-play model.",
            "- The sample is small, so calibration and markout statistics are illustrative rather than statistically strong.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_football_replay(
    input_path: str | Path,
    output_root: Path,
    run_id: str | None = None,
    sample_mode: bool = False,
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> tuple[str, Path, dict[str, object]]:
    frames = load_football_replay_frames(input_path)
    actual_run_id, output_dir = create_run_directory(output_root, run_id=run_id)
    state_changes = detect_state_changes(frames)
    quote_rows = price_replay_frames(frames, state_changes, config=config)
    markout_rows = build_markout_rows(frames, quote_rows)
    calibration_rows = build_calibration_rows(quote_rows, markout_rows)
    no_trade_rows = build_no_trade_rows(quote_rows)

    export_dataclasses(output_dir / "football_replay_quotes.csv", list(quote_rows))
    export_dataclasses(output_dir / "football_markouts.csv", list(markout_rows))
    export_dataclasses(output_dir / "football_calibration.csv", list(calibration_rows))
    export_dataclasses(output_dir / "football_state_changes.csv", list(state_changes))
    write_rows(output_dir / "football_no_trade_reasons.csv", no_trade_rows)

    artifacts = {
        "summary_json": str(output_dir / "summary.json"),
        "football_replay_quotes_csv": str(output_dir / "football_replay_quotes.csv"),
        "football_markouts_csv": str(output_dir / "football_markouts.csv"),
        "football_calibration_csv": str(output_dir / "football_calibration.csv"),
        "football_state_changes_csv": str(output_dir / "football_state_changes.csv"),
        "football_no_trade_reasons_csv": str(output_dir / "football_no_trade_reasons.csv"),
        "football_report_md": str(output_dir / "football_report.md"),
    }

    quoteable_rows = [row for row in quote_rows if row.no_trade_reason is None]
    positive_edge_rows = [row for row in quote_rows if row.max_actionable_edge > 0.0]
    next_markouts = [
        row.next_snapshot_markout
        for row in markout_rows
        if row.next_snapshot_markout is not None and row.decision_side is not FootballDecisionSide.NO_TRADE
    ]
    markout_2_steps = [
        row.markout_2_steps
        for row in markout_rows
        if row.markout_2_steps is not None and row.decision_side is not FootballDecisionSide.NO_TRADE
    ]
    positive_markouts = [value for value in next_markouts if value > 0.0]
    negative_markouts = [value for value in next_markouts if value < 0.0]
    mid_edge_rows = [abs(row.edge_vs_mid) for row in quote_rows if row.edge_vs_mid is not None]

    summary = {
        "run_id": actual_run_id,
        "mode": "football-replay",
        "fixtures": len({frame.fixture.event_id for frame in frames}),
        "snapshots": len(frames),
        "priced_snapshots": len(quote_rows),
        "quoteable_snapshots": len(quoteable_rows),
        "positive_edge_snapshots": len(positive_edge_rows),
        "average_absolute_edge": round(sum(mid_edge_rows) / max(1, len(mid_edge_rows)), 6),
        "average_next_snapshot_markout": round(sum(next_markouts) / len(next_markouts), 6) if next_markouts else 0.0,
        "average_markout_2_steps": round(sum(markout_2_steps) / len(markout_2_steps), 6) if markout_2_steps else 0.0,
        "max_positive_markout": round(max(positive_markouts), 6) if positive_markouts else 0.0,
        "max_negative_markout": round(min(negative_markouts), 6) if negative_markouts else 0.0,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "sample_data_is_synthetic": sample_mode,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)

    write_football_report(
        output_path=output_dir / "football_report.md",
        summary=summary,
        state_changes=state_changes,
        calibration_rows=calibration_rows,
        no_trade_rows=no_trade_rows,
    )
    return actual_run_id, output_dir, summary
