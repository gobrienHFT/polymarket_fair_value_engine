from __future__ import annotations

import json
from hashlib import sha256
from collections import Counter
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

from polymarket_fair_value_engine.analytics.fills import export_dataclasses, write_rows
from polymarket_fair_value_engine.analytics.reports import create_run_directory
from polymarket_fair_value_engine.execution_research.config import config_as_dict, with_overrides
from polymarket_fair_value_engine.execution_research.replay import load_clob_replay
from polymarket_fair_value_engine.execution_research.types import (
    AccountSnapshot,
    ClobSnapshot,
    DecisionRow,
    DecisionSide,
    ExecutionProfileConfig,
    ExecutionResearchConfig,
    ExecutionStyle,
    LifecycleEvent,
    LifecycleEventType,
    LifecycleStatus,
    MarketValidity,
    MarkoutRow,
    ProfileResult,
    ReplayFrame,
    ResearchFill,
    ResearchOrder,
    SimulationOutput,
)
from polymarket_fair_value_engine.types import BookLevel


ARTIFACT_FILENAMES = {
    "execution_replay_validity.csv": "execution_replay_validity_csv",
    "execution_decisions.csv": "execution_decisions_csv",
    "execution_orders.csv": "execution_orders_csv",
    "execution_lifecycle_events.csv": "execution_lifecycle_events_csv",
    "execution_fills.csv": "execution_fills_csv",
    "execution_markouts.csv": "execution_markouts_csv",
    "execution_account.csv": "execution_account_csv",
    "execution_profile_results.csv": "execution_profile_results_csv",
    "execution_experiment_matrix.csv": "execution_experiment_matrix_csv",
    "execution_report.md": "execution_report_md",
    "execution_casebook.md": "execution_casebook_md",
}


