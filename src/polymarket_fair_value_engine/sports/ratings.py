from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from polymarket_fair_value_engine.sports.odds import OneXTwoProbabilities


@dataclass(frozen=True)
class TeamRating:
    team: str
    offense: float
    defense: float


class FootballRatingModel(ABC):
    @abstractmethod
    def one_x_two_probabilities(self, home: TeamRating, away: TeamRating) -> OneXTwoProbabilities:
        raise NotImplementedError
