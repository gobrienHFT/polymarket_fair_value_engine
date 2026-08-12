from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.sports.odds import FootballBinaryMarketType


class FootballMatchStatus(str, Enum):
    PREGAME = "pregame"
    INPLAY = "inplay"
    FINISHED = "finished"
    SUSPENDED = "suspended"


class FootballStateChangeType(str, Enum):
    KICKOFF = "kickoff"
    GOAL_HOME = "goal_home"
    GOAL_AWAY = "goal_away"
    EQUALIZER = "equalizer"
    LEAD_CHANGE = "lead_change"
    RED_CARD_HOME = "red_card_home"
    RED_CARD_AWAY = "red_card_away"
    FINISH = "finish"


class FootballDecisionSide(str, Enum):
    BUY_YES = "buy_yes"
    SELL_YES = "sell_yes"
    NO_TRADE = "no_trade"


@dataclass(frozen=True)
class FootballFixture:
    event_id: str
    league: str
    kickoff_utc: datetime
    home_team: str
    away_team: str

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id must be non-empty")
        if not self.league.strip():
            raise ValueError("league must be non-empty")
        if not self.home_team.strip() or not self.away_team.strip():
            raise ValueError("home_team and away_team must be non-empty")
        if self.home_team.strip() == self.away_team.strip():
            raise ValueError("home_team and away_team must differ")
        if self.kickoff_utc.tzinfo is None or self.kickoff_utc.utcoffset() is None:
            raise ValueError("kickoff_utc must be timezone-aware")


@dataclass(frozen=True)
class BookmakerOneXTwoOddsSnapshot:
    source_name: str
    home_decimal: float
    draw_decimal: float
    away_decimal: float
    observed_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if not self.source_name.strip():
            raise ValueError("source_name must be non-empty")
        for name, value in (
            ("home_decimal", self.home_decimal),
            ("draw_decimal", self.draw_decimal),
            ("away_decimal", self.away_decimal),
        ):
            if not isfinite(value) or value <= 1.0:
                raise ValueError(f"{name} must be finite and greater than 1.0")
        if self.observed_at_utc is not None and (
            self.observed_at_utc.tzinfo is None or self.observed_at_utc.utcoffset() is None
        ):
            raise ValueError("observed_at_utc must be timezone-aware")


@dataclass(frozen=True)
class PolymarketBinaryMarketDefinition:
    event_id: str
    market_id: str
    market_slug: str
    market_question: str
    market_type: FootballBinaryMarketType | None
    raw_market_type: str
    best_bid_yes: float | None
    best_ask_yes: float | None

    def __post_init__(self) -> None:
        if self.best_bid_yes is not None and (not isfinite(self.best_bid_yes) or not 0.0 <= self.best_bid_yes <= 1.0):
            raise ValueError("best_bid_yes must be within [0, 1]")
        if self.best_ask_yes is not None and (not isfinite(self.best_ask_yes) or not 0.0 <= self.best_ask_yes <= 1.0):
            raise ValueError("best_ask_yes must be within [0, 1]")
        if self.best_bid_yes is not None and self.best_ask_yes is not None and self.best_bid_yes > self.best_ask_yes:
            raise ValueError("best_bid_yes cannot exceed best_ask_yes")

    @property
    def market_mid_yes(self) -> float | None:
        if self.best_bid_yes is None or self.best_ask_yes is None:
            return None
        return (self.best_bid_yes + self.best_ask_yes) / 2.0

    @property
    def market_type_label(self) -> str:
        return self.market_type.value if self.market_type is not None else self.raw_market_type


@dataclass(frozen=True)
class NormalizedFootballEvent:
    fixture: FootballFixture
    bookmaker_snapshots: tuple[BookmakerOneXTwoOddsSnapshot, ...]
    markets: tuple[PolymarketBinaryMarketDefinition, ...]


