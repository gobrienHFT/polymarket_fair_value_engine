from __future__ import annotations

from datetime import datetime, timezone

from polymarket_fair_value_engine.data.gamma import GammaClient
from polymarket_fair_value_engine.markets.filters import market_within_expiry_window
from polymarket_fair_value_engine.markets.normalize import normalize_gamma_market
from polymarket_fair_value_engine.types import NormalizedMarket


class MarketDiscoveryService:
    def __init__(self, gamma_client: GammaClient) -> None:
        self.gamma_client = gamma_client

    def discover_crypto_updown(
        self,
        series: str,
        probe_intervals: int,
        max_minutes_to_expiry: int,
        now: datetime | None = None,
    ) -> list[NormalizedMarket]:
        now = now or datetime.now(timezone.utc)
        base_ts = int(now.timestamp() // 300 * 300)

        seen: set[str] = set()
        results: list[NormalizedMarket] = []
        for step in range(-probe_intervals, probe_intervals + 1):
            slug = f"{series}-{base_ts + (step * 300)}"
            if slug in seen:
                continue
            seen.add(slug)
            for raw in self.gamma_client.get_market_by_slug(slug):
                market = normalize_gamma_market(raw)
                if market is None:
                    continue
                if not market_within_expiry_window(market, now=now, max_minutes_to_expiry=max_minutes_to_expiry):
                    continue
                if market.market_id not in {item.market_id for item in results}:
                    results.append(market)

        results.sort(key=lambda item: item.end_ts)
        return results

