# Binary Execution Research Report

## Overview

This deterministic replay separates fair-value direction from execution quality. `fair_yes` is a replay input, not a calibration result produced here. Each scenario uses the same committed YES-book snapshots, lifecycle latencies, risk checks, and accounting rules; only execution style or named sensitivity assumptions change.

- Frames: 19 (15 valid, 4 fail-closed)
- Code version: `execution-research-v1`
- Validation: fixed synthetic replay only; no holdout or production validation claim
- Queue caveat: visible-depth depletion is a bounded proxy, not participant-level historical FIFO

## Profile Comparison

| Profile | Style | Filled | Fill rate | Resting ms | Cancelled | Expired | Races | Raw edge | Net edge | Markout coverage | Spread capture | Next adverse selection | Next signed markout | Total marked PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| conservative | passive | 4.00 | 11.4% | 2000 | 6 | 1 | 2 | 0.0617 | 0.0791 | 100.0% | -0.1033 | 0.1117 | -0.1000 | -0.4759 |
| conservative | aggressive | 7.25 | 72.5% | 1500 | 1 | 0 | 0 | 0.1050 | 0.1290 | 100.0% | -0.0183 | 0.0683 | -0.0683 | 0.8128 |
| base | passive | 9.00 | 25.7% | 2000 | 5 | 1 | 3 | 0.0488 | 0.0666 | 100.0% | -0.0675 | 0.0837 | -0.0688 | -1.1726 |
| base | aggressive | 8.00 | 80.0% | 1500 | 1 | 0 | 0 | 0.1050 | 0.1290 | 100.0% | -0.0183 | 0.0683 | -0.0683 | 0.9522 |
| aggressive | passive | 16.60 | 47.4% | 2000 | 4 | 1 | 3 | 0.0488 | 0.0666 | 100.0% | -0.0675 | 0.0837 | -0.0688 | -1.3770 |
| aggressive | aggressive | 8.00 | 80.0% | 1500 | 1 | 0 | 0 | 0.1050 | 0.1290 | 100.0% | -0.0183 | 0.0683 | -0.0683 | 0.9522 |

## Lifecycle And Validity

Orders record decision, submit, acknowledgement, resting, fill, cancel request, cancel acknowledgement, expiry, rejection, and cancel/fill race events. Invalid, stale, crossed, malformed, expired, or discontinuous frames never create a new execution order.

## Model Edge Attribution

`raw_model_edge` is the directional fair-value difference versus the decision midpoint. `net_realized_edge` is the directional fair-value difference at the execution price after the fill fee; it is an accounting decomposition, not a production alpha estimate. `latency_mid_impact` is the signed midpoint move from decision to fill, with positive values indicating movement against the selected side. `queue_ahead` and `queue_depth_adjustment` expose the visible-depth assumption; the latter is the filled/requested quantity ratio, not a claim about hidden liquidity.

| Type | Profile | Style | Side | Raw edge | Exec price | Spread cost/capture | Fees | Queue ahead | Queue/depth ratio | Latency impact | Fill / unfilled | Net realized edge |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| partial_fill | conservative | passive | BUY_YES | 0.1000 | 0.5000 | -0.1100 | 0.0008 | 2.0000 | 0.1500 | 0.1300 | 0.75 / 4.25 | 0.1190 |
| partial_fill | conservative | passive | SELL_YES | 0.0100 | 0.3700 | -0.1950 | 0.0019 | 0.0000 | 0.5000 | 0.2150 | 2.50 / 2.50 | 0.0293 |
| partial_fill | conservative | passive | BUY_YES | 0.0750 | 0.5500 | -0.0050 | 0.0008 | 6.0000 | 0.1500 | 0.0200 | 0.75 / 4.25 | 0.0889 |
| no_fill_cancelled | conservative | passive | SELL_YES | 0.0100 | n/a | n/a | n/a | 4.0000 | 0.0000 | n/a | 0.00 / 5.00 | n/a |
| no_fill_cancelled | conservative | passive | BUY_YES | 0.1150 | n/a | n/a | n/a | 0.0000 | 0.0000 | n/a | 0.00 / 5.00 | n/a |
| no_fill_cancelled | conservative | passive | BUY_YES | 0.0850 | n/a | n/a | n/a | 0.0000 | 0.0000 | n/a | 0.00 / 5.00 | n/a |
| no_fill_expired | conservative | passive | BUY_YES | 0.0700 | n/a | n/a | n/a | 0.0000 | 0.0000 | n/a | 0.00 / 5.00 | n/a |
| partial_fill | conservative | aggressive | BUY_YES | 0.1000 | 0.5400 | -0.0200 | 0.0032 | 0.0000 | 0.6000 | 0.0000 | 3.00 / 2.00 | 0.0789 |
| filled | conservative | aggressive | BUY_YES | 0.1000 | 0.5300 | -0.0150 | 0.0021 | 0.0000 | 0.4000 | 0.0050 | 2.00 / 0.00 | 0.0889 |
| partial_fill | conservative | aggressive | BUY_YES | 0.1150 | 0.4100 | -0.0200 | 0.0018 | 0.0000 | 0.4500 | 0.1250 | 2.25 / 2.75 | 0.2192 |
| risk_rejected | conservative | aggressive | BUY_YES | 0.0750 | n/a | n/a | n/a | n/a | 0.0000 | n/a | 0.00 / 5.00 | n/a |
| risk_rejected | conservative | aggressive | BUY_YES | 0.0750 | n/a | n/a | n/a | n/a | 0.0000 | n/a | 0.00 / 5.00 | n/a |

