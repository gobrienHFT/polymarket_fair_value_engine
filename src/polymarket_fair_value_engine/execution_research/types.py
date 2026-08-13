from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import isfinite

from polymarket_fair_value_engine.types import BookLevel


class MarketValidity(str, Enum):
    VALID = "valid"
    MALFORMED = "malformed"
    CROSSED = "crossed"
    STALE = "stale"
    DISCONTINUOUS = "discontinuous"
    EXPIRED = "expired"


class ExecutionStyle(str, Enum):
    PASSIVE = "passive"
    AGGRESSIVE = "aggressive"


class DecisionSide(str, Enum):
    BUY_YES = "BUY_YES"
    SELL_YES = "SELL_YES"
    NO_TRADE = "NO_TRADE"


class LifecycleStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESTING = "RESTING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class LifecycleEventType(str, Enum):
    DECISION = "decision"
    RISK_CHECK = "risk_check"
    SUBMIT = "submit"
    ACKNOWLEDGE = "acknowledge"
    REST = "rest"
    PARTIAL_FILL = "partial_fill"
    FILL = "fill"
    CANCEL_REQUEST = "cancel_request"
    CANCEL_ACKNOWLEDGE = "cancel_acknowledge"
    CANCEL_FILL_RACE = "cancel_fill_race"
    REJECT = "reject"
    EXPIRE = "expire"


def _require_text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty")


def _require_number(value: float, name: str, *, minimum: float | None = None, maximum: float | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and numeric > maximum:
        raise ValueError(f"{name} must be <= {maximum}")


@dataclass(frozen=True)
class ExecutionProfileConfig:
    name: str
    description: str
    queue_ahead_fraction: float
    passive_fill_fraction: float
    aggressive_fill_fraction: float

    def __post_init__(self) -> None:
        _require_text(self.name, "profile name")
        _require_text(self.description, "profile description")
        _require_number(self.queue_ahead_fraction, "queue_ahead_fraction", minimum=0.0, maximum=1.0)
        _require_number(self.passive_fill_fraction, "passive_fill_fraction", minimum=0.0, maximum=1.0)
        _require_number(self.aggressive_fill_fraction, "aggressive_fill_fraction", minimum=0.0, maximum=1.0)


@dataclass(frozen=True)
class ExecutionResearchConfig:
    code_version: str
    stale_after_seconds: float
    submit_latency_ms: int
    ack_latency_ms: int
    cancel_latency_ms: int
    order_expiry_seconds: float
    order_size: float
    min_edge: float
    fee_bps: float
    max_position: float
    max_order_notional: float
    starting_cash: float
    markout_horizons: tuple[int, ...]
    profiles: tuple[ExecutionProfileConfig, ...]
    edge_offsets: tuple[float, ...]
    spread_values: tuple[float, ...]
    imbalance_values: tuple[float, ...]
    latency_values_ms: tuple[int, ...]
    inventory_values: tuple[float, ...]
    fee_values_bps: tuple[float, ...]

    def __post_init__(self) -> None:
        _require_text(self.code_version, "code_version")
        _require_number(self.stale_after_seconds, "stale_after_seconds", minimum=0.0)
        for name in ("submit_latency_ms", "ack_latency_ms", "cancel_latency_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be an integer >= 0")
        _require_number(self.order_expiry_seconds, "order_expiry_seconds", minimum=0.0)
        _require_number(self.order_size, "order_size", minimum=1e-12)
        _require_number(self.min_edge, "min_edge", minimum=0.0, maximum=1.0)
        _require_number(self.fee_bps, "fee_bps", minimum=0.0)
        _require_number(self.max_position, "max_position", minimum=1e-12)
        _require_number(self.max_order_notional, "max_order_notional", minimum=1e-12)
        _require_number(self.starting_cash, "starting_cash", minimum=0.0)
        if not self.markout_horizons or any(isinstance(h, bool) or not isinstance(h, int) or h <= 0 for h in self.markout_horizons):
            raise ValueError("markout_horizons must contain positive integers")
        if not self.profiles:
            raise ValueError("at least one execution profile is required")
        names = [profile.name for profile in self.profiles]
        if len(set(names)) != len(names):
            raise ValueError("execution profile names must be unique")
        for values_name in ("edge_offsets", "spread_values", "imbalance_values", "latency_values_ms", "inventory_values", "fee_values_bps"):
            if not getattr(self, values_name):
                raise ValueError(f"{values_name} must not be empty")
        for values_name in ("edge_offsets", "spread_values", "imbalance_values", "inventory_values", "fee_values_bps"):
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)) for value in getattr(self, values_name)):
                raise ValueError(f"{values_name} must contain finite numbers")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in self.latency_values_ms):
            raise ValueError("latency_values_ms must contain integers >= 0")


