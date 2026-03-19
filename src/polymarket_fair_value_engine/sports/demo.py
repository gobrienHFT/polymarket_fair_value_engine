from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from polymarket_fair_value_engine.analytics.fills import export_dataclasses
from polymarket_fair_value_engine.analytics.reports import create_run_directory
from polymarket_fair_value_engine.sports.normalize import FootballFairValueResult, NormalizedFootballEvent, PolymarketBinaryMarketDefinition, load_football_sample
from polymarket_fair_value_engine.sports.odds import OneXTwoProbabilities, binary_yes_probability, decimal_odds_to_implied_probabilities, overround, remove_overround_proportionally


@dataclass(frozen=True)
class ConsensusFootballProbabilities:
    probabilities: OneXTwoProbabilities
    source_name: str
    source_overround: float
    disagreement: float


def _clip_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def _round_down_to_tick(value: float, tick: float = 0.01) -> float:
    return round(math.floor(value / tick) * tick, 4)


def _round_up_to_tick(value: float, tick: float = 0.01) -> float:
    return round(math.ceil(value / tick) * tick, 4)


def _event_consensus(event: NormalizedFootballEvent) -> ConsensusFootballProbabilities:
    fair_probabilities: list[OneXTwoProbabilities] = []
    overrounds: list[float] = []
    source_names: list[str] = []

    for snapshot in event.bookmaker_snapshots:
        implied = decimal_odds_to_implied_probabilities(
            snapshot.home_decimal,
            snapshot.draw_decimal,
            snapshot.away_decimal,
        )
        fair_probabilities.append(remove_overround_proportionally(implied))
        overrounds.append(overround(implied))
        source_names.append(snapshot.source_name)

    home_values = [item.home for item in fair_probabilities]
    draw_values = [item.draw for item in fair_probabilities]
    away_values = [item.away for item in fair_probabilities]
    probabilities = OneXTwoProbabilities(
        home=sum(home_values) / len(home_values),
        draw=sum(draw_values) / len(draw_values),
        away=sum(away_values) / len(away_values),
    )
    disagreement = max(
        (max(values) - min(values)) if len(values) > 1 else 0.0
        for values in (home_values, draw_values, away_values)
    )
    return ConsensusFootballProbabilities(
        probabilities=probabilities,
        source_name="+".join(source_names),
        source_overround=sum(overrounds) / len(overrounds),
        disagreement=disagreement,
    )


def _market_spread(market: PolymarketBinaryMarketDefinition) -> float | None:
    if market.best_bid_yes is None or market.best_ask_yes is None:
        return None
    return market.best_ask_yes - market.best_bid_yes


def _uncertainty(consensus: ConsensusFootballProbabilities, market: PolymarketBinaryMarketDefinition) -> float:
    spread = _market_spread(market) or 0.0
    return round(max(0.01, consensus.source_overround / 2.0, consensus.disagreement, spread / 2.0), 6)


def _candidate_quotes(fair_yes: float, uncertainty: float, market: PolymarketBinaryMarketDefinition) -> tuple[float, float]:
    half_spread = max(0.02, uncertainty)
    bid_yes = _round_down_to_tick(_clip_probability(fair_yes - half_spread))
    ask_yes = _round_up_to_tick(_clip_probability(fair_yes + half_spread))
    if market.best_ask_yes is not None:
        bid_yes = min(bid_yes, _round_down_to_tick(max(0.01, market.best_ask_yes - 0.01)))
    if market.best_bid_yes is not None:
        ask_yes = max(ask_yes, _round_up_to_tick(min(0.99, market.best_bid_yes + 0.01)))
    if bid_yes >= ask_yes:
        bid_yes = _round_down_to_tick(_clip_probability(fair_yes - 0.01))
        ask_yes = _round_up_to_tick(_clip_probability(fair_yes + 0.01))
    return round(_clip_probability(bid_yes), 4), round(_clip_probability(ask_yes), 4)


def _no_trade_reason(fair_yes: float, market: PolymarketBinaryMarketDefinition) -> str | None:
    if market.best_bid_yes is None or market.best_ask_yes is None:
        return "missing_yes_book"
    if market.best_ask_yes - market.best_bid_yes > 0.12:
        return "wide_yes_spread"
    if market.best_bid_yes <= fair_yes <= market.best_ask_yes:
        return "fair_inside_spread"
    return None


