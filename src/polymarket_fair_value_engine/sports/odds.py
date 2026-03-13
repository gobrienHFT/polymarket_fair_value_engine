from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ConsensusPrice:
    event_id: str
    implied_probability_home: float
    implied_probability_away: float
    source: str


class BookmakerConsensusAdapter(ABC):
    @abstractmethod
    def fetch_consensus(self, event_id: str) -> ConsensusPrice:
        raise NotImplementedError

