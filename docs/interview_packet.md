# Execution Research Packet

## Scope

This packet is a compact route through the repo's fair-value-to-execution evidence. It uses only the committed execution-research pack generated from `data/sample_execution_replay.jsonl` and `configs/execution_research.json`. The input is synthetic and bounded so every result is deterministic and inspectable.

## 60-Second Path

1. Open the [execution reference pack](sample_outputs/execution_research_reference/README.md).
2. Read the [execution report](sample_outputs/execution_research_reference/execution_report.md).
3. Read the [execution casebook](execution_casebook.md) for one decision traced from book state to markout and PnL.
4. Inspect [execution replay validity](sample_outputs/execution_research_reference/execution_replay_validity.csv) and [lifecycle events](sample_outputs/execution_research_reference/execution_lifecycle_events.csv).

The key separation is deliberate: fair value supplies direction, while execution quality is measured through spread paid or captured, visible depth, latency, fills, fees, inventory, adverse selection, and signed post-fill markouts.

## 5-Minute Path

1. Read [execution decisions](sample_outputs/execution_research_reference/execution_decisions.csv) to see fair value, midpoint, bid/ask, spread, depth imbalance, microprice, decision side, and risk result together.
2. Compare [profile results](sample_outputs/execution_research_reference/execution_profile_results.csv) across passive/aggressive styles and conservative/base/aggressive fill assumptions.
3. Trace [orders](sample_outputs/execution_research_reference/execution_orders.csv), [fills](sample_outputs/execution_research_reference/execution_fills.csv), and [markouts](sample_outputs/execution_research_reference/execution_markouts.csv).
4. Read [account snapshots](sample_outputs/execution_research_reference/execution_account.csv) for cash, position, realised PnL, unrealised PnL, fees, and marked total PnL.
5. Inspect the [experiment matrix](sample_outputs/execution_research_reference/execution_experiment_matrix.csv) for one-factor changes in edge, spread, imbalance, latency, execution profile, inventory, and fees.
6. Regenerate the committed pack from a fresh clone:

   ```bash
   python -m pip install -e ".[dev]"
   python scripts/refresh_execution_research.py
   pmfe execution-research --sample --config configs/execution_research.json --run-id execution-research-check
   pmfe report --run-id execution-research-check
   ```

## Claim And Non-Claim Matrix

| Area | Supported by this repo | Boundary |
| --- | --- | --- |
| Fair value to execution | Yes, under explicit replay inputs and assumptions | Does not establish a live trading edge |
| Live football execution | No | BTC remains the only live-capable path |
| Queue realism | Visible-depth depletion proxy | No participant-level historical FIFO |
| Hidden liquidity | No | Public snapshots do not reveal it |
| Historical fill truth | No | Synthetic replay fills are assumption-sensitive |
| Latency realism | Parameterized submit, acknowledgement, and cancel delays | Not a venue measurement |
| Profitability | Accounting and markouts are reported | No production alpha claim |

Football fair-value calibration remains a separate offline workflow. The execution harness is intentionally binary-market and microstructure-focused; it does not broaden football into live trading.
