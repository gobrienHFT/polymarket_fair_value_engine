from __future__ import annotations

from abc import ABC, abstractmethod

from polymarket_fair_value_engine.risk.inventory import InventoryPosition
from polymarket_fair_value_engine.types import FairValueEstimate, MarketState, StrategyDecision


class Strategy(ABC):
    name = "base"

    @abstractmethod
    def evaluate(
        self,
        state: MarketState,
        fair_value: FairValueEstimate,
        inventory_position: InventoryPosition,
    ) -> StrategyDecision:
        raise NotImplementedError

