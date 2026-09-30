from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polymarket_fair_value_engine.execution_research.config import load_execution_research_config
from polymarket_fair_value_engine.execution_research.engine import run_execution_research


INPUT_PATH = REPO_ROOT / "data" / "sample_execution_replay.jsonl"
CONFIG_PATH = REPO_ROOT / "configs" / "execution_research.json"
PACK_DIR = REPO_ROOT / "docs" / "sample_outputs" / "execution_research_reference"
RUN_ID = "execution-research-reference"
FILES = (
    "summary.json",
    "execution_replay_validity.csv",
    "execution_decisions.csv",
    "execution_orders.csv",
    "execution_lifecycle_events.csv",
    "execution_fills.csv",
    "execution_markouts.csv",
    "execution_attribution.csv",
    "execution_markout_slices.csv",
    "execution_account.csv",
    "execution_profile_results.csv",
    "execution_experiment_matrix.csv",
    "execution_report.md",
    "execution_casebook.md",
)


def _repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _prepare_pack() -> None:
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    for child in PACK_DIR.iterdir():
        if child.name == "README.md":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _sanitize(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize(item, replacements) for item in value]
    if isinstance(value, str):
        result = value
        for old, new in replacements:
            result = result.replace(old, new).replace(old.replace("\\", "/"), new)
        return result.replace("\\", "/")
    return value


def refresh_execution_research() -> dict[str, str]:
    config, loaded_config_path, config_hash = load_execution_research_config(CONFIG_PATH)
    with TemporaryDirectory(prefix="pmfe_execution_research_") as temp_dir:
        _, output_dir, summary = run_execution_research(
            INPUT_PATH,
            Path(temp_dir) / "runs",
            config,
            config_path=loaded_config_path,
            config_hash=config_hash,
            run_id=RUN_ID,
        )
        _prepare_pack()
        for filename in FILES[1:]:
            source = output_dir / filename
            if not source.exists():
                raise FileNotFoundError(f"Generated execution artifact is missing: {source}")
            shutil.copyfile(source, PACK_DIR / filename)
        replacements = [
            (str(output_dir), _repo_relative(PACK_DIR)),
            (str(INPUT_PATH), _repo_relative(INPUT_PATH)),
            (str(CONFIG_PATH), _repo_relative(CONFIG_PATH)),
        ]
        sanitized_summary = _sanitize(summary, replacements)
        (PACK_DIR / "summary.json").write_text(json.dumps(sanitized_summary, indent=2) + "\n", encoding="utf-8")

    verifier = REPO_ROOT / "scripts" / "verify_committed_artifacts.py"
    result = subprocess.run([sys.executable, str(verifier)], cwd=REPO_ROOT, check=False)
    if result.returncode != 0:
        raise RuntimeError("Committed execution research verification failed after refresh")
    return {
        "pack": _repo_relative(PACK_DIR),
        "summary": _repo_relative(PACK_DIR / "summary.json"),
        "casebook": _repo_relative(PACK_DIR / "execution_casebook.md"),
    }


def main() -> int:
    refreshed = refresh_execution_research()
    print("Refreshed committed execution research pack")
    for key, value in refreshed.items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
