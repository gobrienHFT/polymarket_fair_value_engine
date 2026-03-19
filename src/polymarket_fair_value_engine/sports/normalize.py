from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.sports.odds import FootballBinaryMarketType


@dataclass(frozen=True)
class FootballFixture:
    event_id: str
    league: str
    kickoff_utc: datetime
    home_team: str
    away_team: str


@dataclass(frozen=True)
class BookmakerOneXTwoOddsSnapshot:
    source_name: str
    home_decimal: float
    draw_decimal: float
    away_decimal: float


@dataclass(frozen=True)
class PolymarketBinaryMarketDefinition:
    event_id: str
    market_id: str
    market_slug: str
    market_question: str
    market_type: FootballBinaryMarketType
    best_bid_yes: float | None
    best_ask_yes: float | None

    def __post_init__(self) -> None:
        if self.best_bid_yes is not None and not 0.0 <= self.best_bid_yes <= 1.0:
            raise ValueError("best_bid_yes must be within [0, 1]")
        if self.best_ask_yes is not None and not 0.0 <= self.best_ask_yes <= 1.0:
            raise ValueError("best_ask_yes must be within [0, 1]")
        if self.best_bid_yes is not None and self.best_ask_yes is not None and self.best_bid_yes > self.best_ask_yes:
            raise ValueError("best_bid_yes cannot exceed best_ask_yes")

    @property
    def market_mid_yes(self) -> float | None:
        if self.best_bid_yes is None or self.best_ask_yes is None:
            return None
        return (self.best_bid_yes + self.best_ask_yes) / 2.0


@dataclass(frozen=True)
class NormalizedFootballEvent:
    fixture: FootballFixture
    bookmaker_snapshots: tuple[BookmakerOneXTwoOddsSnapshot, ...]
    markets: tuple[PolymarketBinaryMarketDefinition, ...]


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
    market_type: FootballBinaryMarketType
    fair_yes: float
    fair_no: float
    uncertainty: float
    market_mid_yes: float | None
    best_bid_yes: float | None
    best_ask_yes: float | None
    source_overround: float
    source_name: str
    quote_bid_yes: float
    quote_ask_yes: float
    edge_vs_mid: float | None
    edge_vs_best_ask: float | None
    edge_vs_best_bid: float | None
    no_trade_reason: str | None


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_payloads(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        payloads: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    payloads.append(json.loads(stripped))
        return payloads
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_bookmaker_snapshot(payload: dict[str, Any]) -> BookmakerOneXTwoOddsSnapshot:
    return BookmakerOneXTwoOddsSnapshot(
        source_name=str(payload["source_name"]),
        home_decimal=float(payload["home_decimal"]),
        draw_decimal=float(payload["draw_decimal"]),
        away_decimal=float(payload["away_decimal"]),
    )


def _parse_market(event_id: str, payload: dict[str, Any]) -> PolymarketBinaryMarketDefinition:
    def _optional_probability(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    return PolymarketBinaryMarketDefinition(
        event_id=event_id,
        market_id=str(payload["market_id"]),
        market_slug=str(payload["market_slug"]),
        market_question=str(payload["market_question"]),
        market_type=FootballBinaryMarketType(str(payload["market_type"])),
        best_bid_yes=_optional_probability(payload.get("best_bid_yes")),
        best_ask_yes=_optional_probability(payload.get("best_ask_yes")),
    )


def load_football_sample(path: str | Path) -> tuple[NormalizedFootballEvent, ...]:
    file_path = Path(path)
    events: list[NormalizedFootballEvent] = []
    for payload in _load_payloads(file_path):
        fixture_payload = payload["fixture"]
        fixture = FootballFixture(
            event_id=str(fixture_payload["event_id"]),
            league=str(fixture_payload["league"]),
            kickoff_utc=_parse_datetime(str(fixture_payload["kickoff_utc"])),
            home_team=str(fixture_payload["home_team"]),
            away_team=str(fixture_payload["away_team"]),
        )
        bookmaker_snapshots = tuple(_parse_bookmaker_snapshot(item) for item in payload.get("bookmakers", []))
        if not bookmaker_snapshots:
            raise ValueError(f"Fixture {fixture.event_id} requires at least one bookmaker snapshot")
        markets = tuple(_parse_market(fixture.event_id, item) for item in payload.get("markets", []))
        if not markets:
            raise ValueError(f"Fixture {fixture.event_id} requires at least one market")
        events.append(
            NormalizedFootballEvent(
                fixture=fixture,
                bookmaker_snapshots=bookmaker_snapshots,
                markets=markets,
            )
        )
    return tuple(events)
