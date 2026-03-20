from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

from polymarket_fair_value_engine.sports.normalize import BookmakerOneXTwoOddsSnapshot, FootballDecisionSide, FootballMatchState, FootballMatchStatus, FootballStateChangeType, PolymarketBinaryMarketDefinition
from polymarket_fair_value_engine.sports.odds import OneXTwoProbabilities, binary_yes_probability, decimal_odds_to_implied_probabilities, overround, remove_overround_proportionally


@dataclass(frozen=True)
class FootballPricingConfig:
    quote_tick: float = 0.01
    quote_base_half_spread: float = 0.02
    minimum_bookmaker_sources: int = 2
    stale_source_data_seconds: int = 180
    wide_yes_spread_threshold: float = 0.12
    high_uncertainty_threshold: float = 0.08
    goal_cooldown_minutes: int = 3
    red_card_cooldown_minutes: int = 5
    goal_uncertainty_boost: float = 0.04
    red_card_uncertainty_boost: float = 0.05
    suspended_uncertainty_boost: float = 0.10


DEFAULT_FOOTBALL_PRICING_CONFIG = FootballPricingConfig()


@dataclass(frozen=True)
class ConsensusFootballProbabilities:
    probabilities: OneXTwoProbabilities
    source_name: str
    source_overround: float
    disagreement: float
    source_count: int
    is_stale: bool


@dataclass(frozen=True)
class FootballPricedBinaryMarket:
    market_type: str
    fair_yes: float | None
    fair_no: float | None
    uncertainty: float | None
    market_mid_yes: float | None
    best_bid_yes: float | None
    best_ask_yes: float | None
    source_overround: float
    source_name: str
    source_count: int
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


def _clip_probability(value: float) -> float:
    return max(0.01, min(0.99, value))


def _round_down_to_tick(value: float, tick: float) -> float:
    return round(math.floor(value / tick) * tick, 4)


def _round_up_to_tick(value: float, tick: float) -> float:
    return round(math.ceil(value / tick) * tick, 4)


def build_bookmaker_consensus(
    bookmaker_snapshots: tuple[BookmakerOneXTwoOddsSnapshot, ...],
    timestamp_utc: datetime | None = None,
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> ConsensusFootballProbabilities:
    fair_probabilities: list[OneXTwoProbabilities] = []
    overrounds: list[float] = []
    source_names: list[str] = []
    is_stale = False

    for snapshot in bookmaker_snapshots:
        implied = decimal_odds_to_implied_probabilities(
            snapshot.home_decimal,
            snapshot.draw_decimal,
            snapshot.away_decimal,
        )
        fair_probabilities.append(remove_overround_proportionally(implied))
        overrounds.append(overround(implied))
        source_names.append(snapshot.source_name)
        if timestamp_utc is not None and snapshot.observed_at_utc is not None:
            age_seconds = (timestamp_utc - snapshot.observed_at_utc).total_seconds()
            if age_seconds > config.stale_source_data_seconds:
                is_stale = True

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
        source_count=len(bookmaker_snapshots),
        is_stale=is_stale,
    )


def _market_spread(market: PolymarketBinaryMarketDefinition) -> float | None:
    if market.best_bid_yes is None or market.best_ask_yes is None:
        return None
    return market.best_ask_yes - market.best_bid_yes


