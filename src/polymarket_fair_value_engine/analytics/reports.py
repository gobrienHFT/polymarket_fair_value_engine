from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.analytics.fills import export_dataclasses, write_rows


ARTIFACT_FILENAMES = {
    "summary.json": "summary_json",
    "orders.csv": "orders_csv",
    "fills.csv": "fills_csv",
    "inventory.csv": "inventory_csv",
    "pnl.csv": "pnl_csv",
    "football_fair_values.csv": "football_fair_values_csv",
    "football_edges.csv": "football_edges_csv",
    "football_replay_quotes.csv": "football_replay_quotes_csv",
    "football_markouts.csv": "football_markouts_csv",
    "football_calibration.csv": "football_calibration_csv",
    "football_state_changes.csv": "football_state_changes_csv",
    "football_no_trade_reasons.csv": "football_no_trade_reasons_csv",
    "football_report.md": "football_report_md",
    "football_strategy_results.csv": "football_strategy_results_csv",
    "football_strategy_slices.csv": "football_strategy_slices_csv",
    "football_strategy_report.md": "football_strategy_report_md",
    "football_strategy_best.json": "football_strategy_best_json",
    "best_strategy/summary.json": "best_strategy_summary_json",
    "best_strategy/football_report.md": "best_strategy_report_md",
}
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass
class RunDecisionStats:
    """Reason-coded counters shared by replay and paper run summaries."""

    observations: int = 0
    priced_observations: int = 0
    skipped_observations: int = 0
    quoteable_observations: int = 0
    quotes_generated: int = 0
    quotes_approved: int = 0
    quotes_rejected: int = 0
    skip_reasons: Counter[str] = field(default_factory=Counter)
    risk_rejection_reasons: Counter[str] = field(default_factory=Counter)

    def observe(self) -> None:
        self.observations += 1

    def record_skip(self, reason: str) -> None:
        self.skipped_observations += 1
        self.skip_reasons[reason] += 1

    def record_priced(self, generated: int, approved: int, rejected_reasons: tuple[str, ...]) -> None:
        self.priced_observations += 1
        if approved > 0:
            self.quoteable_observations += 1
        self.quotes_generated += generated
        self.quotes_approved += approved
        self.quotes_rejected += len(rejected_reasons)
        for reason in rejected_reasons:
            category = reason.split(":", 1)[-1]
            self.risk_rejection_reasons[category] += 1

    def as_dict(self) -> dict[str, object]:
        return {
            "observations": self.observations,
            "priced_observations": self.priced_observations,
            "skipped_observations": self.skipped_observations,
            "quoteable_observations": self.quoteable_observations,
            "skip_reasons": dict(sorted(self.skip_reasons.items())),
            "quotes_generated": self.quotes_generated,
            "quotes_approved": self.quotes_approved,
            "quotes_rejected": self.quotes_rejected,
            "risk_rejection_reasons": dict(sorted(self.risk_rejection_reasons.items())),
        }


def validate_run_id(run_id: str) -> str:
    if run_id == "latest":
        raise ValueError("run_id 'latest' is reserved for report lookup")
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError("run_id must use only letters, numbers, '.', '_' and '-' and be at most 128 characters")
    return run_id


def create_run_directory(root: Path, run_id: str | None = None) -> tuple[str, Path]:
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    validate_run_id(run_id)
    root = root.resolve()
    path = (root / run_id).resolve()
    path.relative_to(root)
    path.mkdir(parents=True, exist_ok=True)
    return run_id, path


def write_run_report(
    output_dir: Path,
    orders: list[Any],
    fills: list[Any],
    inventory_rows: list[dict[str, Any]],
    pnl_rows: list[Any],
    summary: dict[str, Any],
) -> None:
    export_dataclasses(output_dir / "orders.csv", orders)
    export_dataclasses(output_dir / "fills.csv", fills)
    write_rows(output_dir / "inventory.csv", inventory_rows)
    export_dataclasses(output_dir / "pnl.csv", pnl_rows)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, default=str)


def run_artifacts(output_dir: Path) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for filename, key in ARTIFACT_FILENAMES.items():
        path = output_dir / filename
        if path.exists():
            artifacts[key] = str(path)
    return artifacts


def latest_run_directory(root: Path) -> Path | None:
    if not root.exists():
        return None
    directories = [entry for entry in root.iterdir() if entry.is_dir()]
    if not directories:
        return None
    return sorted(directories)[-1]


def load_summary(root: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    target = latest_run_directory(root) if run_id == "latest" else root / validate_run_id(run_id)
    if target is None or not target.exists():
        raise FileNotFoundError(f"No run directory found for {run_id}.")
    summary_path = target / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"No summary found at {summary_path}.")
    return target, json.loads(summary_path.read_text(encoding="utf-8"))
