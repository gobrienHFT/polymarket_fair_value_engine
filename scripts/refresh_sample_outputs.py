from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polymarket_fair_value_engine.sports.demo import run_football_demo
from polymarket_fair_value_engine.sports.pricing import load_named_football_pricing_config
from polymarket_fair_value_engine.sports.replay import run_football_replay
from polymarket_fair_value_engine.sports.sweep import load_football_sweep_config, run_football_sweep


SAMPLE_OUTPUTS_ROOT = REPO_ROOT / "docs" / "sample_outputs"
FOOTBALL_DEMO_PACK = SAMPLE_OUTPUTS_ROOT / "football_demo_reference"
FOOTBALL_REPLAY_PACK = SAMPLE_OUTPUTS_ROOT / "football_replay_reference"
FOOTBALL_SWEEP_PACK = SAMPLE_OUTPUTS_ROOT / "football_sweep_reference"

FOOTBALL_DEMO_INPUT = REPO_ROOT / "data" / "sample_football_markets.json"
FOOTBALL_REPLAY_INPUT = REPO_ROOT / "data" / "sample_football_replay.jsonl"
FOOTBALL_REPLAY_CONFIG = REPO_ROOT / "configs" / "football_strategy_baseline.json"
FOOTBALL_SWEEP_CONFIG = REPO_ROOT / "configs" / "football_sweep.json"

FOOTBALL_DEMO_RUN_ID = "football-demo-reference"
FOOTBALL_REPLAY_RUN_ID = "football-replay-reference"
FOOTBALL_SWEEP_RUN_ID = "football-sweep-reference"

FOOTBALL_DEMO_FILES = (
    "summary.json",
    "football_fair_values.csv",
    "football_edges.csv",
)
FOOTBALL_REPLAY_FILES = (
    "summary.json",
    "football_replay_quotes.csv",
    "football_markouts.csv",
    "football_calibration.csv",
    "football_state_changes.csv",
    "football_no_trade_reasons.csv",
    "football_report.md",
)
FOOTBALL_SWEEP_FILES = (
    "summary.json",
    "football_strategy_results.csv",
    "football_strategy_slices.csv",
    "football_strategy_report.md",
    "football_strategy_best.json",
    "best_strategy/summary.json",
    "best_strategy/football_replay_quotes.csv",
    "best_strategy/football_markouts.csv",
    "best_strategy/football_calibration.csv",
    "best_strategy/football_state_changes.csv",
    "best_strategy/football_no_trade_reasons.csv",
    "best_strategy/football_report.md",
)


def _repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _prepare_pack_dir(pack_dir: Path) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    for child in pack_dir.iterdir():
        if child.name == "README.md":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _copy_required_files(source_dir: Path, pack_dir: Path, relative_paths: tuple[str, ...]) -> None:
    for relative_path in relative_paths:
        source_path = source_dir / relative_path
        if not source_path.exists():
            raise FileNotFoundError(f"Missing generated artifact: {source_path}")
        destination_path = pack_dir / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)


