from __future__ import annotations

import math
from statistics import mean

import requests

from polymarket_fair_value_engine.data.cache import TTLCache


class CoinbasePriceClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "pmfe/0.1")
        self._candle_cache: TTLCache[list[list[float]]] = TTLCache(ttl_seconds=20)

    def get_spot(self, asset: str) -> float:
        response = self.session.get(
            f"https://api.coinbase.com/v2/prices/{asset}-USD/spot",
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return float(payload["data"]["amount"])

    def get_minute_closes(self, asset: str, lookback_minutes: int) -> list[float]:
        cache_key = f"{asset}:{lookback_minutes}"
        raw = self._candle_cache.get(cache_key)
        if raw is None:
            response = self.session.get(
                f"https://api.exchange.coinbase.com/products/{asset}-USD/candles",
                params={"granularity": 60},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            raw = payload if isinstance(payload, list) else []
            self._candle_cache.set(cache_key, raw)

        closes: list[float] = []
        for row in raw[:lookback_minutes]:
            if isinstance(row, list) and len(row) >= 5:
                closes.append(float(row[4]))
        closes.reverse()
        return closes

    def realized_vol_annualized(self, asset: str, lookback_minutes: int, fallback: float) -> tuple[float, list[float]]:
        closes = self.get_minute_closes(asset=asset, lookback_minutes=lookback_minutes)
        if len(closes) < 5:
            return fallback, closes

        returns: list[float] = []
        for prev, cur in zip(closes, closes[1:]):
            prev = max(prev, 1e-9)
            cur = max(cur, 1e-9)
            returns.append(math.log(cur / prev))

        if len(returns) < 3:
            return fallback, closes

        mu = mean(returns)
        variance = sum((value - mu) ** 2 for value in returns) / max(1, len(returns) - 1)
        sigma_per_minute = math.sqrt(max(1e-12, variance))
        annualizer = math.sqrt(365.0 * 24.0 * 60.0)
        return sigma_per_minute * annualizer, closes

