from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import OrderArgs
    from py_clob_client.order_builder.constants import BUY
except Exception:  # pragma: no cover - handled at runtime when dependency is missing
    ClobClient = None
    OrderArgs = None
    BUY = None


@dataclass(frozen=True)
class MarketSnapshot:
    market_id: str
    question: str
    end_ts: float
    yes_token: str
    no_token: str
    yes_price: float
    no_price: float
    strike: float | None = None
    direction: str | None = None
    asset: str | None = None


class Polymarket5mEVBot:
    """A small 5m-market bot using volatility + quarter Kelly sizing.

    Strategy constraints:
    - Only buy outcomes priced below 0.37
    - Only place orders when expected value is positive
    - Position size is quarter Kelly
    """

    def __init__(self) -> None:
        if load_dotenv is not None:
            load_dotenv()

        self.gamma_url = os.environ.get("POLYMARKET_GAMMA_URL", "https://gamma-api.polymarket.com")
        self.clob_url = os.environ.get("POLYMARKET_CLOB_URL", "https://clob.polymarket.com")
        self.private_key = os.environ.get("POLYMARKET_PRIVATE_KEY", "") or os.environ.get("POLY_PRIVATE_KEY", "")
        self.chain_id = int(os.environ.get("POLYMARKET_CHAIN_ID", "137"))
        self.signature_type = int(os.environ.get("POLYMARKET_SIGNATURE_TYPE", "") or os.environ.get("POLY_SIGNATURE_TYPE", "0"))
        self.funder = os.environ.get("POLYMARKET_FUNDER", "") or os.environ.get("POLY_FUNDER", "")
        self.dry_run = os.environ.get("BOT_DRY_RUN", "1") == "1"
        self.bankroll_usdc = float(os.environ.get("BOT_BANKROLL_USDC", "250"))
        self.max_fraction_per_trade = float(os.environ.get("BOT_MAX_FRACTION_PER_TRADE", "0.05"))
        self.min_order_usdc = float(os.environ.get("BOT_MIN_ORDER_USDC", "5"))
        self.poll_seconds = int(os.environ.get("BOT_POLL_SECONDS", "30"))
        self.lookback = int(os.environ.get("BOT_VOL_LOOKBACK", "72"))
        self.order_price_cap = float(os.environ.get("BOT_PRICE_CAP", "0.37"))
        self.target_series_prefix = os.environ.get("BOT_TARGET_SERIES_PREFIX", "btc-updown-5m").strip()
        self.target_probe_intervals = int(os.environ.get("BOT_TARGET_PROBE_INTERVALS", "6"))
        self.max_minutes_to_expiry = int(os.environ.get("BOT_MAX_MIN_TO_EXPIRY", "10"))
        self.market_scan_pages = int(os.environ.get("BOT_MARKET_SCAN_PAGES", "20"))
        self.base_annual_vol = float(os.environ.get("BOT_BASE_ANNUAL_VOL", "0.8"))
        self.price_tick = float(os.environ.get("BOT_PRICE_TICK", "0.01"))
        self.size_tick = float(os.environ.get("BOT_SIZE_TICK", "0.1"))

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "polymarket-5m-ev-bot/1.0"})
        self.price_history: dict[str, deque[float]] = {}
        self.candle_cache: dict[str, tuple[float, list[list[float]]]] = {}

        self.client = self._build_client()

    def _build_client(self) -> Any:
        if ClobClient is None:
            raise RuntimeError(
                "py-clob-client is required to place orders. Install with: pip install py-clob-client"
            )
        if not self.private_key:
            raise RuntimeError("Set POLYMARKET_PRIVATE_KEY or POLY_PRIVATE_KEY before running the bot.")

        kwargs: dict[str, Any] = {
            "host": self.clob_url,
            "key": self.private_key,
            "chain_id": self.chain_id,
        }
        if self.signature_type:
            kwargs["signature_type"] = self.signature_type
        if self.funder:
            kwargs["funder"] = self.funder

        client = ClobClient(**kwargs)

        # Fix for common limit order failures: API creds must be derived/loaded first.
        # Some users hit auth failures if they sign orders before deriving API creds.
        creds = client.derive_api_key()
        client.set_api_creds(creds)
        return client

    @staticmethod
    def _parse_iso(ts: str) -> float:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()

    @staticmethod
    def _clip(x: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, x))

    def _quantize(self, value: float, tick: float) -> float:
        return round(math.floor(value / tick) * tick, 8)

    def _fetch_5m_markets(self) -> list[MarketSnapshot]:
        if self.target_series_prefix:
            targeted = self._fetch_target_series_markets()
            if targeted:
                return targeted

        now = time.time()
        max_expiry = now + (self.max_minutes_to_expiry * 60)
        rows: list[MarketSnapshot] = []
        cursor = "MA=="
        for _ in range(self.market_scan_pages):
            batch = self.client.get_markets(next_cursor=cursor)
            data = batch.get("data", []) if isinstance(batch, dict) else []
            if not data:
                break

            for market in data:
                if not market.get("active") or market.get("closed") or market.get("archived"):
                    continue
                if not market.get("accepting_orders", False):
                    continue

                end_date = market.get("end_date_iso")
                if not end_date:
                    continue
                end_ts = self._parse_iso(str(end_date))
                if end_ts <= now + 10 or end_ts > max_expiry:
                    continue

                question = str(market.get("question", ""))
                parsed = self._parse_crypto_contract(question)
                if parsed is None:
                    continue
                asset, direction, strike = parsed

                tokens = market.get("tokens") or []
                yes_token = ""
                no_token = ""
                yes_price = 0.0
                no_price = 0.0
                for tok in tokens:
                    outcome = str(tok.get("outcome", "")).strip().lower()
                    token_id = str(tok.get("token_id", ""))
                    price = float(tok.get("price", 0.0))
                    if outcome == "yes":
                        yes_token, yes_price = token_id, price
                    elif outcome == "no":
                        no_token, no_price = token_id, price
                if not yes_token or not no_token:
                    continue
                if not (0.0 < yes_price < 1.0 and 0.0 < no_price < 1.0):
                    continue

                rows.append(
                    MarketSnapshot(
                        market_id=str(market.get("condition_id", "")),
                        question=question,
                        end_ts=end_ts,
                        yes_token=yes_token,
                        no_token=no_token,
                        yes_price=yes_price,
                        no_price=no_price,
                        strike=strike,
                        direction=direction,
                        asset=asset,
                    )
                )

            cursor = batch.get("next_cursor", "") if isinstance(batch, dict) else ""
            if not cursor:
                break
        return rows

    def _fetch_target_series_markets(self) -> list[MarketSnapshot]:
        now = int(time.time())
        base = (now // 300) * 300
        seen: set[str] = set()
        rows: list[MarketSnapshot] = []

        for step in range(-self.target_probe_intervals, self.target_probe_intervals + 1):
            ts = base + (step * 300)
            slug = f"{self.target_series_prefix}-{ts}"
            if slug in seen:
                continue
            seen.add(slug)

            resp = self.session.get(f"{self.gamma_url}/markets", params={"slug": slug}, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if not data:
                continue

            for market in data:
                if not market.get("active") or market.get("closed") or market.get("archived"):
                    continue
                if not market.get("acceptingOrders", False):
                    continue

                end_date = market.get("endDate") or market.get("end_date") or market.get("endDateIso")
                if not end_date:
                    continue
                end_ts = self._parse_iso(str(end_date))
                if end_ts <= time.time() + 10:
                    continue

                outcomes_raw = market.get("outcomes")
                prices_raw = market.get("outcomePrices") or []
                tokens_raw = market.get("clobTokenIds") or []
                try:
                    outcomes = outcomes_raw if isinstance(outcomes_raw, list) else json.loads(str(outcomes_raw))
                    prices = prices_raw if isinstance(prices_raw, list) else json.loads(str(prices_raw))
                    tokens = tokens_raw if isinstance(tokens_raw, list) else json.loads(str(tokens_raw))
                except Exception:
                    continue
                if len(outcomes) < 2 or len(prices) < 2 or len(tokens) < 2:
                    continue

                def find_ix(name: str) -> int:
                    for i, o in enumerate(outcomes):
                        if str(o).strip().lower() == name:
                            return i
                    return -1

                up_ix = find_ix("up")
                down_ix = find_ix("down")
                if up_ix < 0 or down_ix < 0:
                    continue

                yes_price = float(prices[up_ix])
                no_price = float(prices[down_ix])
                if not (0.0 < yes_price < 1.0 and 0.0 < no_price < 1.0):
                    continue

                rows.append(
                    MarketSnapshot(
                        market_id=str(market.get("conditionId", market.get("id", ""))),
                        question=str(market.get("question", "")),
                        end_ts=end_ts,
                        yes_token=str(tokens[up_ix]),
                        no_token=str(tokens[down_ix]),
                        yes_price=yes_price,
                        no_price=no_price,
                        direction="UPDOWN",
                        asset="BTC" if self.target_series_prefix.startswith("btc-") else None,
                    )
                )

        rows.sort(key=lambda m: m.end_ts)
        return rows[:1]

    @staticmethod
    def _parse_crypto_contract(question: str) -> tuple[str, str, float] | None:
        q = question.lower()
        if "bitcoin" in q or "btc" in q:
            asset = "BTC"
        elif "ethereum" in q or " eth " in f" {q} ":
            asset = "ETH"
        elif "solana" in q or " sol " in f" {q} ":
            asset = "SOL"
        else:
            return None

        direction = None
        if " above " in q or " over " in q:
            direction = "ABOVE"
        elif " below " in q or " under " in q:
            direction = "BELOW"
        if direction is None:
            return None

        import re

        matches = re.findall(r"\$([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)", question)
        if not matches:
            matches = re.findall(r" ([0-9]{1,3}(?:,[0-9]{3}){1,}(?:\.[0-9]+)?) ", f" {question} ")
        if not matches:
            return None
        strike = float(matches[-1].replace(",", ""))
        return (asset, direction, strike)

    def _fetch_spot_usd(self, asset: str) -> float:
        pair = f"{asset}-USD"
        resp = self.session.get(f"https://api.coinbase.com/v2/prices/{pair}/spot", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return float(data["data"]["amount"])

    def _fetch_coinbase_minute_closes(self, asset: str) -> list[float]:
        now = time.time()
        cached = self.candle_cache.get(asset)
        if cached and now - cached[0] < 20:
            raw = cached[1]
        else:
            pair = f"{asset}-USD"
            resp = self.session.get(
                f"https://api.exchange.coinbase.com/products/{pair}/candles",
                params={"granularity": 60},
                timeout=12,
            )
            resp.raise_for_status()
            raw = resp.json()
            self.candle_cache[asset] = (now, raw)
        if not isinstance(raw, list):
            return []
        closes: list[float] = []
        for row in raw:
            if isinstance(row, list) and len(row) >= 5:
                closes.append(float(row[4]))
        closes.reverse()
        return closes

    def _estimate_updown_probability(self, asset: str, seconds_to_expiry: float) -> tuple[float, float]:
        closes = self._fetch_coinbase_minute_closes(asset)
        if len(closes) < 20:
            return (0.5, 0.0)

        log_returns: list[float] = []
        for i in range(1, len(closes)):
            prev = max(1e-9, closes[i - 1])
            cur = max(1e-9, closes[i])
            log_returns.append(math.log(cur / prev))
        if len(log_returns) < 10:
            return (0.5, 0.0)

        mu = sum(log_returns) / len(log_returns)
        var = sum((r - mu) ** 2 for r in log_returns) / max(1, len(log_returns) - 1)
        sigma = math.sqrt(max(1e-12, var))

        horizon_min = max(0.5, seconds_to_expiry / 60.0)
        drift = mu * horizon_min
        diffusion = sigma * math.sqrt(horizon_min)
        z = drift / max(1e-9, diffusion)
        p_up = self._normal_cdf(z)
        return (self._clip(p_up, 0.01, 0.99), sigma)

    @staticmethod
    def _normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _probability_yes_from_spot(self, market: MarketSnapshot, now_ts: float) -> tuple[float, float, float]:
        if not market.asset or not market.direction or not market.strike:
            return ((market.yes_price + (1.0 - market.no_price)) / 2.0, self.base_annual_vol, float("nan"))

        spot = self._fetch_spot_usd(market.asset)
        t_sec = max(1.0, market.end_ts - now_ts)
        t_years = t_sec / (365.0 * 24.0 * 3600.0)
        sigma = max(0.1, self.base_annual_vol)
        vol_term = sigma * math.sqrt(max(1e-12, t_years))
        d2 = (math.log(max(1e-9, spot / market.strike)) - 0.5 * sigma * sigma * t_years) / max(1e-9, vol_term)
        p_above = self._normal_cdf(d2)
        p_yes = p_above if market.direction == "ABOVE" else (1.0 - p_above)
        return (self._clip(p_yes, 0.01, 0.99), sigma, spot)

    def _estimate_probability(self, market_id: str, mid_price: float) -> tuple[float, float]:
        history = self.price_history.setdefault(market_id, deque(maxlen=self.lookback))
        history.append(mid_price)
        if len(history) < 8:
            return (mid_price, 0.0)

        vals = list(history)
        log_returns: list[float] = []
        for i in range(1, len(vals)):
            prev = max(1e-6, vals[i - 1])
            cur = max(1e-6, vals[i])
            log_returns.append(math.log(cur / prev))

        mean = sum(log_returns) / len(log_returns)
        var = sum((r - mean) ** 2 for r in log_returns) / max(1, len(log_returns) - 1)
        sigma = math.sqrt(max(1e-10, var))

        ema_fast = vals[-1]
        ema_slow = vals[-1]
        alpha_fast = 2 / (1 + 6)
        alpha_slow = 2 / (1 + 20)
        for price in vals[:-1]:
            ema_fast = alpha_fast * price + (1 - alpha_fast) * ema_fast
            ema_slow = alpha_slow * price + (1 - alpha_slow) * ema_slow

        z_signal = (ema_fast - ema_slow) / max(1e-6, sigma * vals[-1])
        adjusted = mid_price + (0.045 * z_signal)
        p_up = self._clip(adjusted, 0.01, 0.99)
        return (p_up, sigma)

    @staticmethod
    def _kelly_fraction(win_probability: float, price: float) -> float:
        # Binary payoff: pay "price" to win 1.0 if correct.
        # Full Kelly simplifies to (p - price) / (1 - price).
        if price >= 1.0:
            return 0.0
        edge = win_probability - price
        if edge <= 0:
            return 0.0
        return edge / max(1e-6, 1.0 - price)

    def _build_order_size(self, kelly_fraction: float, price: float) -> float:
        fraction = min(self.max_fraction_per_trade, max(0.0, kelly_fraction * 0.25))
        notional = self.bankroll_usdc * fraction
        if notional < self.min_order_usdc:
            return 0.0
        raw_size = notional / max(1e-8, price)
        return self._quantize(raw_size, self.size_tick)

    def _place_limit_buy(self, token_id: str, price: float, size: float) -> dict[str, Any]:
        px = self._quantize(self._clip(price, 0.01, 0.99), self.price_tick)
        sz = self._quantize(size, self.size_tick)
        if sz <= 0 or px <= 0:
            return {"skipped": True, "reason": "invalid_quantized_order"}
        if self.dry_run:
            return {
                "dry_run": True,
                "order_type": "GTC",
                "token_id": token_id,
                "price": px,
                "size": sz,
                "side": "BUY",
            }

        # Fix for previous limit-order issues:
        # 1) strict tick rounding for both price and size
        # 2) explicit good-til-cancel flag
        # 3) API creds set during client bootstrap
        order = OrderArgs(price=px, size=sz, side=BUY, token_id=token_id)
        signed = self.client.create_order(order)
        posted = self.client.post_order(signed, order_type="GTC")
        return posted if isinstance(posted, dict) else {"response": str(posted)}

    def run_once(self) -> list[dict[str, Any]]:
        markets = self._fetch_5m_markets()
        actions: list[dict[str, Any]] = []
        now_ts = time.time()
        print(f"scan_ts={datetime.now(timezone.utc).isoformat()} markets_considered={len(markets)} dry_run={self.dry_run}")

        for m in markets:
            if m.direction == "UPDOWN":
                p_yes, sigma = self._estimate_updown_probability(
                    asset=(m.asset or "BTC"),
                    seconds_to_expiry=max(1.0, m.end_ts - now_ts),
                )
                spot = float("nan")
            else:
                p_yes, sigma, spot = self._probability_yes_from_spot(m, now_ts)
            p_no = 1.0 - p_yes

            yes_ev = p_yes - m.yes_price
            no_ev = p_no - m.no_price

            candidates: list[tuple[str, float, float, str]] = []
            if m.yes_price <= self.order_price_cap and yes_ev > 0:
                candidates.append((m.yes_token, m.yes_price, p_yes, "YES"))
            if m.no_price <= self.order_price_cap and no_ev > 0:
                candidates.append((m.no_token, m.no_price, p_no, "NO"))

            if not candidates:
                continue

            token_id, price, win_prob, side_label = max(candidates, key=lambda x: x[2] - x[1])
            kelly = self._kelly_fraction(win_prob, price)
            size = self._build_order_size(kelly, price)
            if size <= 0:
                continue

            order_resp = self._place_limit_buy(token_id=token_id, price=price, size=size)
            action = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "market_id": m.market_id,
                "question": m.question,
                "picked": side_label,
                "asset": m.asset,
                "direction": m.direction,
                "strike": m.strike,
                "spot": None if math.isnan(spot) else round(spot, 4),
                "price": round(price, 4),
                "win_prob": round(win_prob, 4),
                "ev": round(win_prob - price, 4),
                "volatility": round(sigma, 6),
                "kelly_full": round(kelly, 4),
                "size": size,
                "order": order_resp,
            }
            actions.append(action)
            print(json.dumps(action))
        return actions

    def run_forever(self) -> None:
        print(f"Starting Polymarket 5m positive-EV bot... dry_run={self.dry_run}")
        while True:
            try:
                self.run_once()
            except Exception as exc:
                print(f"Loop error: {exc}")
            time.sleep(self.poll_seconds)


if __name__ == "__main__":
    bot = Polymarket5mEVBot()
    if os.environ.get("BOT_RUN_ONCE", "0") == "1":
        bot.run_once()
    else:
        bot.run_forever()
