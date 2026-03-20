from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from polymarket_fair_value_engine.analytics.fills import export_dataclasses, write_rows
from polymarket_fair_value_engine.analytics.reports import create_run_directory
from polymarket_fair_value_engine.sports.normalize import FootballCalibrationRow, FootballDecisionSide, FootballMarkoutRow, FootballMatchStatus, FootballReplayFrame, FootballReplayQuoteRow, FootballStateChange, FootballStateChangeType, load_football_replay_frames
from polymarket_fair_value_engine.sports.odds import FootballBinaryMarketType
from polymarket_fair_value_engine.sports.pricing import DEFAULT_FOOTBALL_PRICING_CONFIG, FootballPricingConfig, price_binary_market, serialize_football_pricing_config


_GOAL_CHANGE_TYPES = {
    FootballStateChangeType.GOAL_HOME,
    FootballStateChangeType.GOAL_AWAY,
    FootballStateChangeType.EQUALIZER,
    FootballStateChangeType.LEAD_CHANGE,
}
_RED_CARD_CHANGE_TYPES = {
    FootballStateChangeType.RED_CARD_HOME,
    FootballStateChangeType.RED_CARD_AWAY,
}


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
        if change.change_type in _GOAL_CHANGE_TYPES and age_seconds <= config.goal_cooldown_minutes * 60:
            active.append(change.change_type)
        if change.change_type in _RED_CARD_CHANGE_TYPES and age_seconds <= config.red_card_cooldown_minutes * 60:
            active.append(change.change_type)
    return tuple(dict.fromkeys(active))


def match_phase_label(match_status: FootballMatchStatus) -> str:
    return "pregame" if match_status is FootballMatchStatus.PREGAME else "inplay"


def state_regime_label(
    match_status: FootballMatchStatus,
    state_change_tags: tuple[FootballStateChangeType, ...],
) -> str:
    if match_status is FootballMatchStatus.FINISHED:
        return "finished"
    if match_status is FootballMatchStatus.SUSPENDED:
        return "suspended"
    if any(tag in _RED_CARD_CHANGE_TYPES for tag in state_change_tags):
        return "recent_red_card"
    if any(tag in _GOAL_CHANGE_TYPES for tag in state_change_tags):
        return "recent_goal"
    return "stable"


def source_quality_label(
    source_count: int,
    source_is_stale: bool,
    source_disagreement: float,
    config: FootballPricingConfig,
) -> str:
    if source_is_stale:
        return "stale"
    if source_count <= 1:
        return "one_source"
    if source_disagreement >= config.high_disagreement_threshold:
        return "high_disagreement"
    return "normal"


