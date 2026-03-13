from __future__ import annotations

from abc import ABC, abstractmethod

from polymarket_fair_value_engine.types import FairValueEstimate, MarketState


class FairValueModel(ABC):
    name = "base"

    @abstractmethod
    def estimate(self, state: MarketState) -> FairValueEstimate:
        raise NotImplementedError