## Markout Coverage And Slices

Coverage is the share of filled attribution rows with a next valid midpoint; missing future marks remain null. Slice outputs are descriptive summaries by profile/style and edge, spread, inventory, or decision-to-fill latency bucket.

| Profile | Style | Slice | Observations | Markout coverage | Positive next rate | Avg next signed | Avg 1/3/5 markout | Avg net edge |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: |
| aggressive | aggressive | edge_bucket=0.05+ | 3 | 100.0% | 0.0000 | -0.0683 | -0.0683 / -0.1300 / -0.0667 | 0.1290 |
| aggressive | aggressive | inventory_bucket=long | 3 | 100.0% | 0.0000 | -0.0683 | -0.0683 / -0.1300 / -0.0667 | 0.1290 |
| aggressive | aggressive | latency_bucket=1500ms+ | 1 | 100.0% | 0.0000 | -0.1400 | -0.1400 / -0.1600 / -0.1650 | 0.0889 |
| aggressive | aggressive | latency_bucket=500-1500ms | 2 | 100.0% | 0.0000 | -0.0325 | -0.0325 / -0.1150 / -0.0175 | 0.1491 |
| aggressive | aggressive | spread_bucket=0.02-0.05 | 3 | 100.0% | 0.0000 | -0.0683 | -0.0683 / -0.1300 / -0.0667 | 0.1290 |
| aggressive | passive | edge_bucket=0.00-0.02 | 2 | 100.0% | 0.5000 | -0.0900 | -0.0900 / -0.2000 / -0.2175 | 0.0292 |
| aggressive | passive | edge_bucket=0.05+ | 2 | 100.0% | 0.5000 | -0.0475 | -0.0475 / -0.0450 / 0.0650 | 0.1039 |
| aggressive | passive | inventory_bucket=long | 1 | 100.0% | 0.0000 | -0.1300 | -0.1300 / -0.1500 / 0.0650 | 0.1190 |
| aggressive | passive | inventory_bucket=short | 3 | 100.0% | 0.6667 | -0.0483 | -0.0483 / -0.1133 / -0.2175 | 0.0491 |
| aggressive | passive | latency_bucket=1500ms+ | 4 | 100.0% | 0.5000 | -0.0688 | -0.0688 / -0.1225 / -0.1233 | 0.0666 |
| aggressive | passive | spread_bucket=0.02-0.05 | 4 | 100.0% | 0.5000 | -0.0688 | -0.0688 / -0.1225 / -0.1233 | 0.0666 |
| base | aggressive | edge_bucket=0.05+ | 3 | 100.0% | 0.0000 | -0.0683 | -0.0683 / -0.1300 / -0.0667 | 0.1290 |
| base | aggressive | inventory_bucket=long | 3 | 100.0% | 0.0000 | -0.0683 | -0.0683 / -0.1300 / -0.0667 | 0.1290 |
| base | aggressive | latency_bucket=1500ms+ | 1 | 100.0% | 0.0000 | -0.1400 | -0.1400 / -0.1600 / -0.1650 | 0.0889 |
| base | aggressive | latency_bucket=500-1500ms | 2 | 100.0% | 0.0000 | -0.0325 | -0.0325 / -0.1150 / -0.0175 | 0.1491 |
| base | aggressive | spread_bucket=0.02-0.05 | 3 | 100.0% | 0.0000 | -0.0683 | -0.0683 / -0.1300 / -0.0667 | 0.1290 |
| base | passive | edge_bucket=0.00-0.02 | 2 | 100.0% | 0.5000 | -0.0900 | -0.0900 / -0.2000 / -0.2175 | 0.0292 |
| base | passive | edge_bucket=0.05+ | 2 | 100.0% | 0.5000 | -0.0475 | -0.0475 / -0.0450 / 0.0650 | 0.1039 |
| base | passive | inventory_bucket=long | 2 | 100.0% | 0.5000 | -0.0525 | -0.0525 / -0.1675 / -0.0650 | 0.0741 |
| base | passive | inventory_bucket=short | 2 | 100.0% | 0.5000 | -0.0850 | -0.0850 / -0.0775 / -0.2400 | 0.0591 |