def _mean(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return fmean(materialized) if materialized else None


def _round(value: float | None, places: int = 6) -> float | None:
    return round(value, places) if value is not None else None


def _signed_side(side: DecisionSide) -> float:
    return 1.0 if side is DecisionSide.BUY_YES else -1.0


def _is_active(order: ResearchOrder) -> bool:
    return order.status in {
        LifecycleStatus.SUBMITTED,
        LifecycleStatus.ACKNOWLEDGED,
        LifecycleStatus.RESTING,
        LifecycleStatus.PARTIALLY_FILLED,
        LifecycleStatus.CANCEL_REQUESTED,
    }


class _Account:
    def __init__(self, starting_cash: float, starting_position: float = 0.0) -> None:
        self.starting_cash = starting_cash
        self.starting_equity = starting_cash + (starting_position * 0.5)
        self.cash = starting_cash
        self.position = starting_position
        self.average_cost = 0.5 if starting_position != 0.0 else 0.0
        self.realized_pnl = 0.0
        self.fees = 0.0

    def apply_fill(self, side: DecisionSide, price: float, size: float, fee: float) -> None:
        self.fees += fee
        if side is DecisionSide.BUY_YES:
            self.cash -= price * size + fee
            if self.position >= 0.0:
                new_position = self.position + size
                self.average_cost = ((self.average_cost * self.position) + (price * size) + fee) / new_position
                self.position = new_position
                return
            closing = min(size, -self.position)
            self.realized_pnl += (self.average_cost - price) * closing - fee * (closing / size)
            remainder = size - closing
            self.position += closing
            if remainder > 0.0:
                self.position = remainder
                self.average_cost = price + (fee * remainder / size) / remainder
            return

        self.cash += price * size - fee
        if self.position <= 0.0:
            new_position = self.position - size
            short_size = -new_position
            self.average_cost = ((self.average_cost * (-self.position)) + (price * size) + fee) / short_size
            self.position = new_position
            return
        closing = min(size, self.position)
        self.realized_pnl += (price - self.average_cost) * closing - fee * (closing / size)
        remainder = size - closing
        self.position -= closing
        if remainder > 0.0:
            self.position = -remainder
            self.average_cost = price + (fee * remainder / size) / remainder

    def unrealized_pnl(self, mark: float | None) -> float:
        if mark is None or self.position == 0.0:
            return 0.0
        if self.position > 0.0:
            return (mark - self.average_cost) * self.position
        return (self.average_cost - mark) * (-self.position)

    def total_pnl(self, mark: float | None) -> float:
        if mark is None:
            return self.cash - self.starting_equity
        return self.cash + (self.position * mark) - self.starting_equity


def _emit(
    events: list[LifecycleEvent],
    event_number: list[int],
    event_type: LifecycleEventType,
    timestamp: datetime,
    *,
    order: ResearchOrder | None,
    profile_name: str,
    style: ExecutionStyle,
    side: DecisionSide | None,
    price: float | None,
    size: float | None,
    detail: str,
    decision_id: str | None = None,
) -> None:
    event_number[0] += 1
    events.append(
        LifecycleEvent(
            event_id=f"event-{event_number[0]:06d}",
            event_type=event_type,
            timestamp=timestamp,
            order_id=order.order_id if order is not None else None,
            decision_id=decision_id if decision_id is not None else (order.decision_id if order is not None else None),
            profile_name=profile_name,
            style=style,
            side=side,
            price=price,
            size=size,
            detail=detail,
        )
    )


def _same_side_depth(snapshot: ClobSnapshot, side: DecisionSide, price: float) -> float:
    levels = snapshot.bids if side is DecisionSide.BUY_YES else snapshot.asks
    return sum(level.size for level in levels if abs(level.price - price) <= 1e-9)


def _opposing_level(snapshot: ClobSnapshot, side: DecisionSide) -> BookLevel | None:
    return snapshot.best_ask if side is DecisionSide.BUY_YES else snapshot.best_bid


def _decision_for(frame: ReplayFrame, style: ExecutionStyle, config: ExecutionResearchConfig) -> tuple[DecisionSide, float | None, float | None, str | None]:
    snapshot = frame.snapshot
    if snapshot.validity is not MarketValidity.VALID:
        reason = "invalid_market_state:" + ",".join(snapshot.validity_reasons)
        return DecisionSide.NO_TRADE, None, None, reason
    if frame.fair_yes is None or snapshot.mid is None or snapshot.best_bid is None or snapshot.best_ask is None:
        return DecisionSide.NO_TRADE, None, None, "missing_fair_or_book"

    fee_rate = config.fee_bps / 10000.0
    if frame.fair_yes >= snapshot.mid:
        price = snapshot.best_bid.price if style is ExecutionStyle.PASSIVE else snapshot.best_ask.price
        edge = frame.fair_yes - price - (price * fee_rate)
        if edge >= config.min_edge:
            return DecisionSide.BUY_YES, price, edge, None
        return DecisionSide.NO_TRADE, price, edge, "edge_below_threshold"

    price = snapshot.best_ask.price if style is ExecutionStyle.PASSIVE else snapshot.best_bid.price
    edge = price - frame.fair_yes - (price * fee_rate)
    if edge >= config.min_edge:
        return DecisionSide.SELL_YES, price, edge, None
    return DecisionSide.NO_TRADE, price, edge, "edge_below_threshold"


def _risk_check(account: _Account, side: DecisionSide, price: float, size: float, config: ExecutionResearchConfig) -> str:
    if price * size > config.max_order_notional:
        return "max_order_notional"
    signed_position = account.position + (_signed_side(side) * size)
    if abs(signed_position) > config.max_position:
        return "max_position"
    return "approved"


def _fill_order(
    order: ResearchOrder,
    frame: ReplayFrame,
    profile: ExecutionProfileConfig,
    config: ExecutionResearchConfig,
    account: _Account,
    fills: list[ResearchFill],
    events: list[LifecycleEvent],
    event_number: list[int],
    fill_number: list[int],
    *,
    race: bool,
) -> bool:
    snapshot = frame.snapshot
    if snapshot.timestamp is None or snapshot.validity is not MarketValidity.VALID:
        return False
    opposing = _opposing_level(snapshot, order.side)
    if opposing is None:
        return False

    capacity = 0.0
    fill_reason = ""
    if order.style is ExecutionStyle.AGGRESSIVE:
        if (order.side is DecisionSide.BUY_YES and opposing.price > order.price) or (order.side is DecisionSide.SELL_YES and opposing.price < order.price):
            return False
        capacity = opposing.size * profile.aggressive_fill_fraction
        fill_reason = "aggressive_cross"
        fill_price = opposing.price
    else:
        current_depth = _same_side_depth(snapshot, order.side, order.price)
        depletion = max(0.0, order.last_queue_depth - current_depth)
        crossed_volume = opposing.size if (
            (order.side is DecisionSide.BUY_YES and opposing.price <= order.price)
            or (order.side is DecisionSide.SELL_YES and opposing.price >= order.price)
        ) else 0.0
        capacity = max(max(0.0, depletion - order.queue_ahead), crossed_volume) * profile.passive_fill_fraction
        order.last_queue_depth = current_depth
        fill_reason = "visible_depth_depletion" if depletion > 0.0 else "touch_or_cross"
        fill_price = order.price
    fill_size = min(order.remaining_size, capacity)
    if fill_size <= 0.0:
        return False

    fee = fill_price * fill_size * config.fee_bps / 10000.0
    if race:
        _emit(
            events,
            event_number,
            LifecycleEventType.CANCEL_FILL_RACE,
            snapshot.timestamp,
            order=order,
            profile_name=order.profile_name,
            style=order.style,
            side=order.side,
            price=fill_price,
            size=fill_size,
            detail="fill occurred before cancel acknowledgement",
        )
    fill_number[0] += 1
    fills.append(
        ResearchFill(
            fill_id=f"fill-{fill_number[0]:06d}",
            order_id=order.order_id,
            decision_id=order.decision_id,
            profile_name=order.profile_name,
            style=order.style,
            side=order.side,
            timestamp=snapshot.timestamp,
            price=fill_price,
            size=fill_size,
            fee=fee,
            fair_yes=order.fair_yes,
            mid_yes=order.mid_yes,
            spread=snapshot.spread or 0.0,
            depth_imbalance=snapshot.depth_imbalance,
            microprice=snapshot.microprice,
            fill_reason=fill_reason,
        )
    )
    account.apply_fill(order.side, fill_price, fill_size, fee)
    order.remaining_size -= fill_size
    order.filled_size += fill_size
    order.fees_paid += fee
    order.last_update_timestamp = snapshot.timestamp
    if order.remaining_size <= 1e-9:
        order.remaining_size = 0.0
        order.status = LifecycleStatus.FILLED
        event_type = LifecycleEventType.FILL
    else:
        order.status = LifecycleStatus.CANCEL_REQUESTED if order.cancel_request_timestamp is not None else LifecycleStatus.PARTIALLY_FILLED
        event_type = LifecycleEventType.PARTIAL_FILL
    _emit(
        events,
        event_number,
        event_type,
        snapshot.timestamp,
        order=order,
        profile_name=order.profile_name,
        style=order.style,
        side=order.side,
        price=fill_price,
        size=fill_size,
        detail=fill_reason,
    )
    return True


def _advance_order(
    order: ResearchOrder,
    frame: ReplayFrame,
    profile: ExecutionProfileConfig,
    config: ExecutionResearchConfig,
    account: _Account,
    fills: list[ResearchFill],
    events: list[LifecycleEvent],
    event_number: list[int],
    fill_number: list[int],
) -> None:
    timestamp = frame.snapshot.timestamp
    if timestamp is None:
        return
    if order.status is LifecycleStatus.SUBMITTED and timestamp >= order.acknowledge_timestamp:
        order.status = LifecycleStatus.ACKNOWLEDGED
        order.first_rest_timestamp = order.acknowledge_timestamp
        order.last_queue_depth = _same_side_depth(frame.snapshot, order.side, order.price)
        order.queue_ahead = order.last_queue_depth * profile.queue_ahead_fraction
        _emit(events, event_number, LifecycleEventType.ACKNOWLEDGE, order.acknowledge_timestamp, order=order, profile_name=order.profile_name, style=order.style, side=order.side, price=order.price, size=order.remaining_size, detail="acknowledged")
        _emit(events, event_number, LifecycleEventType.REST, order.acknowledge_timestamp, order=order, profile_name=order.profile_name, style=order.style, side=order.side, price=order.price, size=order.remaining_size, detail="resting or eligible for aggressive execution")
        order.status = LifecycleStatus.RESTING

    race = order.status is LifecycleStatus.CANCEL_REQUESTED and order.cancel_acknowledge_timestamp is not None and timestamp <= order.cancel_acknowledge_timestamp
    if _is_active(order) and frame.snapshot.validity is MarketValidity.VALID:
        _fill_order(order, frame, profile, config, account, fills, events, event_number, fill_number, race=race)
    if order.status is LifecycleStatus.FILLED:
        return
    if order.status is LifecycleStatus.CANCEL_REQUESTED and order.cancel_acknowledge_timestamp is not None and timestamp >= order.cancel_acknowledge_timestamp:
        order.status = LifecycleStatus.CANCELLED
        order.last_update_timestamp = timestamp
        _emit(events, event_number, LifecycleEventType.CANCEL_ACKNOWLEDGE, order.cancel_acknowledge_timestamp, order=order, profile_name=order.profile_name, style=order.style, side=order.side, price=order.price, size=order.remaining_size, detail="cancel acknowledged")
        return
    if _is_active(order) and timestamp >= order.expiry_timestamp:
        order.status = LifecycleStatus.EXPIRED
        order.last_update_timestamp = timestamp
        _emit(events, event_number, LifecycleEventType.EXPIRE, order.expiry_timestamp, order=order, profile_name=order.profile_name, style=order.style, side=order.side, price=order.price, size=order.remaining_size, detail="order expiry reached")


def _request_cancel(order: ResearchOrder, timestamp: datetime, config: ExecutionResearchConfig, events: list[LifecycleEvent], event_number: list[int]) -> None:
    if not _is_active(order) or order.cancel_request_timestamp is not None:
        return
    order.status = LifecycleStatus.CANCEL_REQUESTED
    order.cancel_request_timestamp = timestamp
    order.cancel_acknowledge_timestamp = timestamp + timedelta(milliseconds=config.cancel_latency_ms)
    order.last_update_timestamp = timestamp
    _emit(events, event_number, LifecycleEventType.CANCEL_REQUEST, timestamp, order=order, profile_name=order.profile_name, style=order.style, side=order.side, price=order.price, size=order.remaining_size, detail="decision changed or data became invalid")


def _simulate(
    frames: list[ReplayFrame],
    config: ExecutionResearchConfig,
    profile: ExecutionProfileConfig,
    style: ExecutionStyle,
    *,
    initial_position: float = 0.0,
) -> SimulationOutput:
    decisions: list[DecisionRow] = []
    orders: list[ResearchOrder] = []
    events: list[LifecycleEvent] = []
    fills: list[ResearchFill] = []
    account_snapshots: list[AccountSnapshot] = []
    account = _Account(config.starting_cash, starting_position=initial_position)
    current_order: ResearchOrder | None = None
    event_number = [0]
    order_number = [0]
    fill_number = [0]

    for frame_index, frame in enumerate(frames):
        snapshot = frame.snapshot
        if current_order is not None:
            _advance_order(current_order, frame, profile, config, account, fills, events, event_number, fill_number)
            if current_order.status in {LifecycleStatus.FILLED, LifecycleStatus.CANCELLED, LifecycleStatus.REJECTED, LifecycleStatus.EXPIRED}:
                current_order = None

        decision_id = f"{profile.name}-{style.value}-decision-{frame_index + 1:04d}"
        side, price, edge, no_trade_reason = _decision_for(frame, style, config)
        _emit(
            events,
            event_number,
            LifecycleEventType.DECISION,
            snapshot.timestamp or datetime(1970, 1, 1, tzinfo=timezone.utc),
            order=None,
            profile_name=profile.name,
            style=style,
            side=side,
            price=price,
            size=config.order_size if side is not DecisionSide.NO_TRADE else None,
            detail=no_trade_reason or "actionable fair-value edge",
            decision_id=decision_id,
        )

        risk_result = "not_evaluated"
        order_id: str | None = None
        if current_order is not None and _is_active(current_order):
            if side is DecisionSide.NO_TRADE or side is not current_order.side or price is None or abs(price - current_order.price) > 1e-9:
                if snapshot.timestamp is not None:
                    _request_cancel(current_order, snapshot.timestamp, config, events, event_number)
                no_trade_reason = no_trade_reason or "cancel_pending"
                risk_result = "cancel_pending"
            else:
                risk_result = "existing_order_maintained"
            order_id = current_order.order_id
        elif side is not DecisionSide.NO_TRADE and price is not None and snapshot.timestamp is not None:
            risk_result = _risk_check(account, side, price, config.order_size, config)
            _emit(events, event_number, LifecycleEventType.RISK_CHECK, snapshot.timestamp, order=None, profile_name=profile.name, style=style, side=side, price=price, size=config.order_size, detail=risk_result, decision_id=decision_id)
            if risk_result == "approved":
                order_number[0] += 1
                order_id = f"{profile.name}-{style.value}-order-{order_number[0]:04d}"
                submit_timestamp = snapshot.timestamp + timedelta(milliseconds=config.submit_latency_ms)
                acknowledge_timestamp = submit_timestamp + timedelta(milliseconds=config.ack_latency_ms)
                current_order = ResearchOrder(
                    order_id=order_id,
                    decision_id=decision_id,
                    market_id=snapshot.market_id,
                    profile_name=profile.name,
                    style=style,
                    side=side,
                    price=price,
                    size=config.order_size,
                    remaining_size=config.order_size,
                    status=LifecycleStatus.SUBMITTED,
                    decision_timestamp=snapshot.timestamp,
                    submit_timestamp=submit_timestamp,
                    acknowledge_timestamp=acknowledge_timestamp,
                    expiry_timestamp=snapshot.timestamp + timedelta(seconds=config.order_expiry_seconds),
                    fair_yes=frame.fair_yes or 0.0,
                    mid_yes=snapshot.mid or price,
                    edge_after_fee=edge or 0.0,
                )
                orders.append(current_order)
                _emit(events, event_number, LifecycleEventType.SUBMIT, submit_timestamp, order=current_order, profile_name=profile.name, style=style, side=side, price=price, size=config.order_size, detail="order submitted")
            else:
                _emit(events, event_number, LifecycleEventType.REJECT, snapshot.timestamp, order=None, profile_name=profile.name, style=style, side=side, price=price, size=config.order_size, detail=risk_result, decision_id=decision_id)

        decisions.append(
            DecisionRow(
                decision_id=decision_id,
                frame_row=snapshot.source_row,
                timestamp=snapshot.timestamp,
                market_id=snapshot.market_id,
                profile_name=profile.name,
                style=style,
                data_validity=snapshot.validity,
                validity_reasons=snapshot.validity_reasons,
                fair_yes=frame.fair_yes,
                market_mid_yes=snapshot.mid,
                best_bid_yes=snapshot.best_bid.price if snapshot.best_bid else None,
                best_ask_yes=snapshot.best_ask.price if snapshot.best_ask else None,
                spread=snapshot.spread,
                bid_depth=snapshot.bid_depth,
                ask_depth=snapshot.ask_depth,
                depth_imbalance=snapshot.depth_imbalance,
                microprice=snapshot.microprice,
                decision=side,
                decision_edge_after_fee=edge,
                decision_price=price,
                risk_result=risk_result,
                no_trade_reason=no_trade_reason,
                order_id=order_id,
            )
        )
        if snapshot.timestamp is not None:
            mark = snapshot.mid if snapshot.validity is MarketValidity.VALID else None
            account_snapshots.append(
                AccountSnapshot(
                    timestamp=snapshot.timestamp,
                    profile_name=profile.name,
                    style=style,
                    market_id=snapshot.market_id,
                    position_yes=account.position,
                    cash=account.cash,
                    realized_pnl=account.realized_pnl,
                    unrealized_pnl=account.unrealized_pnl(mark),
                    total_pnl=account.total_pnl(mark),
                    mark_yes=mark,
                )
            )

    last_timestamp = next((frame.snapshot.timestamp for frame in reversed(frames) if frame.snapshot.timestamp is not None), None)
    if last_timestamp is not None and current_order is not None and _is_active(current_order):
        if current_order.cancel_request_timestamp is not None and current_order.cancel_acknowledge_timestamp is not None:
            final_timestamp = max(last_timestamp, current_order.cancel_acknowledge_timestamp)
            current_order.status = LifecycleStatus.CANCELLED
            current_order.last_update_timestamp = final_timestamp
            _emit(events, event_number, LifecycleEventType.CANCEL_ACKNOWLEDGE, final_timestamp, order=current_order, profile_name=profile.name, style=style, side=current_order.side, price=current_order.price, size=current_order.remaining_size, detail="cancel acknowledged after replay")
        else:
            final_timestamp = max(last_timestamp, current_order.expiry_timestamp)
            current_order.status = LifecycleStatus.EXPIRED
            current_order.last_update_timestamp = final_timestamp
            _emit(events, event_number, LifecycleEventType.EXPIRE, final_timestamp, order=current_order, profile_name=profile.name, style=style, side=current_order.side, price=current_order.price, size=current_order.remaining_size, detail="replay ended before a fill")

    markout_rows = _build_markouts(frames, fills, config.markout_horizons)
    valid_decisions = [row for row in decisions if row.data_validity is MarketValidity.VALID]
    invalid_reason_counts: Counter[str] = Counter(reason for row in decisions for reason in row.validity_reasons)
    submitted_orders = len(orders)
    acknowledged_orders = sum(1 for order in orders if order.first_rest_timestamp is not None)
    filled_orders = sum(1 for order in orders if order.status is LifecycleStatus.FILLED)
    partial_fills = sum(1 for fill in fills if any(order.order_id == fill.order_id and order.remaining_size > 0.0 for order in orders))
    total_order_size = sum(order.size for order in orders)
    filled_size = sum(fill.size for fill in fills)
    resting_durations = [
        (order.last_update_timestamp - order.first_rest_timestamp).total_seconds() * 1000.0
        for order in orders
        if order.first_rest_timestamp is not None and order.last_update_timestamp is not None
    ]
    spread_capture = [
        (fill.mid_yes - fill.price) if fill.side is DecisionSide.BUY_YES else (fill.price - fill.mid_yes)
        for fill in fills
    ]
    latest_mark = next((snapshot.mark_yes for snapshot in reversed(account_snapshots) if snapshot.mark_yes is not None), None)
    final_snapshot = account_snapshots[-1] if account_snapshots else None
    result = ProfileResult(
        profile_name=profile.name,
        profile_description=profile.description,
        style=style,
        decisions=len(decisions),
        valid_frames=len(valid_decisions),
        invalid_frames=len(decisions) - len(valid_decisions),
        quoteable_decisions=sum(1 for row in decisions if row.risk_result in {"approved", "existing_order_maintained"}),
        no_trade_decisions=sum(1 for row in decisions if row.decision is DecisionSide.NO_TRADE),
        risk_rejections=sum(1 for row in decisions if row.risk_result.startswith("max_")),
        orders_submitted=submitted_orders,
        orders_acknowledged=acknowledged_orders,
        orders_filled=filled_orders,
        partial_fills=partial_fills,
        total_order_size=total_order_size,
        filled_size=filled_size,
        fill_rate=(filled_size / total_order_size) if total_order_size else 0.0,
        cancelled_orders=sum(1 for order in orders if order.status is LifecycleStatus.CANCELLED),
        expired_orders=sum(1 for order in orders if order.status is LifecycleStatus.EXPIRED),
        cancel_fill_races=sum(1 for event in events if event.event_type is LifecycleEventType.CANCEL_FILL_RACE),
        average_time_resting_ms=_mean(resting_durations),
        average_spread_paid_or_captured=_mean(spread_capture),
        total_fees=sum(fill.fee for fill in fills),
        final_position_yes=account.position,
        realized_pnl=account.realized_pnl,
        unrealized_pnl=account.unrealized_pnl(latest_mark),
        total_pnl=account.total_pnl(latest_mark),
        average_next_signed_markout=_mean(row.next_snapshot_signed_markout for row in markout_rows if row.next_snapshot_signed_markout is not None),
        average_signed_markout_by_horizon={
            str(horizon): _mean(row.horizon_markouts.get(str(horizon)) for row in markout_rows if row.horizon_markouts.get(str(horizon)) is not None)
            for horizon in config.markout_horizons
        },
        average_spread=_mean(row.spread for row in valid_decisions if row.spread is not None),
        average_depth_imbalance=_mean(row.depth_imbalance for row in valid_decisions if row.depth_imbalance is not None),
        average_microprice_delta=_mean((row.microprice - row.market_mid_yes) for row in valid_decisions if row.microprice is not None and row.market_mid_yes is not None),
        invalid_reason_counts=dict(sorted(invalid_reason_counts.items())),
        notes="Public snapshot replay uses visible-depth depletion as a queue proxy; it does not reconstruct participant-level FIFO.",
    )
    return SimulationOutput(result=result, decisions=decisions, orders=orders, events=events, fills=fills, markouts=markout_rows, account_snapshots=account_snapshots)


def _build_markouts(frames: list[ReplayFrame], fills: list[ResearchFill], horizons: tuple[int, ...]) -> list[MarkoutRow]:
    valid_frames = [(index, frame) for index, frame in enumerate(frames) if frame.snapshot.validity is MarketValidity.VALID and frame.snapshot.timestamp is not None and frame.snapshot.mid is not None]
    rows: list[MarkoutRow] = []
    for fill in fills:
        future = [frame for _, frame in valid_frames if frame.snapshot.timestamp is not None and frame.snapshot.timestamp > fill.timestamp]
        next_mid = future[0].snapshot.mid if future else None
        sign = _signed_side(fill.side)
        horizon_markouts: dict[str, float | None] = {}
        for horizon in horizons:
            future_frame = future[horizon - 1] if len(future) >= horizon else None
            horizon_markouts[str(horizon)] = sign * (future_frame.snapshot.mid - fill.price) if future_frame is not None and future_frame.snapshot.mid is not None else None
        settlement = next((frame.settlement_yes for frame in frames if frame.snapshot.timestamp is not None and frame.snapshot.timestamp >= fill.timestamp and frame.settlement_yes is not None), None)
        eventual_signed = sign * ((1.0 if settlement else 0.0) - fill.price) if settlement is not None else None
        rows.append(
            MarkoutRow(
                fill_id=fill.fill_id,
                order_id=fill.order_id,
                profile_name=fill.profile_name,
                style=fill.style,
                side=fill.side,
                fill_timestamp=fill.timestamp,
                fill_price=fill.price,
                fee=fill.fee,
                current_mid_yes=fill.mid_yes,
                fair_yes=fill.fair_yes,
                spread_paid_or_captured=(fill.mid_yes - fill.price) if fill.side is DecisionSide.BUY_YES else (fill.price - fill.mid_yes),
                next_snapshot_mid_yes=next_mid,
                next_snapshot_signed_markout=sign * (next_mid - fill.price) if next_mid is not None else None,
                horizon_markouts=horizon_markouts,
                eventual_settlement_yes=settlement,
                eventual_signed_markout=eventual_signed,
            )
        )
    return rows


def _frame_with_fair_offset(frame: ReplayFrame, offset: float) -> ReplayFrame:
    fair = None if frame.fair_yes is None else max(0.01, min(0.99, frame.fair_yes + offset))
    return replace(frame, fair_yes=fair)


def _frame_with_spread(frame: ReplayFrame, spread: float) -> ReplayFrame:
    snapshot = frame.snapshot
    if snapshot.mid is None or not snapshot.bids or not snapshot.asks:
        return frame
    half = max(0.001, spread / 2.0)
    bid = max(0.001, snapshot.mid - half)
    ask = min(0.999, snapshot.mid + half)
    if bid >= ask:
        return frame
    bids = (BookLevel(price=bid, size=snapshot.bids[0].size),) + snapshot.bids[1:]
    asks = (BookLevel(price=ask, size=snapshot.asks[0].size),) + snapshot.asks[1:]
    return replace(frame, snapshot=replace(snapshot, bids=bids, asks=asks))


def _frame_with_imbalance(frame: ReplayFrame, imbalance: float) -> ReplayFrame:
    snapshot = frame.snapshot
    if not snapshot.bids or not snapshot.asks:
        return frame
    bounded = max(-0.95, min(0.95, imbalance))
    total = snapshot.bid_depth + snapshot.ask_depth
    bid_size = max(0.1, total * (1.0 + bounded) / 2.0)
    ask_size = max(0.1, total - bid_size)
    bids = (BookLevel(price=snapshot.bids[0].price, size=bid_size),) + snapshot.bids[1:]
    asks = (BookLevel(price=snapshot.asks[0].price, size=ask_size),) + snapshot.asks[1:]
    return replace(frame, snapshot=replace(snapshot, bids=bids, asks=asks))


def _result_row(result: ProfileResult, experiment_id: str, dimension: str, value: Any) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "dimension": dimension,
        "value": value,
        "profile_name": result.profile_name,
        "style": result.style.value,
        "quoteable_decisions": result.quoteable_decisions,
        "orders_submitted": result.orders_submitted,
        "filled_size": _round(result.filled_size),
        "fill_rate": _round(result.fill_rate),
        "average_spread_paid_or_captured": _round(result.average_spread_paid_or_captured),
        "average_next_signed_markout": _round(result.average_next_signed_markout),
        "total_pnl": _round(result.total_pnl),
        "fees": _round(result.total_fees),
        "final_position_yes": _round(result.final_position_yes),
        "assessment": "",
    }


