from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import mean

from polymarket_fair_value_engine.config import ModelConfig
from polymarket_fair_value_engine.data.external_prices import CoinbasePriceClient
from polymarket_fair_value_engine.models.base import FairValueModel
from polymarket_fair_value_engine.models.market_implied import market_mid_probability, market_spread
from polymarket_fair_value_engine.models.uncertainty import blend_probability, compute_uncertainty_buffer
from polymarket_fair_value_engine.types import FairValueEstimate, MarketState


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


class CryptoUpDownFairValueModel(FairValueModel):
    name = "crypto_updown_diffusion"

    def __init__(self, config: ModelConfig, price_client: CoinbasePriceClient) -> None:
        self.config = config
        self.price_client = price_client

    def estimate(self, state: MarketState) -> FairValueEstimate:
        now = datetime.now(timezone.utc)
        asset = state.market.asset or "BTC"
        spot = state.reference_price if state.reference_price is not None else self.price_client.get_spot(asset)
        annualized_vol = float(state.market.metadata.get("annualized_vol", 0.0))
        closes: list[float] = []
        if annualized_vol <= 0.0:
            annualized_vol, closes = self.price_client.realized_vol_annualized(
                asset=asset,
                lookback_minutes=self.config.vol_lookback_minutes,
                fallback=self.config.base_annual_vol,
            )
        else:
            closes = [float(item) for item in state.market.metadata.get("reference_closes", [])]

        returns: list[float] = []
        for prev, cur in zip(closes, closes[1:]):
            prev = max(prev, 1e-9)
            cur = max(cur, 1e-9)
            returns.append(math.log(cur / prev))

        minute_mu = float(state.market.metadata.get("minute_mu", mean(returns) if returns else 0.0))
        minute_sigma = annualized_vol / math.sqrt(365.0 * 24.0 * 60.0)
        minute_sigma = max(minute_sigma, self.config.vol_floor / math.sqrt(365.0 * 24.0 * 60.0))

        horizon_minutes = max(0.5, state.market.seconds_to_expiry(now) / 60.0)
        drift = minute_mu * horizon_minutes
        diffusion = minute_sigma * math.sqrt(horizon_minutes)
        raw_probability = _normal_cdf(drift / max(diffusion, 1e-9))

        market_mid = market_mid_probability(state)
        blended_probability = blend_probability(raw_probability, market_mid, self.config.market_blend_weight)
        p_yes = max(0.01, min(0.99, blended_probability))
        uncertainty = compute_uncertainty_buffer(
            annualized_vol=max(annualized_vol, self.config.vol_floor),
            seconds_to_expiry=state.market.seconds_to_expiry(now),
            market_spread=market_spread(state),
            multiplier=self.config.uncertainty_multiplier,
        )
        return FairValueEstimate(
            market_id=state.market.market_id,
            p_yes=p_yes,
            p_no=1.0 - p_yes,
            model_name=self.name,
            uncertainty=uncertainty,
            reference_price=spot,
            market_mid=market_mid,
            diagnostics={
                "asset": asset,
                "spot": round(spot, 4),
                "annualized_vol": round(annualized_vol, 6),
                "minute_mu": round(minute_mu, 8),
                "horizon_minutes": round(horizon_minutes, 3),
                "raw_probability": round(raw_probability, 6),
                "market_blend_weight": self.config.market_blend_weight,
                "close_count": len(closes),
            },
        )