@dataclass(frozen=True)
class FootballMatchState:
    status: FootballMatchStatus
    minute: int
    added_time: int
    home_goals: int
    away_goals: int
    home_red_cards: int
    away_red_cards: int

    def __post_init__(self) -> None:
        for name, value in (
            ("minute", self.minute),
            ("added_time", self.added_time),
            ("home_goals", self.home_goals),
            ("away_goals", self.away_goals),
            ("home_red_cards", self.home_red_cards),
            ("away_red_cards", self.away_red_cards),
        ):
            if value < 0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class FootballReplayFrame:
    frame_id: str
    timestamp_utc: datetime
    fixture: FootballFixture
    match_state: FootballMatchState
    bookmaker_snapshots: tuple[BookmakerOneXTwoOddsSnapshot, ...]
    markets: tuple[PolymarketBinaryMarketDefinition, ...]

    def __post_init__(self) -> None:
        if not self.frame_id.strip():
            raise ValueError("frame_id must be non-empty")
        if self.timestamp_utc.tzinfo is None or self.timestamp_utc.utcoffset() is None:
            raise ValueError("timestamp_utc must be timezone-aware")
        if any(market.event_id != self.fixture.event_id for market in self.markets):
            raise ValueError("all replay markets must belong to the frame fixture")


@dataclass(frozen=True)
class FootballStateChange:
    frame_id: str
    event_id: str
    timestamp_utc: datetime
    change_type: FootballStateChangeType
    minute: int
    home_goals: int
    away_goals: int
    home_red_cards: int
    away_red_cards: int


@dataclass(frozen=True)
class FootballFairValueResult:
    event_id: str
    league: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    market_id: str
    market_slug: str
    market_question: str
    market_type: str
    fair_yes: float | None
    fair_no: float | None
    uncertainty: float | None
    market_mid_yes: float | None
    best_bid_yes: float | None
    best_ask_yes: float | None
    source_overround: float
    source_disagreement: float
    source_name: str
    source_count: int
    source_is_stale: bool
    quote_bid_yes: float | None
    quote_ask_yes: float | None
    buy_edge_vs_ask: float | None
    sell_edge_vs_bid: float | None
    edge_vs_mid: float | None
    max_actionable_edge: float
    decision_side: FootballDecisionSide
    edge_vs_best_ask: float | None
    edge_vs_best_bid: float | None
    no_trade_reason: str | None


@dataclass(frozen=True)
class FootballReplayQuoteRow:
    frame_id: str
    timestamp_utc: datetime
    event_id: str
    league: str
    kickoff_utc: datetime
    home_team: str
    away_team: str
    match_status: FootballMatchStatus
    minute: int
    added_time: int
    home_goals: int
    away_goals: int
    home_red_cards: int
    away_red_cards: int
    state_change_tags: tuple[FootballStateChangeType, ...]
    state_regime: str
    market_id: str
    market_slug: str
    market_question: str
    market_type: str
    fair_yes: float | None
    fair_no: float | None
    uncertainty: float | None
    market_mid_yes: float | None
    best_bid_yes: float | None
    best_ask_yes: float | None
    source_overround: float
    source_disagreement: float
    source_name: str
    source_count: int
    source_is_stale: bool
    source_quality: str
    quote_bid_yes: float | None
    quote_ask_yes: float | None
    buy_edge_vs_ask: float | None
    sell_edge_vs_bid: float | None
    edge_vs_mid: float | None
    max_actionable_edge: float
    decision_side: FootballDecisionSide
    edge_vs_best_ask: float | None
    edge_vs_best_bid: float | None
    no_trade_reason: str | None