def _sanitize_paths(payload: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(payload, dict):
        return {key: _sanitize_paths(value, replacements) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_sanitize_paths(value, replacements) for value in payload]
    if isinstance(payload, str):
        value = payload
        for old, new in replacements:
            value = value.replace(old, new)
            value = value.replace(old.replace("\\", "/"), new)
        return value.replace("\\", "/")
    return payload


def _write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _refresh_football_demo(temp_root: Path) -> dict[str, str]:
    _, output_dir, summary = run_football_demo(
        input_path=FOOTBALL_DEMO_INPUT,
        output_root=temp_root / "runs",
        run_id=FOOTBALL_DEMO_RUN_ID,
    )
    _prepare_pack_dir(FOOTBALL_DEMO_PACK)
    _copy_required_files(output_dir, FOOTBALL_DEMO_PACK, FOOTBALL_DEMO_FILES[1:])
    sanitized_summary = _sanitize_paths(
        summary,
        [
            (str(output_dir), _repo_relative(FOOTBALL_DEMO_PACK)),
        ],
    )
    _write_summary(FOOTBALL_DEMO_PACK / "summary.json", sanitized_summary)
    return {
        "pack": _repo_relative(FOOTBALL_DEMO_PACK),
        "summary": _repo_relative(FOOTBALL_DEMO_PACK / "summary.json"),
    }


def _refresh_football_replay(temp_root: Path) -> dict[str, str]:
    named_config = load_named_football_pricing_config(FOOTBALL_REPLAY_CONFIG)
    _, output_dir, summary = run_football_replay(
        input_path=FOOTBALL_REPLAY_INPUT,
        output_root=temp_root / "runs",
        run_id=FOOTBALL_REPLAY_RUN_ID,
        sample_mode=True,
        config=named_config.pricing_config,
        config_name=named_config.name,
        config_description=named_config.description,
        config_path=named_config.path,
    )
    _prepare_pack_dir(FOOTBALL_REPLAY_PACK)
    _copy_required_files(output_dir, FOOTBALL_REPLAY_PACK, FOOTBALL_REPLAY_FILES[1:])
    sanitized_summary = _sanitize_paths(
        summary,
        [
            (str(output_dir), _repo_relative(FOOTBALL_REPLAY_PACK)),
            (str(FOOTBALL_REPLAY_CONFIG), _repo_relative(FOOTBALL_REPLAY_CONFIG)),
        ],
    )
    _write_summary(FOOTBALL_REPLAY_PACK / "summary.json", sanitized_summary)
    return {
        "pack": _repo_relative(FOOTBALL_REPLAY_PACK),
        "summary": _repo_relative(FOOTBALL_REPLAY_PACK / "summary.json"),
    }


def _refresh_football_sweep(temp_root: Path) -> dict[str, str]:
    sweep_config = load_football_sweep_config(FOOTBALL_SWEEP_CONFIG)
    _, output_dir, summary = run_football_sweep(
        input_path=FOOTBALL_REPLAY_INPUT,
        output_root=temp_root / "runs",
        sweep_config=sweep_config,
        run_id=FOOTBALL_SWEEP_RUN_ID,
        sample_mode=True,
        config_path=str(FOOTBALL_SWEEP_CONFIG),
    )
    _prepare_pack_dir(FOOTBALL_SWEEP_PACK)
    _copy_required_files(output_dir, FOOTBALL_SWEEP_PACK, FOOTBALL_SWEEP_FILES[1:])
    best_strategy_output_dir = output_dir / "best_strategy"
    replacements = [
        (str(best_strategy_output_dir), _repo_relative(FOOTBALL_SWEEP_PACK / "best_strategy")),
        (str(output_dir), _repo_relative(FOOTBALL_SWEEP_PACK)),
        (str(FOOTBALL_SWEEP_CONFIG), _repo_relative(FOOTBALL_SWEEP_CONFIG)),
        (str(FOOTBALL_REPLAY_CONFIG), _repo_relative(FOOTBALL_REPLAY_CONFIG)),
    ]
    sanitized_summary = _sanitize_paths(
        summary,
        replacements,
    )
    _write_summary(FOOTBALL_SWEEP_PACK / "summary.json", sanitized_summary)
    best_strategy_json_path = output_dir / "football_strategy_best.json"
    best_strategy_payload = json.loads(best_strategy_json_path.read_text(encoding="utf-8"))
    _write_json(
        FOOTBALL_SWEEP_PACK / "football_strategy_best.json",
        _sanitize_paths(best_strategy_payload, replacements),
    )
    best_strategy_summary_path = FOOTBALL_SWEEP_PACK / "best_strategy" / "summary.json"
    best_strategy_summary = json.loads((best_strategy_output_dir / "summary.json").read_text(encoding="utf-8"))
    _write_summary(best_strategy_summary_path, _sanitize_paths(best_strategy_summary, replacements))
    return {
        "pack": _repo_relative(FOOTBALL_SWEEP_PACK),
        "summary": _repo_relative(FOOTBALL_SWEEP_PACK / "summary.json"),
    }


def refresh_sample_outputs() -> dict[str, dict[str, str]]:
    with TemporaryDirectory(prefix="pmfe_sample_outputs_") as temp_dir:
        temp_root = Path(temp_dir)
        return {
            "football_demo_reference": _refresh_football_demo(temp_root),
            "football_replay_reference": _refresh_football_replay(temp_root),
            "football_sweep_reference": _refresh_football_sweep(temp_root),
        }


def main() -> int:
    refreshed = refresh_sample_outputs()
    print("Refreshed committed football sample-output packs")
    for name, details in refreshed.items():
        print(f"- {name}: {details['pack']}")
        print(f"  summary: {details['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