def price_replay_frames(
    frames: tuple[FootballReplayFrame, ...],
    changes: tuple[FootballStateChange, ...],
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> tuple[FootballReplayQuoteRow, ...]:
    changes_by_event = _group_state_changes(changes)
    quote_rows: list[FootballReplayQuoteRow] = []

    for frame in sorted(frames, key=lambda item: (item.timestamp_utc, item.fixture.event_id, item.frame_id)):
        active_tags = _active_state_changes(frame, changes_by_event, config)
        state_regime = state_regime_label(frame.match_state.status, active_tags)
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
                    state_regime=state_regime,
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
                    source_disagreement=priced.source_disagreement,
                    source_name=priced.source_name,
                    source_count=priced.source_count,
                    source_is_stale=priced.source_is_stale,
                    source_quality=source_quality_label(
                        source_count=priced.source_count,
                        source_is_stale=priced.source_is_stale,
                        source_disagreement=priced.source_disagreement,
                        config=config,
                    ),
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

            raw_next_mid_change = None
            if current_mid is not None and next_mid is not None:
                raw_next_mid_change = round(next_mid - current_mid, 6)

            directional_next_capture = None
            if sign != 0 and raw_next_mid_change is not None:
                directional_next_capture = round(sign * raw_next_mid_change, 6)

            raw_2step_mid_change = None
            if current_mid is not None and mid_2_steps is not None:
                raw_2step_mid_change = round(mid_2_steps - current_mid, 6)

            directional_2step_capture = None
            if sign != 0 and raw_2step_mid_change is not None:
                directional_2step_capture = round(sign * raw_2step_mid_change, 6)

            max_favorable_move = None
            max_adverse_move = None
            if sign != 0 and current_mid is not None:
                directional_moves = [
                    round(sign * (future.market_mid_yes - current_mid), 6)
                    for future in future_rows
                    if future.market_mid_yes is not None
                ]
                if directional_moves:
                    max_favorable_move = round(max(max(move, 0.0) for move in directional_moves), 6)
                    max_adverse_move = round(max(max(-move, 0.0) for move in directional_moves), 6)

            final_frame = final_states.get(row.event_id)
            eventual_settlement = None
            raw_eventual_resolution_change = None
            directional_eventual_capture = None
            if final_frame is not None:
                eventual_settlement = _settlement_yes(
                    final_frame.match_state.home_goals,
                    final_frame.match_state.away_goals,
                    row.market_type,
                )
                if eventual_settlement is not None and current_mid is not None:
                    raw_eventual_resolution_change = round(eventual_settlement - current_mid, 6)
                    if sign != 0:
                        directional_eventual_capture = round(sign * raw_eventual_resolution_change, 6)

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
                    raw_next_mid_change=raw_next_mid_change,
                    directional_next_capture=directional_next_capture,
                    next_snapshot_markout=raw_next_mid_change,
                    next_snapshot_edge_capture=directional_next_capture,
                    mid_yes_2_steps=mid_2_steps,
                    raw_2step_mid_change=raw_2step_mid_change,
                    directional_2step_capture=directional_2step_capture,
                    markout_2_steps=raw_2step_mid_change,
                    max_favorable_move=max_favorable_move,
                    max_adverse_move=max_adverse_move,
                    eventual_settlement_yes=eventual_settlement,
                    raw_eventual_resolution_change=raw_eventual_resolution_change,
                    directional_eventual_capture=directional_eventual_capture,
                    eventual_resolution_markout=raw_eventual_resolution_change,
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
        calibration_groups[("match_phase", match_phase_label(quote.match_status))].append(markout)

    rows: list[FootballCalibrationRow] = []
    for (bucket_type, bucket_value), grouped_rows in sorted(calibration_groups.items()):
        raw_next = [row.raw_next_mid_change for row in grouped_rows]
        raw_2step = [row.raw_2step_mid_change for row in grouped_rows]
        directional_next = [row.directional_next_capture for row in grouped_rows]
        directional_2step = [row.directional_2step_capture for row in grouped_rows]
        directional_eventual = [row.directional_eventual_capture for row in grouped_rows]
        adverse_moves = [row.max_adverse_move for row in grouped_rows]
        positive_capture_rate = _positive_rate(directional_next)
        rows.append(
            FootballCalibrationRow(
                bucket_type=bucket_type,
                bucket_value=bucket_value,
                observations=len(grouped_rows),
                average_raw_next_mid_change=_average(raw_next),
                average_raw_2step_mid_change=_average(raw_2step),
                average_directional_next_capture=_average(directional_next),
                average_directional_2step_capture=_average(directional_2step),
                average_directional_eventual_capture=_average(directional_eventual),
                positive_capture_rate=positive_capture_rate,
                average_max_adverse_move=_average(adverse_moves),
                average_next_snapshot_markout=_average(raw_next),
                average_markout_2_steps=_average(raw_2step),
                sign_hit_rate=positive_capture_rate,
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
        "- `raw_next_mid_change`: next midpoint minus current midpoint.",
        "- `directional_next_capture`: the next midpoint move expressed in the chosen decision direction.",
        "- `raw_2step_mid_change`: midpoint change two frames forward versus the current midpoint.",
        "- `directional_2step_capture`: the 2-step midpoint move expressed in the chosen decision direction.",
        "- `raw_eventual_resolution_change`: final settlement minus the current midpoint.",
        "- `directional_eventual_capture`: final settlement move expressed in the chosen decision direction.",
        "- Legacy fields such as `next_snapshot_markout` and `eventual_resolution_markout` are preserved as aliases for the raw metrics.",
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
        f"- Average raw next-mid change: `{summary['average_next_snapshot_markout']}`",
        f"- Average directional next capture: `{summary['average_directional_next_capture']}`",
        f"- Positive capture rate: `{summary['positive_capture_rate']}`",
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
                f"- `{row.bucket_type}` `{row.bucket_value}`: n={row.observations}, avg_raw_next={row.average_raw_next_mid_change}, avg_dir_next={row.average_directional_next_capture}, hit_rate={row.positive_capture_rate}"
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
            "- Directional capture metrics are about quote-decision quality, not about simulated fill realism.",
            "- The sample is small, so calibration and markout statistics are illustrative rather than statistically strong.",
        ]
    )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _replay_summary(
    *,
    run_id: str,
    output_dir: Path,
    frames: tuple[FootballReplayFrame, ...],
    quote_rows: tuple[FootballReplayQuoteRow, ...],
    markout_rows: tuple[FootballMarkoutRow, ...],
    artifacts: dict[str, str],
    sample_mode: bool,
    config: FootballPricingConfig,
    config_name: str | None,
    config_description: str | None,
    config_path: str | None,
) -> dict[str, object]:
    quoteable_rows = [row for row in quote_rows if row.no_trade_reason is None]
    positive_edge_rows = [row for row in quote_rows if row.max_actionable_edge > 0.0]
    raw_next = [
        row.raw_next_mid_change
        for row in markout_rows
        if row.raw_next_mid_change is not None and row.decision_side is not FootballDecisionSide.NO_TRADE
    ]
    raw_2step = [
        row.raw_2step_mid_change
        for row in markout_rows
        if row.raw_2step_mid_change is not None and row.decision_side is not FootballDecisionSide.NO_TRADE
    ]
    directional_next = [row.directional_next_capture for row in markout_rows if row.directional_next_capture is not None]
    directional_2step = [row.directional_2step_capture for row in markout_rows if row.directional_2step_capture is not None]
    directional_eventual = [row.directional_eventual_capture for row in markout_rows if row.directional_eventual_capture is not None]
    positive_markouts = [value for value in raw_next if value > 0.0]
    negative_markouts = [value for value in raw_next if value < 0.0]
    mid_edge_rows = [abs(row.edge_vs_mid) for row in quote_rows if row.edge_vs_mid is not None]

    return {
        "run_id": run_id,
        "mode": "football-replay",
        "fixtures": len({frame.fixture.event_id for frame in frames}),
        "snapshots": len(frames),
        "priced_snapshots": len(quote_rows),
        "quoteable_snapshots": len(quoteable_rows),
        "positive_edge_snapshots": len(positive_edge_rows),
        "average_absolute_edge": round(sum(mid_edge_rows) / max(1, len(mid_edge_rows)), 6),
        "average_next_snapshot_markout": round(sum(raw_next) / len(raw_next), 6) if raw_next else 0.0,
        "average_markout_2_steps": round(sum(raw_2step) / len(raw_2step), 6) if raw_2step else 0.0,
        "average_directional_next_capture": round(sum(directional_next) / len(directional_next), 6) if directional_next else 0.0,
        "average_directional_2step_capture": round(sum(directional_2step) / len(directional_2step), 6) if directional_2step else 0.0,
        "average_directional_eventual_capture": round(sum(directional_eventual) / len(directional_eventual), 6) if directional_eventual else 0.0,
        "positive_capture_rate": round(sum(1 for value in directional_next if value > 0.0) / len(directional_next), 6) if directional_next else 0.0,
        "max_positive_markout": round(max(positive_markouts), 6) if positive_markouts else 0.0,
        "max_negative_markout": round(min(negative_markouts), 6) if negative_markouts else 0.0,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
        "sample_data_is_synthetic": sample_mode,
        "pricing_config_name": config_name,
        "pricing_config_description": config_description,
        "pricing_config_path": config_path,
        "pricing_config": serialize_football_pricing_config(config),
    }


def run_football_replay(
    input_path: str | Path,
    output_root: Path,
    run_id: str | None = None,
    sample_mode: bool = False,
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
    config_name: str | None = None,
    config_description: str | None = None,
    config_path: str | None = None,
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
    summary = _replay_summary(
        run_id=actual_run_id,
        output_dir=output_dir,
        frames=frames,
        quote_rows=quote_rows,
        markout_rows=markout_rows,
        artifacts=artifacts,
        sample_mode=sample_mode,
        config=config,
        config_name=config_name,
        config_description=config_description,
        config_path=config_path,
    )
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