@dataclass(frozen=True)
class FootballMarkoutRow:
    frame_id: str
    timestamp_utc: datetime
    event_id: str
    market_id: str
    market_type: str
    match_status: FootballMatchStatus
    minute: int
    decision_side: FootballDecisionSide
    no_trade_reason: str | None
    fair_yes: float | None
    current_mid_yes: float | None
    next_snapshot_mid_yes: float | None
    raw_next_mid_change: float | None
    directional_next_capture: float | None
    next_snapshot_markout: float | None
    next_snapshot_edge_capture: float | None
    mid_yes_2_steps: float | None
    raw_2step_mid_change: float | None
    directional_2step_capture: float | None
    markout_2_steps: float | None
    max_favorable_move: float | None
    max_adverse_move: float | None
    eventual_settlement_yes: float | None
    raw_eventual_resolution_change: float | None
    directional_eventual_capture: float | None
    eventual_resolution_markout: float | None


@dataclass(frozen=True)
class FootballCalibrationRow:
    bucket_type: str
    bucket_value: str
    observations: int
    average_raw_next_mid_change: float | None
    average_raw_2step_mid_change: float | None
    average_directional_next_capture: float | None
    average_directional_2step_capture: float | None
    average_directional_eventual_capture: float | None
    positive_capture_rate: float | None
    average_max_adverse_move: float | None
    average_next_snapshot_markout: float | None
    average_markout_2_steps: float | None
    sign_hit_rate: float | None


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include a timezone offset")
    return parsed


def _load_payloads(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        payloads: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if stripped:
                    try:
                        payload = json.loads(stripped)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f"Invalid JSON on line {line_number} of {path}: {exc.msg}") from exc
                    if not isinstance(payload, dict):
                        raise ValueError(f"Replay row on line {line_number} of {path} must be a JSON object")
                    payloads.append(payload)
        return payloads
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"Football sample file {path} must contain a JSON array of objects")
    return payload


def _parse_fixture(payload: dict[str, Any]) -> FootballFixture:
    return FootballFixture(
        event_id=str(payload["event_id"]),
        league=str(payload["league"]),
        kickoff_utc=_parse_datetime(str(payload["kickoff_utc"])),
        home_team=str(payload["home_team"]),
        away_team=str(payload["away_team"]),
    )


def _parse_bookmaker_snapshot(payload: dict[str, Any]) -> BookmakerOneXTwoOddsSnapshot:
    observed_at = payload.get("observed_at_utc")
    return BookmakerOneXTwoOddsSnapshot(
        source_name=str(payload["source_name"]),
        home_decimal=float(payload["home_decimal"]),
        draw_decimal=float(payload["draw_decimal"]),
        away_decimal=float(payload["away_decimal"]),
        observed_at_utc=_parse_datetime(str(observed_at)) if observed_at else None,
    )