def build_uncertainty(
    consensus: ConsensusFootballProbabilities,
    market: PolymarketBinaryMarketDefinition,
    match_state: FootballMatchState | None = None,
    recent_state_changes: tuple[FootballStateChangeType, ...] = (),
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> float:
    spread = _market_spread(market) or 0.0
    uncertainty = max(0.01, consensus.source_overround / 2.0, consensus.disagreement, spread / 2.0)
    if match_state is not None and match_state.status is FootballMatchStatus.SUSPENDED:
        uncertainty = max(uncertainty, config.suspended_uncertainty_boost)
    if any(
        change in {
            FootballStateChangeType.GOAL_HOME,
            FootballStateChangeType.GOAL_AWAY,
            FootballStateChangeType.EQUALIZER,
            FootballStateChangeType.LEAD_CHANGE,
        }
        for change in recent_state_changes
    ):
        uncertainty = max(uncertainty, config.goal_uncertainty_boost)
    if any(
        change in {FootballStateChangeType.RED_CARD_HOME, FootballStateChangeType.RED_CARD_AWAY}
        for change in recent_state_changes
    ):
        uncertainty = max(uncertainty, config.red_card_uncertainty_boost)
    return round(uncertainty, 6)


def build_candidate_quotes(
    fair_yes: float,
    uncertainty: float,
    market: PolymarketBinaryMarketDefinition,
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> tuple[float, float]:
    half_spread = max(config.quote_base_half_spread, uncertainty)
    bid_yes = _round_down_to_tick(_clip_probability(fair_yes - half_spread), config.quote_tick)
    ask_yes = _round_up_to_tick(_clip_probability(fair_yes + half_spread), config.quote_tick)
    if market.best_ask_yes is not None:
        bid_yes = min(bid_yes, _round_down_to_tick(max(0.01, market.best_ask_yes - config.quote_tick), config.quote_tick))
    if market.best_bid_yes is not None:
        ask_yes = max(ask_yes, _round_up_to_tick(min(0.99, market.best_bid_yes + config.quote_tick), config.quote_tick))
    if bid_yes >= ask_yes:
        bid_yes = _round_down_to_tick(_clip_probability(fair_yes - config.quote_tick), config.quote_tick)
        ask_yes = _round_up_to_tick(_clip_probability(fair_yes + config.quote_tick), config.quote_tick)
    return round(_clip_probability(bid_yes), 4), round(_clip_probability(ask_yes), 4)


def _buy_edge_vs_ask(best_ask_yes: float | None, fair_yes: float | None) -> float | None:
    if best_ask_yes is None or fair_yes is None:
        return None
    return round(fair_yes - best_ask_yes, 6)


def _sell_edge_vs_bid(best_bid_yes: float | None, fair_yes: float | None) -> float | None:
    if best_bid_yes is None or fair_yes is None:
        return None
    return round(best_bid_yes - fair_yes, 6)


def _edge_vs_mid(market_mid_yes: float | None, fair_yes: float | None) -> float | None:
    if market_mid_yes is None or fair_yes is None:
        return None
    return round(fair_yes - market_mid_yes, 6)


def _legacy_edge_vs_bid(best_bid_yes: float | None, fair_yes: float | None) -> float | None:
    if best_bid_yes is None or fair_yes is None:
        return None
    return round(fair_yes - best_bid_yes, 6)


def _decision_side(buy_edge_vs_ask: float | None, sell_edge_vs_bid: float | None) -> FootballDecisionSide:
    buy_edge = max(buy_edge_vs_ask or 0.0, 0.0)
    sell_edge = max(sell_edge_vs_bid or 0.0, 0.0)
    if buy_edge > sell_edge and buy_edge > 0.0:
        return FootballDecisionSide.BUY_YES
    if sell_edge > 0.0:
        return FootballDecisionSide.SELL_YES
    return FootballDecisionSide.NO_TRADE


def _select_no_trade_reason(
    market: PolymarketBinaryMarketDefinition,
    consensus: ConsensusFootballProbabilities,
    match_state: FootballMatchState | None,
    recent_state_changes: tuple[FootballStateChangeType, ...],
    uncertainty: float | None,
    fair_yes: float | None,
    config: FootballPricingConfig,
) -> str | None:
    if match_state is not None and match_state.status is FootballMatchStatus.FINISHED:
        return "finished_match_state"
    if match_state is not None and match_state.status is FootballMatchStatus.SUSPENDED:
        return "suspended_match_state"
    if market.market_type is None:
        return "unsupported_market_type"
    if consensus.source_count < config.minimum_bookmaker_sources:
        return "insufficient_bookmaker_sources"
    if consensus.is_stale:
        return "stale_source_data"
    if market.best_bid_yes is None or market.best_ask_yes is None:
        return "missing_yes_book"
    spread = market.best_ask_yes - market.best_bid_yes
    if spread > config.wide_yes_spread_threshold:
        return "wide_yes_spread"
    if any(
        change in {FootballStateChangeType.RED_CARD_HOME, FootballStateChangeType.RED_CARD_AWAY}
        for change in recent_state_changes
    ):
        return "cooldown_after_red_card"
    if any(
        change in {
            FootballStateChangeType.GOAL_HOME,
            FootballStateChangeType.GOAL_AWAY,
            FootballStateChangeType.EQUALIZER,
            FootballStateChangeType.LEAD_CHANGE,
        }
        for change in recent_state_changes
    ):
        return "cooldown_after_goal"
    if uncertainty is not None and uncertainty >= config.high_uncertainty_threshold:
        return "high_uncertainty"
    if fair_yes is not None and market.best_bid_yes <= fair_yes <= market.best_ask_yes:
        return "fair_inside_spread"
    return None


def price_binary_market(
    market: PolymarketBinaryMarketDefinition,
    bookmaker_snapshots: tuple[BookmakerOneXTwoOddsSnapshot, ...],
    timestamp_utc: datetime | None = None,
    match_state: FootballMatchState | None = None,
    recent_state_changes: tuple[FootballStateChangeType, ...] = (),
    config: FootballPricingConfig = DEFAULT_FOOTBALL_PRICING_CONFIG,
) -> FootballPricedBinaryMarket:
    consensus = build_bookmaker_consensus(bookmaker_snapshots, timestamp_utc=timestamp_utc, config=config)
    uncertainty = build_uncertainty(
        consensus,
        market,
        match_state=match_state,
        recent_state_changes=recent_state_changes,
        config=config,
    )

    fair_yes: float | None
    fair_no: float | None
    quote_bid_yes: float | None
    quote_ask_yes: float | None
    if market.market_type is None:
        fair_yes = None
        fair_no = None
        quote_bid_yes = None
        quote_ask_yes = None
    else:
        fair_yes = round(binary_yes_probability(consensus.probabilities, market.market_type), 6)
        fair_no = round(1.0 - fair_yes, 6)
        quote_bid_yes, quote_ask_yes = build_candidate_quotes(fair_yes, uncertainty, market, config=config)

    market_mid_yes = round(market.market_mid_yes, 6) if market.market_mid_yes is not None else None
    buy_edge_vs_ask = _buy_edge_vs_ask(market.best_ask_yes, fair_yes)
    sell_edge_vs_bid = _sell_edge_vs_bid(market.best_bid_yes, fair_yes)
    edge_vs_mid = _edge_vs_mid(market_mid_yes, fair_yes)
    max_actionable_edge = round(max(buy_edge_vs_ask or 0.0, sell_edge_vs_bid or 0.0, 0.0), 6)
    decision_side = _decision_side(buy_edge_vs_ask, sell_edge_vs_bid)
    no_trade_reason = _select_no_trade_reason(
        market,
        consensus,
        match_state=match_state,
        recent_state_changes=recent_state_changes,
        uncertainty=uncertainty,
        fair_yes=fair_yes,
        config=config,
    )
    if no_trade_reason is not None:
        decision_side = FootballDecisionSide.NO_TRADE

    return FootballPricedBinaryMarket(
        market_type=market.market_type_label,
        fair_yes=fair_yes,
        fair_no=fair_no,
        uncertainty=uncertainty,
        market_mid_yes=market_mid_yes,
        best_bid_yes=market.best_bid_yes,
        best_ask_yes=market.best_ask_yes,
        source_overround=round(consensus.source_overround, 6),
        source_name=consensus.source_name,
        source_count=consensus.source_count,
        quote_bid_yes=quote_bid_yes,
        quote_ask_yes=quote_ask_yes,
        buy_edge_vs_ask=buy_edge_vs_ask,
        sell_edge_vs_bid=sell_edge_vs_bid,
        edge_vs_mid=edge_vs_mid,
        max_actionable_edge=max_actionable_edge,
        decision_side=decision_side,
        edge_vs_best_ask=buy_edge_vs_ask,
        edge_vs_best_bid=_legacy_edge_vs_bid(market.best_bid_yes, fair_yes),
        no_trade_reason=no_trade_reason,
    )
