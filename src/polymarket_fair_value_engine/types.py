from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any


class MarketFamily(str, Enum):
    CRYPTO_UPDOWN = "crypto_updown"
    SPORTS_BINARY = "sports_binary"
    MACRO_BINARY = "macro_binary"


class TokenSide(str, Enum):
    YES = "YES"
    NO = "NO"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


def _require_finite(value: float, field_name: str, *, minimum: float | None = None, maximum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    if maximum is not None and numeric > maximum:
        raise ValueError(f"{field_name} must be <= {maximum}")


def _require_timezone(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True)
class BookLevel:
    price: float
    size: float

    def __post_init__(self) -> None:
        if not isfinite(self.price) or not 0.0 <= self.price <= 1.0:
            raise ValueError("book price must be finite and within [0, 1]")
        if not isfinite(self.size) or self.size <= 0.0:
            raise ValueError("book size must be finite and greater than zero")


@dataclass(frozen=True)
class TokenOrderBook:
    token_id: str
    bids: tuple[BookLevel, ...] = ()
    asks: tuple[BookLevel, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "clob_rest"

    def __post_init__(self) -> None:
        if not self.token_id.strip():
            raise ValueError("token_id must be non-empty")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("order-book timestamp must be timezone-aware")
        object.__setattr__(self, "bids", tuple(sorted(self.bids, key=lambda level: level.price, reverse=True)))
        object.__setattr__(self, "asks", tuple(sorted(self.asks, key=lambda level: level.price)))

    @property
    def best_bid(self) -> BookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> BookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def midpoint(self) -> float | None:
        if self.best_bid and self.best_ask:
            return (self.best_bid.price + self.best_ask.price) / 2.0
        if self.best_bid:
            return self.best_bid.price
        if self.best_ask:
            return self.best_ask.price
        return None


@dataclass(frozen=True)
class NormalizedMarket:
    market_id: str
    slug: str
    question: str
    series: str
    family: MarketFamily
    asset: str | None
    end_ts: datetime
    start_ts: datetime | None = None
    yes_token_id: str = ""
    no_token_id: str = ""
    tick_size: float = 0.01
    size_tick: float = 0.1
    last_yes_price: float | None = None
    last_no_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.market_id, "market_id")
        _require_text(self.slug, "slug")
        _require_text(self.question, "question")
        _require_text(self.series, "series")
        _require_text(self.yes_token_id, "yes_token_id")
        _require_text(self.no_token_id, "no_token_id")
        _require_timezone(self.end_ts, "end_ts")
        if self.start_ts is not None:
            _require_timezone(self.start_ts, "start_ts")
            if self.start_ts > self.end_ts:
                raise ValueError("start_ts must not be after end_ts")
        _require_finite(self.tick_size, "tick_size", minimum=1e-12, maximum=1.0)
        _require_finite(self.size_tick, "size_tick", minimum=1e-12)
        if self.last_yes_price is not None:
            _require_finite(self.last_yes_price, "last_yes_price", minimum=0.0, maximum=1.0)
        if self.last_no_price is not None:
            _require_finite(self.last_no_price, "last_no_price", minimum=0.0, maximum=1.0)

    def seconds_to_expiry(self, now: datetime) -> float:
        return max(0.0, (self.end_ts - now).total_seconds())


@dataclass(frozen=True)
class MarketState:
    market: NormalizedMarket
    yes_book: TokenOrderBook | None
    no_book: TokenOrderBook | None
    observed_at: datetime
    reference_price: float | None = None
    stale: bool = False

    def __post_init__(self) -> None:
        _require_timezone(self.observed_at, "observed_at")
        if self.reference_price is not None:
            _require_finite(self.reference_price, "reference_price", minimum=0.0)

    @property
    def yes_bid(self) -> float | None:
        return self.yes_book.best_bid.price if self.yes_book and self.yes_book.best_bid else None

    @property
    def yes_ask(self) -> float | None:
        return self.yes_book.best_ask.price if self.yes_book and self.yes_book.best_ask else None

    @property
    def no_bid(self) -> float | None:
        return self.no_book.best_bid.price if self.no_book and self.no_book.best_bid else None

    @property
    def no_ask(self) -> float | None:
        return self.no_book.best_ask.price if self.no_book and self.no_book.best_ask else None

    @property
    def yes_mid(self) -> float | None:
        if self.yes_book and self.yes_book.midpoint is not None:
            return self.yes_book.midpoint
        if self.no_book and self.no_book.midpoint is not None:
            return max(0.0, min(1.0, 1.0 - self.no_book.midpoint))
        if self.market.last_yes_price is not None:
            return self.market.last_yes_price
        if self.market.last_no_price is not None:
            return max(0.0, min(1.0, 1.0 - self.market.last_no_price))
        return None

    @property
    def spread(self) -> float | None:
        if self.yes_bid is not None and self.yes_ask is not None:
            return max(0.0, self.yes_ask - self.yes_bid)
        return None


@dataclass(frozen=True)
class FairValueEstimate:
    market_id: str
    p_yes: float
    p_no: float
    model_name: str
    uncertainty: float
    reference_price: float | None
    market_mid: float | None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.market_id, "market_id")
        _require_finite(self.p_yes, "p_yes", minimum=0.0, maximum=1.0)
        _require_finite(self.p_no, "p_no", minimum=0.0, maximum=1.0)
        if abs((self.p_yes + self.p_no) - 1.0) > 1e-6:
            raise ValueError("p_yes and p_no must sum to 1")
        _require_finite(self.uncertainty, "uncertainty", minimum=0.0)
        if self.market_mid is not None:
            _require_finite(self.market_mid, "market_mid", minimum=0.0, maximum=1.0)


