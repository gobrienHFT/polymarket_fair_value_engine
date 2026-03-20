from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from polymarket_fair_value_engine.analytics.fills import export_dataclasses
from polymarket_fair_value_engine.analytics.reports import create_run_directory
from polymarket_fair_value_engine.sports.normalize import FootballFairValueResult, NormalizedFootballEvent, load_football_sample
from polymarket_fair_value_engine.sports.pricing import DEFAULT_FOOTBALL_PRICING_CONFIG, price_binary_market


def _positive_edge_magnitude(row: FootballFairValueResult) -> float:
    return row.max_actionable_edge


def price_football_markets(events: Iterable[NormalizedFootballEvent]) -> tuple[FootballFairValueResult, ...]:
    rows: list[FootballFairValueResult] = []
    for event in events:
        for market in event.markets:
            priced = price_binary_market(
                market=market,
                bookmaker_snapshots=event.bookmaker_snapshots,
                timestamp_utc=event.fixture.kickoff_utc,
                config=DEFAULT_FOOTBALL_PRICING_CONFIG,
            )
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
            key=lambda row: (row.max_actionable_edge, abs(row.edge_vs_mid or 0.0)),
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