## Passive And Aggressive Read

- Passive execution can capture spread but depends on queue-ahead, visible-depth depletion, expiry, and cancel/fill races; a positive raw edge can still produce a negative signed markout or no fill.
- Aggressive execution increases participation and pays the opposing quote; it is only defensible here when the raw edge survives the spread and fee assumptions. The profile table and attribution rows show that trade-off on this bounded sample, not a universal execution rule.

## Sensitivity Matrix

The matrix is one-factor-at-a-time around a fixed baseline. It varies fair-value edge, spread, book imbalance, visible depth, queue-ahead fraction, passive participation, end-to-end order latency, execution profile, initial inventory, and fees. Price movement is evaluated through signed markouts rather than tuned as a hidden volatility parameter. This is a tooling and assumption-sensitivity exercise, not a profitability validation.
Assessment rule: a row is labelled `assumption_sensitive` when its next signed markout changes by at least 0.01, fill rate by at least 0.10, or marked PnL by at least 0.50 versus baseline; otherwise it is `stable_on_this_sample`.

| Dimension | Value | Style | Fill rate | Next signed markout | Total marked PnL | Assessment |
| --- | --- | --- | ---: | ---: | ---: | --- |
| baseline | default | passive | 0.2571 | -0.0688 | -1.1726 | baseline |
| fair_value_edge_offset | -0.01 | passive | 0.2571 | -0.0688 | -1.1726 | stable_on_this_sample |
| fair_value_edge_offset | 0.02 | passive | 0.1071 | -0.0267 | 0.4463 | assumption_sensitive |
| spread | 0.02 | passive | 0.2000 | -0.1583 | -1.0556 | assumption_sensitive |
| spread | 0.06 | passive | 0.2250 | -0.0933 | -1.5023 | assumption_sensitive |
| book_imbalance | -0.5 | passive | 0.4359 | -0.0688 | -0.8724 | assumption_sensitive |
| book_imbalance | 0.5 | passive | 0.3625 | -0.0688 | -0.9113 | assumption_sensitive |
| visible_depth_multiplier | 0.5 | passive | 0.1286 | -0.0688 | -0.5863 | assumption_sensitive |
| visible_depth_multiplier | 2.0 | passive | 0.3714 | -0.0688 | -1.1416 | assumption_sensitive |
| latency_ms | 0 | passive | 0.0429 | -0.1300 | 0.1635 | assumption_sensitive |
| latency_ms | 750 | passive | 0.0429 | -0.1300 | 0.1635 | assumption_sensitive |
| execution_profile | conservative | passive | 0.1143 | -0.1000 | -0.4759 | assumption_sensitive |
| execution_profile | base | passive | 0.2571 | -0.0688 | -1.1726 | stable_on_this_sample |
| execution_profile | aggressive | passive | 0.4743 | -0.0688 | -1.3770 | assumption_sensitive |
| queue_ahead_fraction | 1.0 | passive | 0.2286 | -0.1000 | -0.9518 | assumption_sensitive |
| queue_ahead_fraction | 0.5 | passive | 0.2571 | -0.0688 | -1.1726 | stable_on_this_sample |
| queue_ahead_fraction | 0.1 | passive | 0.3143 | -0.0688 | -1.2786 | stable_on_this_sample |
| passive_fill_fraction | 0.25 | passive | 0.1286 | -0.0688 | -0.5863 | assumption_sensitive |
| passive_fill_fraction | 0.5 | passive | 0.2571 | -0.0688 | -1.1726 | stable_on_this_sample |
| passive_fill_fraction | 1.0 | passive | 0.3714 | -0.0688 | -1.1416 | assumption_sensitive |
| initial_inventory_yes | -5.0 | passive | 0.2571 | -0.0688 | -1.7226 | assumption_sensitive |
| initial_inventory_yes | 5.0 | passive | 0.2571 | -0.0688 | -0.6226 | assumption_sensitive |
| fee_bps | 0.0 | passive | 0.2571 | -0.0688 | -1.1650 | stable_on_this_sample |
| fee_bps | 50.0 | passive | 0.2571 | -0.0688 | -1.1841 | stable_on_this_sample |

## Claims And Non-Claims

- Claims supported by this artifact: fair-value direction can be evaluated separately from spread cost, visible depth, latency, fee drag, inventory, fills, and markouts under explicit assumptions.
- Non-claims: no live football execution, no recorded public evidence pack, no hidden liquidity, no participant-level FIFO reconstruction, no historical fill truth from public snapshots, no latency advantage, and no production alpha claim.
