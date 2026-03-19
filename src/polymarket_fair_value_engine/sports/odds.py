from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class FootballOutcome(str, Enum):
    HOME = "HOME"
    DRAW = "DRAW"
    AWAY = "AWAY"


class FootballBinaryMarketType(str, Enum):
    HOME_WIN = "home_win"
    AWAY_WIN = "away_win"
    DRAW = "draw"
    HOME_OR_DRAW = "home_or_draw"
    AWAY_OR_DRAW = "away_or_draw"
    EITHER_TEAM_WINS = "either_team_wins"


@dataclass(frozen=True)
class OneXTwoProbabilities:
    home: float
    draw: float
    away: float

    def __post_init__(self) -> None:
        for name, value in (("home", self.home), ("draw", self.draw), ("away", self.away)):
            if not isfinite(value) or value < 0.0:
                raise ValueError(f"{name} probability must be finite and non-negative")

    @property
    def total(self) -> float:
        return self.home + self.draw + self.away


def _validate_decimal_odds(decimal_odds: float, label: str) -> float:
    if not isfinite(decimal_odds) or decimal_odds <= 1.0:
        raise ValueError(f"{label} decimal odds must be greater than 1.0")
    return decimal_odds


def decimal_odds_to_implied_probabilities(home_decimal: float, draw_decimal: float, away_decimal: float) -> OneXTwoProbabilities:
    return OneXTwoProbabilities(
        home=1.0 / _validate_decimal_odds(home_decimal, "home"),
        draw=1.0 / _validate_decimal_odds(draw_decimal, "draw"),
        away=1.0 / _validate_decimal_odds(away_decimal, "away"),
    )


def overround(probabilities: OneXTwoProbabilities) -> float:
    return probabilities.total - 1.0


def remove_overround_proportionally(probabilities: OneXTwoProbabilities) -> OneXTwoProbabilities:
    total = probabilities.total
    if total <= 0.0:
        raise ValueError("Cannot remove overround from zero-sum probabilities")
    return OneXTwoProbabilities(
        home=probabilities.home / total,
        draw=probabilities.draw / total,
        away=probabilities.away / total,
    )


def binary_yes_probability(probabilities: OneXTwoProbabilities, market_type: FootballBinaryMarketType) -> float:
    if market_type is FootballBinaryMarketType.HOME_WIN:
        return probabilities.home
    if market_type is FootballBinaryMarketType.AWAY_WIN:
        return probabilities.away
    if market_type is FootballBinaryMarketType.DRAW:
        return probabilities.draw
    if market_type is FootballBinaryMarketType.HOME_OR_DRAW:
        return probabilities.home + probabilities.draw
    if market_type is FootballBinaryMarketType.AWAY_OR_DRAW:
        return probabilities.away + probabilities.draw
    if market_type is FootballBinaryMarketType.EITHER_TEAM_WINS:
        return probabilities.home + probabilities.away
    raise ValueError(f"Unsupported football binary market type: {market_type}")
