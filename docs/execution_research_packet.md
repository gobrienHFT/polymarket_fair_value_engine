# Binary Market Execution Research

## Research Question

The question here is simple: how much of a probabilistic fair-value discrepancy remains executable once a decision meets a binary order book? I keep the model input separate from the execution process, then measure what spread, visible depth, queue uncertainty, latency, fees, inventory, fills, and adverse selection do to it.

## Study Design

The harness takes `fair_yes` values from `data/sample_execution_replay.jsonl` and sends the same market states, lifecycle latencies, risk checks, and accounting rules through each execution scenario. It starts after fair value has been formed; it does not calibrate that probability.

The replay compares passive and aggressive styles under conservative, base, and aggressive visible-depth profiles. Invalid, stale, crossed, malformed, expired, or discontinuous frames fail closed. For valid frames, it records the decision, risk result, order lifecycle, fills, fees, inventory, PnL, and signed markouts.

The input is a small synthetic fixture chosen so the whole path can be reproduced. It is not a historical venue record or a production validation set.

## Reproduce The Run

After installing the editable package, regenerate the reference pack with:

```bash
python scripts/refresh_execution_research.py
```

That script regenerates `docs/sample_outputs/execution_research_reference/`, copies the top-level casebook, and checks the links and files. A direct CLI run is useful for temporary experiments; the refresh script is the stable way to recreate the published files.

## 60-Second Path

1. Read the [execution report](sample_outputs/execution_research_reference/execution_report.md) for the profile comparison and validity treatment.
2. Inspect [execution attribution](sample_outputs/execution_research_reference/execution_attribution.csv) to see raw model edge, execution price, spread cost or capture, latency impact, fees, fill ratio, and net realized edge together.
3. Trace the [execution casebook](execution_casebook.md) for passive, aggressive, no-fill, risk, and cancel/fill-race examples.

Fair value supplies direction. Execution quality determines what survives contact with the book.

## Attribution Definitions

- `raw_model_edge`: directional fair-value difference versus the decision midpoint.
- `spread_paid_or_captured`: directional difference between the fill-time midpoint and execution price.
- `latency_mid_impact`: signed midpoint move from decision to fill. Positive values indicate movement against the selected side.
- `queue_ahead`: visible quantity assumed to be ahead of the order.
- `queue_depth_adjustment`: filled quantity divided by requested quantity under the visible-depth proxy.
- `net_realized_edge`: directional fair-value difference at execution after fee per contract.
- `markout_1`, `markout_3`, and `markout_5`: signed future midpoint changes from the fill price at the configured horizons.

These fields answer different questions. A positive raw model edge can pay spread, lose value during latency, fill only partially, or receive no fill. A positive fair-to-fill accounting result can still coexist with a negative post-fill markout. The [attribution CSV](sample_outputs/execution_research_reference/execution_attribution.csv) keeps those effects visible.

## Passive And Aggressive Choices

Passive orders can capture spread but depend on queue-ahead, visible-depth depletion, participation, expiry, and cancel/fill races. Aggressive orders increase participation and pay the opposing quote. The relevant comparison is therefore conditional: does the edge survive the modeled spread, fee, and latency assumptions for the selected style?

The [profile results](sample_outputs/execution_research_reference/execution_profile_results.csv) compare those styles under the three depth assumptions. The [experiment matrix](sample_outputs/execution_research_reference/execution_experiment_matrix.csv) changes one dimension at a time, including fair-value edge, spread, imbalance, visible depth, queue-ahead, participation, latency, inventory, fees, and execution profile.

## Lifecycle And Accounting

Each submitted order is evaluated through submit, acknowledgement, resting, partial or full fill, cancel request, cancel acknowledgement, expiry, rejection, and cancel/fill-race transitions. Invalid market states cannot create a new order, and risk rejections remain distinct from no-fill outcomes.

The [lifecycle events](sample_outputs/execution_research_reference/execution_lifecycle_events.csv), [fills](sample_outputs/execution_research_reference/execution_fills.csv), and [account snapshots](sample_outputs/execution_research_reference/execution_account.csv) connect event ordering to fees, inventory, realized PnL, unrealized PnL, and marked PnL. That connection matters: a final account balance does not explain why an order made or lost money.

## Markouts And Slices

The [execution markouts](sample_outputs/execution_research_reference/execution_markouts.csv) measure signed midpoint movement after fills. The [markout slices](sample_outputs/execution_research_reference/execution_markout_slices.csv) add coverage and descriptive averages by edge, spread, inventory, and decision-to-fill latency buckets. Missing future marks remain missing rather than being filled with a favorable assumption.

The [casebook](execution_casebook.md) puts those outputs together. An apparent edge can be consumed by execution cost, remain unfilled, be rejected by risk, or mark adversely after a fill. Those outcomes belong to the stated replay assumptions; they are not observations about a venue or a live strategy.

## Reproducibility

The refresh records the input, configuration, code version, and output-file hashes in `summary.json`. The reference pack is generated from:

- input: `data/sample_execution_replay.jsonl`
- configuration: `configs/execution_research.json`
- command: `python scripts/refresh_execution_research.py`

The same engine can write temporary outputs under `runs/<run_id>/` for local work. The reference pack is the stable copy linked by the documentation.

## Limits

- the replay uses synthetic binary CLOB states rather than historical venue data
- visible-depth depletion is a queue proxy, not participant-level FIFO reconstruction
- hidden liquidity and historical fill truth are not observable from these inputs
- latency values are configured assumptions, not venue measurements
- there is no holdout split or production profitability validation
- football remains an offline fair-value and replay workflow; live football execution is not implemented
- BTC is the only end-to-end paper/live execution path

## Further Reading

- [execution reference pack](sample_outputs/execution_research_reference/README.md)
- [execution report](sample_outputs/execution_research_reference/execution_report.md)
- [execution casebook](execution_casebook.md)
- [design note](design.md)
