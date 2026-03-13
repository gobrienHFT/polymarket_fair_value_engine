#!/usr/bin/env bash
set -euo pipefail

RUN_ID="sample-demo"

python -m pip install -e .[dev]
pytest -q
pmfe backtest --input data/sample_replay.jsonl --run-id "${RUN_ID}"
pmfe report --run-id "${RUN_ID}"