@dataclass(frozen=True)
class ClobSnapshot:
    market_id: str
    yes_token_id: str
    timestamp: datetime | None
    source_timestamp: datetime | None
    sequence: int | None
    bids: tuple[BookLevel, ...]
    asks: tuple[BookLevel, ...]
    validity: MarketValidity
    validity_reasons: tuple[str, ...]
    source_row: int

    def __post_init__(self) -> None:
        _require_text(self.market_id, "market_id")
        _require_text(self.yes_token_id, "yes_token_id")
        if self.source_row < 1:
            raise ValueError("source_row must be positive")

    @property
    def best_bid(self) -> BookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> BookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def mid(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid.price + self.best_ask.price) / 2.0

    @property
    def spread(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask.price - self.best_bid.price

    @property
    def bid_depth(self) -> float:
        return sum(level.size for level in self.bids)

    @property
    def ask_depth(self) -> float:
        return sum(level.size for level in self.asks)

    @property
    def depth_imbalance(self) -> float | None:
        total = self.bid_depth + self.ask_depth
        if total <= 0.0:
            return None
        return (self.bid_depth - self.ask_depth) / total

    @property
    def microprice(self) -> float | None:
        if self.best_bid is None or self.best_ask is None:
            return None
        top_depth = self.best_bid.size + self.best_ask.size
        if top_depth <= 0.0:
            return None
        return (self.best_ask.price * self.best_bid.size + self.best_bid.price * self.best_ask.size) / top_depth


@dataclass(frozen=True)
class ReplayFrame:
    snapshot: ClobSnapshot
    fair_yes: float | None
    settlement_yes: bool | None
    expires_at: datetime | None


@dataclass
class ResearchOrder:
    order_id: str
    decision_id: str
    market_id: str
    profile_name: str
    style: ExecutionStyle
    side: DecisionSide
    price: float
    size: float
    remaining_size: float
    status: LifecycleStatus
    decision_timestamp: datetime
    submit_timestamp: datetime
    acknowledge_timestamp: datetime
    expiry_timestamp: datetime
    fair_yes: float
    mid_yes: float
    edge_after_fee: float
    queue_ahead: float = 0.0
    last_queue_depth: float = 0.0
    cancel_request_timestamp: datetime | None = None
    cancel_acknowledge_timestamp: datetime | None = None
    filled_size: float = 0.0
    fees_paid: float = 0.0
    first_rest_timestamp: datetime | None = None
    last_update_timestamp: datetime | None = None
    reject_reason: str | None = None


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: str
    event_type: LifecycleEventType
    timestamp: datetime
    order_id: str | None
    decision_id: str | None
    profile_name: str
    style: ExecutionStyle
    side: DecisionSide | None
    price: float | None
    size: float | None
    detail: str


@dataclass(frozen=True)
class ResearchFill:
    fill_id: str
    order_id: str
    decision_id: str
    profile_name: str
    style: ExecutionStyle
    side: DecisionSide
    timestamp: datetime
    price: float
    size: float
    fee: float
    fair_yes: float
    mid_yes: float
    spread: float
    depth_imbalance: float | None
    microprice: float | None
    fill_reason: str


@dataclass(frozen=True)
class MarkoutRow:
    fill_id: str
    order_id: str
    profile_name: str
    style: ExecutionStyle
    side: DecisionSide
    fill_timestamp: datetime
    fill_price: float
    fee: float
    current_mid_yes: float
    fair_yes: float
    spread_paid_or_captured: float
    next_snapshot_mid_yes: float | None
    next_snapshot_signed_markout: float | None
    horizon_markouts: dict[str, float | None]
    eventual_settlement_yes: bool | None
    eventual_signed_markout: float | None


@dataclass(frozen=True)
class DecisionRow:
    decision_id: str
    frame_row: int
    timestamp: datetime | None
    market_id: str
    profile_name: str
    style: ExecutionStyle
    data_validity: MarketValidity
    validity_reasons: tuple[str, ...]
    fair_yes: float | None
    market_mid_yes: float | None
    best_bid_yes: float | None
    best_ask_yes: float | None
    spread: float | None
    bid_depth: float
    ask_depth: float
    depth_imbalance: float | None
    microprice: float | None
    decision: DecisionSide
    decision_edge_after_fee: float | None
    decision_price: float | None
    risk_result: str
    no_trade_reason: str | None
    order_id: str | None


@dataclass(frozen=True)
class AccountSnapshot:
    timestamp: datetime
    profile_name: str
    style: ExecutionStyle
    market_id: str
    position_yes: float
    cash: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    mark_yes: float | None


@dataclass(frozen=True)
class ProfileResult:
    profile_name: str
    profile_description: str
    style: ExecutionStyle
    decisions: int
    valid_frames: int
    invalid_frames: int
    quoteable_decisions: int
    no_trade_decisions: int
    risk_rejections: int
    orders_submitted: int
    orders_acknowledged: int
    orders_filled: int
    partial_fills: int
    total_order_size: float
    filled_size: float
    fill_rate: float
    cancelled_orders: int
    expired_orders: int
    cancel_fill_races: int
    average_time_resting_ms: float | None
    average_spread_paid_or_captured: float | None
    total_fees: float
    final_position_yes: float
    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float
    average_next_signed_markout: float | None
    average_signed_markout_by_horizon: dict[str, float | None]
    average_spread: float | None
    average_depth_imbalance: float | None
    average_microprice_delta: float | None
    invalid_reason_counts: dict[str, int]
    notes: str


@dataclass(frozen=True)
class SimulationOutput:
    result: ProfileResult
    decisions: list[DecisionRow] = field(default_factory=list)
    orders: list[ResearchOrder] = field(default_factory=list)
    events: list[LifecycleEvent] = field(default_factory=list)
    fills: list[ResearchFill] = field(default_factory=list)
    markouts: list[MarkoutRow] = field(default_factory=list)
    account_snapshots: list[AccountSnapshot] = field(default_factory=list)
