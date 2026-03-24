#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/.." && pwd)"
RUN_ID="${1:-sample-demo}"

cd "${REPO_ROOT}"

python -m pip install -e ".[dev]"
pytest -q
BACKTEST_JSON="$(pmfe backtest --sample --run-id "${RUN_ID}")"
printf '%s\n' "${BACKTEST_JSON}"

REPORT_JSON="$(pmfe report --run-id "${RUN_ID}")"
printf '%s\n' "${REPORT_JSON}"

OUTPUT_DIR="$(printf '%s\n' "${REPORT_JSON}" | python -c "import json, sys; print(json.load(sys.stdin)['output_dir'])")"
printf 'Output directory: %s\n' "${OUTPUT_DIR}"
