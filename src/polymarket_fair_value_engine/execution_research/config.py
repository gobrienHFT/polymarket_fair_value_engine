from __future__ import annotations

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.execution_research.types import ExecutionProfileConfig, ExecutionResearchConfig


DEFAULT_CODE_VERSION = "execution-research-v1"


def _number(payload: dict[str, Any], name: str, default: float) -> float:
    value = payload.get(name, default)
    if isinstance(value, bool):
        raise ValueError(f"{name} must be numeric")
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc


def _integer(payload: dict[str, Any], name: str, default: int) -> int:
    value = payload.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _number_list(payload: dict[str, Any], name: str, default: tuple[float, ...]) -> tuple[float, ...]:
    values = payload.get(name, default)
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"{name} must be a non-empty array")
    return tuple(_number({name: value}, name, 0.0) for value in values)


def _integer_list(payload: dict[str, Any], name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    values = payload.get(name, default)
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError(f"{name} must be a non-empty array")
    parsed: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must contain integers")
        parsed.append(value)
    return tuple(parsed)


def _load_payload(path: str | Path) -> tuple[Path, dict[str, Any], str]:
    config_path = Path(path)
    try:
        raw_text = config_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"Execution research config is invalid JSON: {config_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Execution research config must be a JSON object")
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return config_path, payload, digest


def load_execution_research_config(path: str | Path) -> tuple[ExecutionResearchConfig, Path, str]:
    config_path, payload, digest = _load_payload(path)
    profile_payloads = payload.get("profiles")
    if not isinstance(profile_payloads, list) or not profile_payloads:
        raise ValueError("profiles must be a non-empty array")
    profiles: list[ExecutionProfileConfig] = []
    for item in profile_payloads:
        if not isinstance(item, dict):
            raise ValueError("each execution profile must be a JSON object")
        profiles.append(
            ExecutionProfileConfig(
                name=str(item.get("name", "")),
                description=str(item.get("description", "")),
                queue_ahead_fraction=_number(item, "queue_ahead_fraction", 0.5),
                passive_fill_fraction=_number(item, "passive_fill_fraction", 0.5),
                aggressive_fill_fraction=_number(item, "aggressive_fill_fraction", 1.0),
            )
        )

    experiment_matrix = payload.get("experiment_matrix", {})
    if not isinstance(experiment_matrix, dict):
        raise ValueError("experiment_matrix must be a JSON object")
    horizons = _integer_list(payload, "markout_horizons", (1, 3, 5))
    config = ExecutionResearchConfig(
        code_version=str(payload.get("code_version", DEFAULT_CODE_VERSION)),
        stale_after_seconds=_number(payload, "stale_after_seconds", 5.0),
        submit_latency_ms=_integer(payload, "submit_latency_ms", 250),
        ack_latency_ms=_integer(payload, "ack_latency_ms", 250),
        cancel_latency_ms=_integer(payload, "cancel_latency_ms", 500),
        order_expiry_seconds=_number(payload, "order_expiry_seconds", 4.0),
        order_size=_number(payload, "order_size", 5.0),
        min_edge=_number(payload, "min_edge", 0.01),
        fee_bps=_number(payload, "fee_bps", 20.0),
        max_position=_number(payload, "max_position", 10.0),
        max_order_notional=_number(payload, "max_order_notional", 10.0),
        starting_cash=_number(payload, "starting_cash", 100.0),
        markout_horizons=horizons,
        profiles=tuple(profiles),
        edge_offsets=_number_list(experiment_matrix, "edge_offsets", (-0.01, 0.02)),
        spread_values=_number_list(experiment_matrix, "spread_values", (0.02, 0.06)),
        imbalance_values=_number_list(experiment_matrix, "imbalance_values", (-0.5, 0.5)),
        latency_values_ms=_integer_list(experiment_matrix, "latency_values_ms", (0, 750)),
        inventory_values=_number_list(experiment_matrix, "inventory_values", (-5.0, 5.0)),
        fee_values_bps=_number_list(experiment_matrix, "fee_values_bps", (0.0, 50.0)),
    )
    return config, config_path, digest


def config_as_dict(config: ExecutionResearchConfig) -> dict[str, Any]:
    return asdict(config)


def with_overrides(config: ExecutionResearchConfig, **overrides: Any) -> ExecutionResearchConfig:
    return replace(config, **overrides)