@dataclass(frozen=True)
class QuoteIntent:
    market_id: str
    token_id: str
    token_side: TokenSide
    side: OrderSide
    price: float
    size: float
    fair_value: float
    reference_mid: float | None
    created_at: datetime
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.market_id, "market_id")
        _require_text(self.token_id, "token_id")
        _require_text(self.reason, "reason")
        _require_finite(self.price, "price", minimum=0.0, maximum=1.0)
        _require_finite(self.size, "size", minimum=1e-12)
        _require_finite(self.fair_value, "fair_value", minimum=0.0, maximum=1.0)
        if self.reference_mid is not None:
            _require_finite(self.reference_mid, "reference_mid", minimum=0.0, maximum=1.0)
        _require_timezone(self.created_at, "created_at")


@dataclass(frozen=True)
class StrategyDecision:
    market_id: str
    fair_value: FairValueEstimate
    quotes: tuple[QuoteIntent, ...]
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ManagedOrder:
    order_id: str
    market_id: str
    token_id: str
    token_side: TokenSide
    side: OrderSide
    price: float
    size: float
    remaining_size: float
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    fair_value_at_entry: float | None = None
    mid_at_entry: float | None = None
    reason: str = ""

    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass(frozen=True)
class OrderAction:
    action: str
    desired: QuoteIntent | None = None
    existing_order_id: str | None = None
    reason: str = ""


@dataclass(frozen=True)
class FillEvent:
    fill_id: str
    order_id: str
    market_id: str
    token_id: str
    token_side: TokenSide
    side: OrderSide
    price: float
    size: float
    timestamp: datetime
    fair_value_at_order: float | None
    mid_at_order: float | None

    @property
    def notional(self) -> float:
        return self.price * self.size


@dataclass(frozen=True)
class PositionSnapshot:
    market_id: str
    yes_contracts: float
    no_contracts: float
    net_yes_exposure: float
    gross_contracts: float
    mark_price_yes: float | None
    unrealized_pnl: float


@dataclass(frozen=True)
class PnLSnapshot:
    timestamp: datetime
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    gross_exposure: float
    net_exposure: float