def _edge_against_mid(fair_yes: float, market: PolymarketBinaryMarketDefinition) -> float | None:
    if market.market_mid_yes is None:
        return None
    return round(fair_yes - market.market_mid_yes, 6)


def _edge_against_best(price: float | None, fair_yes: float) -> float | None:
    if price is None:
        return None
    return round(fair_yes - price, 6)


def _positive_edge_magnitude(row: FootballFairValueResult) -> float:
    buy_edge = max(row.edge_vs_best_ask or 0.0, 0.0)
    sell_edge = max((row.best_bid_yes - row.fair_yes) if row.best_bid_yes is not None else 0.0, 0.0)
    return round(max(buy_edge, sell_edge), 6)


def price_football_markets(events: Iterable[NormalizedFootballEvent]) -> tuple[FootballFairValueResult, ...]:
    rows: list[FootballFairValueResult] = []
    for event in events:
        consensus = _event_consensus(event)
        for market in event.markets:
            fair_yes = round(binary_yes_probability(consensus.probabilities, market.market_type), 6)
            uncertainty = _uncertainty(consensus, market)
            quote_bid_yes, quote_ask_yes = _candidate_quotes(fair_yes, uncertainty, market)
            rows.append(
                FootballFairValueResult(
                    event_id=event.fixture.event_id,
                    league=event.fixture.league,
                    kickoff_utc=event.fixture.kickoff_utc,
                    home_team=event.fixture.home_team,
                    away_team=event.fixture.away_team,
                    market_id=market.market_id,
                    market_slug=market.market_slug,
                    market_question=market.market_question,
                    market_type=market.market_type,
                    fair_yes=fair_yes,
                    fair_no=round(1.0 - fair_yes, 6),
                    uncertainty=uncertainty,
                    market_mid_yes=round(market.market_mid_yes, 6) if market.market_mid_yes is not None else None,
                    best_bid_yes=market.best_bid_yes,
                    best_ask_yes=market.best_ask_yes,
                    source_overround=round(consensus.source_overround, 6),
                    source_name=consensus.source_name,
                    quote_bid_yes=quote_bid_yes,
                    quote_ask_yes=quote_ask_yes,
                    edge_vs_mid=_edge_against_mid(fair_yes, market),
                    edge_vs_best_ask=_edge_against_best(market.best_ask_yes, fair_yes),
                    edge_vs_best_bid=_edge_against_best(market.best_bid_yes, fair_yes),
                    no_trade_reason=_no_trade_reason(fair_yes, market),
                )
            )
    return tuple(rows)


def run_football_demo(input_path: str | Path, output_root: Path, run_id: str | None = None) -> tuple[str, Path, dict[str, object]]:
    events = load_football_sample(input_path)
    actual_run_id, output_dir = create_run_directory(output_root, run_id=run_id)
    fair_value_rows = tuple(
        sorted(
            price_football_markets(events),
            key=lambda row: (row.kickoff_utc, row.event_id, row.market_slug),
        )
    )
    edge_rows = tuple(
        sorted(
            fair_value_rows,
            key=lambda row: (_positive_edge_magnitude(row), abs(row.edge_vs_mid or 0.0)),
            reverse=True,
        )
    )

    export_dataclasses(output_dir / "football_fair_values.csv", list(fair_value_rows))
    export_dataclasses(output_dir / "football_edges.csv", list(edge_rows))

    artifacts = {
        "summary_json": str(output_dir / "summary.json"),
        "football_fair_values_csv": str(output_dir / "football_fair_values.csv"),
        "football_edges_csv": str(output_dir / "football_edges.csv"),
    }
    mid_edge_rows = [abs(row.edge_vs_mid) for row in fair_value_rows if row.edge_vs_mid is not None]
    summary = {
        "run_id": actual_run_id,
        "mode": "football-demo",
        "fixtures": len(events),
        "markets": sum(len(event.markets) for event in events),
        "priced_markets": len(fair_value_rows),
        "positive_edge_markets": sum(1 for row in fair_value_rows if _positive_edge_magnitude(row) > 0.0),
        "average_absolute_edge": round(sum(mid_edge_rows) / max(1, len(mid_edge_rows)), 6),
        "max_positive_edge": round(max((_positive_edge_magnitude(row) for row in fair_value_rows), default=0.0), 6),
        "output_dir": str(output_dir),
        "artifacts": artifacts,
    }
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)
    return actual_run_id, output_dir, summary