def _run_experiment_matrix(frames: list[ReplayFrame], config: ExecutionResearchConfig) -> list[dict[str, Any]]:
    baseline_profile = config.profiles[1] if len(config.profiles) > 1 else config.profiles[0]
    baseline = _simulate(frames, config, baseline_profile, ExecutionStyle.PASSIVE)
    rows = [_result_row(baseline.result, "baseline", "baseline", "default")]
    cases: list[tuple[str, Any, list[ReplayFrame], ExecutionResearchConfig, ExecutionProfileConfig, float]] = []
    for value in config.edge_offsets:
        cases.append(("fair_value_edge_offset", value, [_frame_with_fair_offset(frame, value) for frame in frames], config, baseline_profile, 0.0))
    for value in config.spread_values:
        cases.append(("spread", value, [_frame_with_spread(frame, value) for frame in frames], config, baseline_profile, 0.0))
    for value in config.imbalance_values:
        cases.append(("book_imbalance", value, [_frame_with_imbalance(frame, value) for frame in frames], config, baseline_profile, 0.0))
    for value in config.latency_values_ms:
        cases.append(("submit_latency_ms", value, frames, with_overrides(config, submit_latency_ms=value), baseline_profile, 0.0))
    for profile in config.profiles:
        cases.append(("execution_profile", profile.name, frames, config, profile, 0.0))
    for value in config.inventory_values:
        cases.append(("initial_inventory_yes", value, frames, config, baseline_profile, value))
    for value in config.fee_values_bps:
        cases.append(("fee_bps", value, frames, with_overrides(config, fee_bps=value), baseline_profile, 0.0))
    for index, (dimension, value, case_frames, case_config, profile, inventory) in enumerate(cases, start=1):
        result = _simulate(case_frames, case_config, profile, ExecutionStyle.PASSIVE, initial_position=inventory)
        rows.append(_result_row(result.result, f"experiment-{index:03d}", dimension, value))
    baseline_row = rows[0]
    for row in rows:
        if row["dimension"] == "baseline":
            row["assessment"] = "baseline"
            continue
        markout_delta = abs((row["average_next_signed_markout"] or 0.0) - (baseline_row["average_next_signed_markout"] or 0.0))
        fill_rate_delta = abs((row["fill_rate"] or 0.0) - (baseline_row["fill_rate"] or 0.0))
        pnl_delta = abs((row["total_pnl"] or 0.0) - (baseline_row["total_pnl"] or 0.0))
        row["assessment"] = "assumption_sensitive" if markout_delta >= 0.01 or fill_rate_delta >= 0.10 or pnl_delta >= 0.50 else "stable_on_this_sample"
    return rows


