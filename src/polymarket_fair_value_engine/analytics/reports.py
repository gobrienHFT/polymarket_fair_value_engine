from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from polymarket_fair_value_engine.analytics.fills import export_dataclasses, write_rows


def create_run_directory(root: Path, run_id: str | None = None) -> tuple[str, Path]:
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = root / run_id
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
    return {
        "summary_json": str(output_dir / "summary.json"),
        "orders_csv": str(output_dir / "orders.csv"),
        "fills_csv": str(output_dir / "fills.csv"),
        "inventory_csv": str(output_dir / "inventory.csv"),
        "pnl_csv": str(output_dir / "pnl.csv"),
    }


def latest_run_directory(root: Path) -> Path | None:
    if not root.exists():
        return None
    directories = [entry for entry in root.iterdir() if entry.is_dir()]
    if not directories:
        return None
    return sorted(directories)[-1]


def load_summary(root: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    target = latest_run_directory(root) if run_id == "latest" else root / run_id
    if target is None or not target.exists():
        raise FileNotFoundError(f"No run directory found for {run_id}.")
    summary_path = target / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"No summary found at {summary_path}.")
    return target, json.loads(summary_path.read_text(encoding="utf-8"))
