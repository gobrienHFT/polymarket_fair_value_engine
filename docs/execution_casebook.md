# Binary Execution Casebook

This casebook is generated from the committed execution replay. It follows one baseline passive scenario from raw book state through fair value, risk, lifecycle, fill/no-fill, markout, and accounting.

## Case 1: Actionable Edge

- Raw state: source row `1`; bid/ask `0.5` / `0.54`; midpoint `0.52`; spread `0.040000000000000036`.
- Microstructure: bid depth `18.0`, ask depth `12.0`, imbalance `0.2`, microprice `0.5285714285714286`.
- Decision: `BUY_YES` under `base/passive`; fair YES `0.6200`; edge after fee `0.119`; quote `0.5000`.
- Risk: `approved`; order `base-passive-order-0001` was submitted for `5.00` contracts.
- Lifecycle: `submit, acknowledge, rest, partial_fill, cancel_request, cancel_acknowledge`.
- Execution: `visible_depth_depletion` with fee `0.001500` and spread capture `0.020000`.
- Evaluation: next valid midpoint `0.37` and signed next markout `-0.13`.

## Case 2: Fail-Closed State

- Source row `5` is classified `crossed` with reasons `crossed`. It produces a `NO_TRADE` decision and cannot submit an order.

## Case 3: No-Fill And Risk Restraint

- Order `base-passive-order-0007` reached `EXPIRED` with `5.00` contracts unfilled. The lifecycle log records acknowledgement, resting, and expiry without inventing a fill from a missing market event.

## Baseline Outcome

The selected scenario finished with `9.00` filled contracts, `25.7%` fill rate, `0.007630` fees, position `-3.00`, and marked PnL `-1.172630`. These are sample-path accounting outputs, not a production estimate.

## Read With

- `execution_replay_validity.csv` for input-state classification
- `execution_decisions.csv` for fair value, edge, microstructure, and risk decisions
- `execution_lifecycle_events.csv` for every order transition
- `execution_fills.csv`, `execution_markouts.csv`, and `execution_account.csv` for post-trade evaluation
