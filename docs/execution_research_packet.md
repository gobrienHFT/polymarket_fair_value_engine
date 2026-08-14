# Execution Research Review Packet

## Scope

This packet is a compact route through the repo's fair-value-to-execution evidence. It uses only the committed execution-research pack generated from `data/sample_execution_replay.jsonl` and `configs/execution_research.json`. The input is synthetic and bounded so every result is deterministic and inspectable.

## Canonical Refresh

After installing the editable package, the single reviewer refresh command is:

```bash
python scripts/refresh_execution_research.py
```

The script regenerates the committed reference pack, copies the top-level casebook, and runs the committed-artifact verifier. The optional direct CLI form is useful for a temporary run, but is not the canonical reviewer path.

## 60-Second Path

1. Open the [execution reference pack](sample_outputs/execution_research_reference/README.md).
2. Read the [execution report](sample_outputs/execution_research_reference/execution_report.md).
3. Read the [execution casebook](execution_casebook.md) for five bounded decisions traced from book state to lifecycle outcome and markout.
4. Inspect [execution attribution](sample_outputs/execution_research_reference/execution_attribution.csv) to see raw model edge, execution cost, latency impact, fill ratio, fees, inventory, and net realized edge together.

The key separation is deliberate: fair value supplies direction, while execution quality is measured through spread paid or captured, visible depth, latency, fills, fees, inventory, adverse selection, and signed post-fill markouts. The harness consumes `fair_yes`; it does not claim to calibrate that probability. Football fair-value calibration remains in the football replay artifacts.

## Attribution Definitions

- `raw_model_edge` is the directional fair-value difference versus the decision midpoint.
- `spread_paid_or_captured` is the directional difference between the fill-time midpoint and execution price.
- `latency_mid_impact` is the signed midpoint move from decision to fill; positive values indicate movement against the selected side.
- `queue_depth_adjustment` is the filled/requested quantity ratio under the visible-depth proxy.
- `net_realized_edge` is the directional fair-value difference at execution after fee per contract.
- `markout_1`, `markout_3`, and `markout_5` are signed future midpoint changes from the fill price at the next valid snapshot and configured horizons.

These quantities answer different questions. A positive fair-to-fill edge can coexist with a negative post-fill markout; neither number is a production profitability claim.

## 5-Minute Path

1. Read [execution decisions](sample_outputs/execution_research_reference/execution_decisions.csv) to see fair value, midpoint, bid/ask, spread, depth imbalance, microprice, decision side, and risk result together.
2. Compare [profile results](sample_outputs/execution_research_reference/execution_profile_results.csv) across passive/aggressive styles and conservative/base/aggressive sensitivity assumptions.
3. Trace [orders](sample_outputs/execution_research_reference/execution_orders.csv), [fills](sample_outputs/execution_research_reference/execution_fills.csv), and [lifecycle events](sample_outputs/execution_research_reference/execution_lifecycle_events.csv).
4. Read [markouts](sample_outputs/execution_research_reference/execution_markouts.csv) and [markout slices](sample_outputs/execution_research_reference/execution_markout_slices.csv) for signed post-fill movement, coverage, and edge/spread/inventory/latency breakdowns.
5. Read [account snapshots](sample_outputs/execution_research_reference/execution_account.csv) for cash, position, realized PnL, unrealized PnL, fees, and marked total PnL.
6. Inspect the [experiment matrix](sample_outputs/execution_research_reference/execution_experiment_matrix.csv) for one-factor changes in edge, spread, visible depth, queue-ahead, participation, latency, execution profile, inventory, and fees.

## Claim And Non-Claim Matrix

| Area | Supported by this repo | Boundary |
| --- | --- | --- |
| Fair value to execution | Yes, under explicit replay inputs and assumptions | Does not establish a live trading edge |
| Live football execution | No | BTC remains the only live-capable path |
| Queue realism | Visible-depth depletion proxy | No participant-level historical FIFO |
| Hidden liquidity | No | Public snapshots do not reveal it |
| Historical fill truth | No | Synthetic replay fills are assumption-sensitive |
| Latency realism | Parameterized submit, acknowledgement, and cancel delays | Not a venue measurement |
| Recorded public evidence | Not included | Available public data is not sufficient here to bind historical depth, fair-value inputs, and provenance deterministically |
| Profitability | Accounting and markouts are reported | No production alpha claim |

Football fair-value calibration remains a separate offline workflow. The execution harness is intentionally binary-market and microstructure-focused; it does not broaden football into live trading.
