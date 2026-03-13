from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class TeamRating:
    team: str
    offense: float
    defense: float


class TeamRatingModel(ABC):
    @abstractmethod
    def win_probability(self, home: TeamRating, away: TeamRating) -> float:
        raise NotImplementedError