def _validity_rows(frames: list[ReplayFrame]) -> list[dict[str, Any]]:
    return [
        {
            "source_row": frame.snapshot.source_row,
            "market_id": frame.snapshot.market_id,
            "timestamp_utc": frame.snapshot.timestamp.isoformat() if frame.snapshot.timestamp else None,
            "book_timestamp_utc": frame.snapshot.source_timestamp.isoformat() if frame.snapshot.source_timestamp else None,
            "sequence": frame.snapshot.sequence,
            "validity": frame.snapshot.validity.value,
            "validity_reasons": "|".join(frame.snapshot.validity_reasons),
            "best_bid_yes": frame.snapshot.best_bid.price if frame.snapshot.best_bid else None,
            "best_ask_yes": frame.snapshot.best_ask.price if frame.snapshot.best_ask else None,
            "spread": frame.snapshot.spread,
            "bid_depth": frame.snapshot.bid_depth,
            "ask_depth": frame.snapshot.ask_depth,
            "depth_imbalance": frame.snapshot.depth_imbalance,
            "microprice": frame.snapshot.microprice,
            "fair_yes": frame.fair_yes,
            "settlement_yes": frame.settlement_yes,
        }
        for frame in frames
    ]


def _profile_rows(outputs: list[SimulationOutput]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for output in outputs:
        result = asdict(output.result)
        result["style"] = output.result.style.value
        result["average_signed_markout_by_horizon"] = json.dumps(result["average_signed_markout_by_horizon"], sort_keys=True)
        result["invalid_reason_counts"] = json.dumps(result["invalid_reason_counts"], sort_keys=True)
        rows.append(result)
    return rows


def _report_markout_text(result: ProfileResult) -> str:
    next_capture = "n/a" if result.average_next_signed_markout is None else f"{result.average_next_signed_markout:.4f}"
    pnl = f"{result.total_pnl:.4f}"
    return f"{result.profile_name}/{result.style.value}: {result.filled_size:.2f} filled contracts, {result.fill_rate:.1%} fill rate, next signed markout {next_capture}, total marked PnL {pnl}."


def _render_report(outputs: list[SimulationOutput], matrix_rows: list[dict[str, Any]], frames: list[ReplayFrame], config: ExecutionResearchConfig) -> str:
    lines = [
        "# Binary Execution Research Report",
        "",
        "## Overview",
        "",
        "This deterministic replay separates fair-value direction from execution quality. Each scenario uses the same committed YES-book snapshots, lifecycle latencies, risk checks, and accounting rules; only execution style or named sensitivity assumptions change.",
        "",
        f"- Frames: {len(frames)} ({sum(frame.snapshot.validity is MarketValidity.VALID for frame in frames)} valid, {sum(frame.snapshot.validity is not MarketValidity.VALID for frame in frames)} fail-closed)",
        f"- Code version: `{config.code_version}`",
        "- Queue caveat: visible-depth depletion is a bounded proxy, not participant-level historical FIFO",
        "",
        "## Profile Comparison",
        "",
        "| Profile | Style | Filled | Fill rate | Avg spread capture | Next signed markout | Total marked PnL |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for output in outputs:
        result = output.result
        lines.append(
            f"| {result.profile_name} | {result.style.value} | {result.filled_size:.2f} | {result.fill_rate:.1%} | {result.average_spread_paid_or_captured if result.average_spread_paid_or_captured is not None else 0.0:.4f} | {result.average_next_signed_markout if result.average_next_signed_markout is not None else 0.0:.4f} | {result.total_pnl:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Lifecycle And Validity",
            "",
            "Orders record decision, submit, acknowledgement, resting, fill, cancel request, cancel acknowledgement, expiry, rejection, and cancel/fill race events. Invalid, stale, crossed, malformed, expired, or discontinuous frames never create a new execution order.",
            "",
            "## Sensitivity Matrix",
            "",
            "The matrix is one-factor-at-a-time around a fixed baseline. It varies fair-value edge, spread, depth imbalance, submit latency, execution profile, initial inventory, and fees. It is a tooling and assumption-sensitivity exercise, not a profitability validation.",
            "",
            "| Dimension | Value | Style | Fill rate | Next signed markout | Total marked PnL | Assessment |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in matrix_rows[: min(len(matrix_rows), 16)]:
        lines.append(f"| {row['dimension']} | {row['value']} | {row['style']} | {row['fill_rate'] if row['fill_rate'] is not None else 0.0} | {row['average_next_signed_markout'] if row['average_next_signed_markout'] is not None else 0.0} | {row['total_pnl'] if row['total_pnl'] is not None else 0.0} | {row['assessment']} |")
    lines.extend(
        [
            "",
            "## Claims And Non-Claims",
            "",
            "- Claims supported by this artifact: fair-value direction can be evaluated separately from spread cost, visible depth, latency, fee drag, inventory, fills, and markouts under explicit assumptions.",
            "- Non-claims: no live football execution, no hidden liquidity, no participant-level FIFO reconstruction, no historical fill truth from public snapshots, no latency advantage, and no production alpha claim.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_casebook(output: SimulationOutput, frames: list[ReplayFrame]) -> str:
    result = output.result
    first_fill = output.fills[0] if output.fills else None
    first_markout = output.markouts[0] if output.markouts else None
    invalid = next((frame for frame in frames if frame.snapshot.validity is not MarketValidity.VALID), None)
    lines = [
        "# Binary Execution Casebook",
        "",
        "This casebook is generated from the committed execution replay. It follows one baseline passive scenario from raw book state through fair value, risk, lifecycle, fill/no-fill, markout, and accounting.",
        "",
        "## Case 1: Actionable Edge",
        "",
    ]
    if first_fill is None:
        lines.append("The selected baseline scenario produced no fill; the lifecycle artifacts still show the submitted, resting, expiry, and cancellation path.")
    else:
        lines.extend(
            [
                f"- Decision: `{first_fill.side.value}` under `{first_fill.profile_name}/{first_fill.style.value}`.",
                f"- Fair YES: `{first_fill.fair_yes:.4f}`; decision midpoint: `{first_fill.mid_yes:.4f}`; fill price: `{first_fill.price:.4f}`; size: `{first_fill.size:.2f}`.",
                f"- Risk: approved within configured position and notional limits; order `{first_fill.order_id}` is fully or partially audited in `execution_lifecycle_events.csv`.",
                f"- Execution: `{first_fill.fill_reason}` with fee `{first_fill.fee:.6f}` and spread capture `{(first_fill.mid_yes - first_fill.price) if first_fill.side is DecisionSide.BUY_YES else (first_fill.price - first_fill.mid_yes):.6f}`.",
            ]
        )
        if first_markout is not None:
            lines.append(f"- Evaluation: next valid midpoint `{first_markout.next_snapshot_mid_yes}` and signed next markout `{first_markout.next_snapshot_signed_markout}`.")
    lines.extend(["", "## Case 2: Fail-Closed State", ""])
    if invalid is None:
        lines.append("The bundled sample contains no invalid state; malformed, crossed, stale, and discontinuous fixtures are covered by the replay validity tests.")
    else:
        lines.append(f"- Source row `{invalid.snapshot.source_row}` is classified `{invalid.snapshot.validity.value}` with reasons `{', '.join(invalid.snapshot.validity_reasons)}`. It produces a `NO_TRADE` decision and cannot submit an order.")
    lines.extend(
        [
            "",
            "## Baseline Outcome",
            "",
            f"The selected scenario finished with `{result.filled_size:.2f}` filled contracts, `{result.fill_rate:.1%}` fill rate, `{result.total_fees:.6f}` fees, position `{result.final_position_yes:.2f}`, and marked PnL `{result.total_pnl:.6f}`. These are sample-path accounting outputs, not a production estimate.",
            "",
            "## Read With",
            "",
            "- `execution_replay_validity.csv` for input-state classification",
            "- `execution_decisions.csv` for fair value, edge, microstructure, and risk decisions",
            "- `execution_lifecycle_events.csv` for every order transition",
            "- `execution_fills.csv`, `execution_markouts.csv`, and `execution_account.csv` for post-trade evaluation",
            "",
        ]
    )
    return "\n".join(lines)


def _write_artifact(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def run_execution_research(
    input_path: str | Path,
    output_root: Path,
    config: ExecutionResearchConfig,
    *,
    config_path: str | Path,
    config_hash: str,
    run_id: str | None = None,
) -> tuple[str, Path, dict[str, Any]]:
    input_file = Path(input_path)
    input_hash = sha256(input_file.read_bytes()).hexdigest()
    frames = load_clob_replay(input_file, config)
    actual_run_id, output_dir = create_run_directory(output_root, run_id=run_id)
    outputs = [
        _simulate(frames, config, profile, style)
        for profile in config.profiles
        for style in (ExecutionStyle.PASSIVE, ExecutionStyle.AGGRESSIVE)
    ]
    matrix_rows = _run_experiment_matrix(frames, config)
    validity_rows = _validity_rows(frames)
    base_output = next(output for output in outputs if output.result.profile_name == (config.profiles[1].name if len(config.profiles) > 1 else config.profiles[0].name) and output.result.style is ExecutionStyle.PASSIVE)
    report = _render_report(outputs, matrix_rows, frames, config)
    casebook = _render_casebook(base_output, frames)

    export_dataclasses(output_dir / "execution_decisions.csv", [asdict(row) for output in outputs for row in output.decisions])
    export_dataclasses(output_dir / "execution_orders.csv", [order for output in outputs for order in output.orders])
    export_dataclasses(output_dir / "execution_lifecycle_events.csv", [event for output in outputs for event in output.events])
    export_dataclasses(output_dir / "execution_fills.csv", [fill for output in outputs for fill in output.fills])
    export_dataclasses(output_dir / "execution_markouts.csv", [markout for output in outputs for markout in output.markouts])
    export_dataclasses(output_dir / "execution_account.csv", [snapshot for output in outputs for snapshot in output.account_snapshots])
    write_rows(output_dir / "execution_replay_validity.csv", validity_rows)
    write_rows(output_dir / "execution_profile_results.csv", _profile_rows(outputs))
    write_rows(output_dir / "execution_experiment_matrix.csv", matrix_rows)
    _write_artifact(output_dir / "execution_report.md", report)
    _write_artifact(output_dir / "execution_casebook.md", casebook)

    validity_counts = Counter(frame.snapshot.validity.value for frame in frames)
    summary: dict[str, Any] = {
        "run_id": actual_run_id,
        "mode": "execution-research",
        "code_version": config.code_version,
        "input_path": str(input_file),
        "input_sha256": input_hash,
        "config_path": str(config_path),
        "config_sha256": config_hash,
        "frames": len(frames),
        "valid_frames": validity_counts.get(MarketValidity.VALID.value, 0),
        "invalid_frames": len(frames) - validity_counts.get(MarketValidity.VALID.value, 0),
        "validity_counts": dict(sorted(validity_counts.items())),
        "profiles": [profile.name for profile in config.profiles],
        "styles": [style.value for style in ExecutionStyle],
        "profile_results": _profile_rows(outputs),
        "matrix_rows": len(matrix_rows),
        "output_dir": str(output_dir),
        "artifacts": {key: str(output_dir / filename) for filename, key in ARTIFACT_FILENAMES.items()},
        "claims": {
            "fair_value_to_execution": True,
            "live_football_execution": False,
            "participant_level_fifo": False,
            "hidden_liquidity": False,
            "historical_fill_truth": False,
            "production_alpha": False,
        },
        "limitations": [
            "The replay input is synthetic and bounded.",
            "Visible-depth depletion is used as a queue-ahead proxy; public snapshots do not reveal participant-level historical FIFO.",
            "Latency and fees are parameterized assumptions, not measured venue-specific production observations.",
        ],
        "config": config_as_dict(config),
    }
    _write_artifact(output_dir / "summary.json", json.dumps(summary, indent=2, default=str) + "\n")
    return actual_run_id, output_dir, summary
