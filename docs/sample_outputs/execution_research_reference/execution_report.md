# Binary Execution Research Report

## Overview

This deterministic replay separates fair-value direction from execution quality. Each scenario uses the same committed YES-book snapshots, lifecycle latencies, risk checks, and accounting rules; only execution style or named sensitivity assumptions change.

- Frames: 19 (15 valid, 4 fail-closed)
- Code version: `execution-research-v1`
- Queue caveat: visible-depth depletion is a bounded proxy, not participant-level historical FIFO

## Profile Comparison

| Profile | Style | Filled | Fill rate | Avg spread capture | Next signed markout | Total marked PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| conservative | passive | 4.00 | 11.4% | 0.0183 | -0.1000 | -0.4759 |
| conservative | aggressive | 7.25 | 72.5% | 0.0250 | -0.0683 | 0.8128 |
| base | passive | 9.00 | 25.7% | 0.0187 | -0.0688 | -1.1726 |
| base | aggressive | 8.00 | 80.0% | 0.0250 | -0.0683 | 0.9522 |
| aggressive | passive | 16.60 | 47.4% | 0.0187 | -0.0688 | -1.3770 |
| aggressive | aggressive | 8.00 | 80.0% | 0.0250 | -0.0683 | 0.9522 |

## Lifecycle And Validity

Orders record decision, submit, acknowledgement, resting, fill, cancel request, cancel acknowledgement, expiry, rejection, and cancel/fill race events. Invalid, stale, crossed, malformed, expired, or discontinuous frames never create a new execution order.

## Sensitivity Matrix

The matrix is one-factor-at-a-time around a fixed baseline. It varies fair-value edge, spread, depth imbalance, submit latency, execution profile, initial inventory, and fees. It is a tooling and assumption-sensitivity exercise, not a profitability validation.

| Dimension | Value | Style | Fill rate | Next signed markout | Total marked PnL | Assessment |
| --- | --- | --- | ---: | ---: | ---: | --- |
| baseline | default | passive | 0.257143 | -0.06875 | -1.17263 | baseline |
| fair_value_edge_offset | -0.01 | passive | 0.257143 | -0.06875 | -1.17263 | stable_on_this_sample |
| fair_value_edge_offset | 0.02 | passive | 0.107143 | -0.026667 | 0.446325 | assumption_sensitive |
| spread | 0.02 | passive | 0.2 | -0.158333 | -1.05564 | assumption_sensitive |
| spread | 0.06 | passive | 0.225 | -0.093333 | -1.50227 | assumption_sensitive |
| book_imbalance | -0.5 | passive | 0.435937 | -0.06875 | -0.872411 | assumption_sensitive |
| book_imbalance | 0.5 | passive | 0.3625 | -0.06875 | -0.911324 | assumption_sensitive |
| submit_latency_ms | 0 | passive | 0.257143 | -0.06875 | -1.17263 | stable_on_this_sample |
| submit_latency_ms | 750 | passive | 0.257143 | -0.06875 | -1.17263 | stable_on_this_sample |
| execution_profile | conservative | passive | 0.114286 | -0.1 | -0.475925 | assumption_sensitive |
| execution_profile | base | passive | 0.257143 | -0.06875 | -1.17263 | stable_on_this_sample |
| execution_profile | aggressive | passive | 0.474286 | -0.06875 | -1.377008 | assumption_sensitive |
| initial_inventory_yes | -5.0 | passive | 0.257143 | -0.06875 | -1.72263 | assumption_sensitive |
| initial_inventory_yes | 5.0 | passive | 0.257143 | -0.06875 | -0.62263 | assumption_sensitive |
| fee_bps | 0.0 | passive | 0.257143 | -0.06875 | -1.165 | stable_on_this_sample |
| fee_bps | 50.0 | passive | 0.257143 | -0.06875 | -1.184075 | stable_on_this_sample |

## Claims And Non-Claims

- Claims supported by this artifact: fair-value direction can be evaluated separately from spread cost, visible depth, latency, fee drag, inventory, fills, and markouts under explicit assumptions.
- Non-claims: no live football execution, no hidden liquidity, no participant-level FIFO reconstruction, no historical fill truth from public snapshots, no latency advantage, and no production alpha claim.