def _parse_market(event_id: str, payload: dict[str, Any]) -> PolymarketBinaryMarketDefinition:
    raw_market_type = str(payload["market_type"])
    try:
        market_type = FootballBinaryMarketType(raw_market_type)
    except ValueError:
        market_type = None

    def _optional_probability(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    return PolymarketBinaryMarketDefinition(
        event_id=event_id,
        market_id=str(payload["market_id"]),
        market_slug=str(payload["market_slug"]),
        market_question=str(payload["market_question"]),
        market_type=market_type,
        raw_market_type=raw_market_type,
        best_bid_yes=_optional_probability(payload.get("best_bid_yes")),
        best_ask_yes=_optional_probability(payload.get("best_ask_yes")),
    )


def _parse_match_state(payload: dict[str, Any]) -> FootballMatchState:
    return FootballMatchState(
        status=FootballMatchStatus(str(payload["status"])),
        minute=int(payload.get("minute", 0)),
        added_time=int(payload.get("added_time", 0)),
        home_goals=int(payload.get("home_goals", 0)),
        away_goals=int(payload.get("away_goals", 0)),
        home_red_cards=int(payload.get("home_red_cards", 0)),
        away_red_cards=int(payload.get("away_red_cards", 0)),
    )


def load_football_sample(path: str | Path) -> tuple[NormalizedFootballEvent, ...]:
    file_path = Path(path)
    events: list[NormalizedFootballEvent] = []
    seen_event_ids: set[str] = set()
    for payload in _load_payloads(file_path):
        fixture = _parse_fixture(payload["fixture"])
        if fixture.event_id in seen_event_ids:
            raise ValueError(f"Duplicate football fixture event_id: {fixture.event_id}")
        bookmaker_snapshots = tuple(_parse_bookmaker_snapshot(item) for item in payload.get("bookmakers", []))
        if not bookmaker_snapshots:
            raise ValueError(f"Fixture {fixture.event_id} requires at least one bookmaker snapshot")
        markets = tuple(_parse_market(fixture.event_id, item) for item in payload.get("markets", []))
        if not markets:
            raise ValueError(f"Fixture {fixture.event_id} requires at least one market")
        market_ids = [market.market_id for market in markets]
        if len(market_ids) != len(set(market_ids)):
            raise ValueError(f"Fixture {fixture.event_id} contains duplicate market_id values")
        events.append(
            NormalizedFootballEvent(
                fixture=fixture,
                bookmaker_snapshots=bookmaker_snapshots,
                markets=markets,
            )
        )
        seen_event_ids.add(fixture.event_id)
    return tuple(events)


def load_football_replay_frames(path: str | Path) -> tuple[FootballReplayFrame, ...]:
    file_path = Path(path)
    frames: list[FootballReplayFrame] = []
    seen_frame_ids: set[str] = set()
    previous_timestamp_by_event: dict[str, datetime] = {}
    fixture_by_event: dict[str, FootballFixture] = {}
    for payload in _load_payloads(file_path):
        fixture = _parse_fixture(payload["fixture"])
        timestamp_utc = _parse_datetime(str(payload["timestamp_utc"]))
        frame_id = str(payload.get("frame_id", f"{fixture.event_id}:{timestamp_utc.isoformat()}"))
        if frame_id in seen_frame_ids:
            raise ValueError(f"Duplicate football replay frame_id: {frame_id}")
        previous_timestamp = previous_timestamp_by_event.get(fixture.event_id)
        if previous_timestamp is not None and timestamp_utc <= previous_timestamp:
            raise ValueError(
                f"Replay timestamps for {fixture.event_id} must be strictly increasing; "
                f"got {timestamp_utc.isoformat()} after {previous_timestamp.isoformat()}"
            )
        previous_fixture = fixture_by_event.get(fixture.event_id)
        if previous_fixture is not None and fixture != previous_fixture:
            raise ValueError(f"Fixture metadata changed within replay event {fixture.event_id}")
        match_state = _parse_match_state(payload["match_state"])
        bookmaker_snapshots = tuple(_parse_bookmaker_snapshot(item) for item in payload.get("bookmakers", []))
        if not bookmaker_snapshots:
            raise ValueError(f"Replay frame for {fixture.event_id} at {timestamp_utc.isoformat()} requires at least one bookmaker snapshot")
        markets = tuple(_parse_market(fixture.event_id, item) for item in payload.get("markets", []))
        if not markets:
            raise ValueError(f"Replay frame for {fixture.event_id} at {timestamp_utc.isoformat()} requires at least one market")
        market_ids = [market.market_id for market in markets]
        if len(market_ids) != len(set(market_ids)):
            raise ValueError(f"Replay frame {frame_id} contains duplicate market_id values")
        frames.append(
            FootballReplayFrame(
                frame_id=frame_id,
                timestamp_utc=timestamp_utc,
                fixture=fixture,
                match_state=match_state,
                bookmaker_snapshots=bookmaker_snapshots,
                markets=markets,
            )
        )
        seen_frame_ids.add(frame_id)
        previous_timestamp_by_event[fixture.event_id] = timestamp_utc
        fixture_by_event[fixture.event_id] = fixture
    if not frames:
        raise ValueError(f"Football replay file {file_path} contains no frames")
    return tuple(frames)
