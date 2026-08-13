from __future__ import annotations

import json
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.execution_research.types import ClobSnapshot, ExecutionResearchConfig, MarketValidity, ReplayFrame
from polymarket_fair_value_engine.types import BookLevel


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _parse_sequence(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _parse_probability(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if isfinite(parsed) and 0.0 <= parsed <= 1.0 else None


def _parse_levels(value: Any) -> tuple[tuple[BookLevel, ...], bool]:
    if not isinstance(value, list):
        return (), False
    levels: list[BookLevel] = []
    try:
        for raw_level in value:
            if not isinstance(raw_level, list) or len(raw_level) != 2:
                return (), False
            price = float(raw_level[0])
            size = float(raw_level[1])
            if not isfinite(price) or not isfinite(size):
                return (), False
            levels.append(BookLevel(price=price, size=size))
    except (TypeError, ValueError, OverflowError):
        return (), False
    bids_or_asks = tuple(levels)
    return bids_or_asks, True


def _status(reasons: list[str]) -> MarketValidity:
    if not reasons:
        return MarketValidity.VALID
    for candidate in (
        MarketValidity.MALFORMED,
        MarketValidity.CROSSED,
        MarketValidity.STALE,
        MarketValidity.DISCONTINUOUS,
        MarketValidity.EXPIRED,
    ):
        if candidate.value in reasons:
            return candidate
    return MarketValidity.MALFORMED


def load_clob_replay(path: str | Path, config: ExecutionResearchConfig) -> list[ReplayFrame]:
    replay_path = Path(path)
    frames: list[ReplayFrame] = []
    previous: dict[str, tuple[int, datetime, str]] = {}
    with replay_path.open("r", encoding="utf-8") as handle:
        for row_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            reasons: list[str] = []
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {}
                reasons.append(MarketValidity.MALFORMED.value)
            if not isinstance(payload, dict):
                payload = {}
                reasons.append(MarketValidity.MALFORMED.value)

            market_id = payload.get("market_id")
            yes_token_id = payload.get("yes_token_id")
            if not isinstance(market_id, str) or not market_id.strip():
                market_id = f"invalid-line-{row_number}"
                reasons.append(MarketValidity.MALFORMED.value)
            if not isinstance(yes_token_id, str) or not yes_token_id.strip():
                yes_token_id = "invalid-token"
                reasons.append(MarketValidity.MALFORMED.value)

            timestamp = _parse_timestamp(payload.get("timestamp_utc"))
            if timestamp is None:
                reasons.append(MarketValidity.MALFORMED.value)
            source_timestamp = _parse_timestamp(payload.get("book_timestamp_utc"))
            if source_timestamp is None:
                reasons.append(MarketValidity.MALFORMED.value)
            sequence = _parse_sequence(payload.get("sequence"))
            if sequence is None:
                reasons.append(MarketValidity.MALFORMED.value)

            bids, bids_ok = _parse_levels(payload.get("yes_bids"))
            asks, asks_ok = _parse_levels(payload.get("yes_asks"))
            if not bids_ok or not asks_ok or not bids or not asks:
                reasons.append(MarketValidity.MALFORMED.value)

            fair_yes = _parse_probability(payload.get("fair_yes"))
            if fair_yes is None:
                reasons.append(MarketValidity.MALFORMED.value)
            settlement_yes = payload.get("settlement_yes")
            if settlement_yes is not None and not isinstance(settlement_yes, bool):
                settlement_yes = None
                reasons.append(MarketValidity.MALFORMED.value)
            expires_at = _parse_timestamp(payload.get("expires_at_utc")) if payload.get("expires_at_utc") else None
            if payload.get("expires_at_utc") and expires_at is None:
                reasons.append(MarketValidity.MALFORMED.value)

            if timestamp is not None and source_timestamp is not None:
                source_lag = (timestamp - source_timestamp).total_seconds()
                if source_lag < 0.0:
                    reasons.append(MarketValidity.MALFORMED.value)
                elif source_lag > config.stale_after_seconds:
                    reasons.append(MarketValidity.STALE.value)
            if bids and asks and bids[0].price > asks[0].price:
                reasons.append(MarketValidity.CROSSED.value)
            if timestamp is not None and expires_at is not None and timestamp >= expires_at:
                reasons.append(MarketValidity.EXPIRED.value)

            prior = previous.get(market_id)
            if prior is not None and sequence is not None and timestamp is not None:
                previous_sequence, previous_timestamp, previous_token_id = prior
                if sequence != previous_sequence + 1 or timestamp <= previous_timestamp:
                    reasons.append(MarketValidity.DISCONTINUOUS.value)
                if yes_token_id != previous_token_id:
                    reasons.append(MarketValidity.MALFORMED.value)
            if sequence is not None and timestamp is not None:
                previous[market_id] = (sequence, timestamp, yes_token_id)

            normalized_reasons = tuple(sorted(set(reasons)))
            snapshot = ClobSnapshot(
                market_id=market_id,
                yes_token_id=yes_token_id,
                timestamp=timestamp,
                source_timestamp=source_timestamp,
                sequence=sequence,
                bids=tuple(sorted(bids, key=lambda level: level.price, reverse=True)),
                asks=tuple(sorted(asks, key=lambda level: level.price)),
                validity=_status(list(normalized_reasons)),
                validity_reasons=normalized_reasons,
                source_row=row_number,
            )
            frames.append(
                ReplayFrame(
                    snapshot=snapshot,
                    fair_yes=fair_yes,
                    settlement_yes=settlement_yes,
                    expires_at=expires_at,
                )
            )
    if not frames:
        raise ValueError(f"Execution replay file {replay_path} contains no rows")
    if not any(frame.snapshot.validity is MarketValidity.VALID for frame in frames):
        raise ValueError(f"Execution replay file {replay_path} contains no valid market states")
    return frames
