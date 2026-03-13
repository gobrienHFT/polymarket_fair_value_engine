from __future__ import annotations

import math


def compute_uncertainty_buffer(
    annualized_vol: float,
    seconds_to_expiry: float,
    market_spread: float,
    multiplier: float,
) -> float:
    horizon_years = max(seconds_to_expiry, 1.0) / (365.0 * 24.0 * 3600.0)
    vol_component = annualized_vol * math.sqrt(horizon_years)
    spread_component = market_spread / 2.0
    return max(0.005, min(0.20, multiplier * (vol_component + spread_component)))


def blend_probability(model_probability: float, market_probability: float | None, weight: float) -> float:
    if market_probability is None:
        return model_probability
    weight = max(0.0, min(1.0, weight))
    return ((1.0 - weight) * model_probability) + (weight * market_probability)

