# Binary Execution Casebook

This casebook is generated from the committed execution replay. It follows one baseline passive scenario from raw book state through fair value, risk, lifecycle, fill/no-fill, markout, and accounting.

## Case 1: Actionable Edge

- Decision: `BUY_YES` under `base/passive`.
- Fair YES: `0.6200`; decision midpoint: `0.5200`; fill price: `0.5000`; size: `1.50`.
- Risk: approved within configured position and notional limits; order `base-passive-order-0001` is fully or partially audited in `execution_lifecycle_events.csv`.
- Execution: `visible_depth_depletion` with fee `0.001500` and spread capture `0.020000`.
- Evaluation: next valid midpoint `0.37` and signed next markout `-0.13`.

## Case 2: Fail-Closed State

- Source row `5` is classified `crossed` with reasons `crossed`. It produces a `NO_TRADE` decision and cannot submit an order.

## Baseline Outcome

The selected scenario finished with `9.00` filled contracts, `25.7%` fill rate, `0.007630` fees, position `-3.00`, and marked PnL `-1.172630`. These are sample-path accounting outputs, not a production estimate.

## Read With

- `execution_replay_validity.csv` for input-state classification
- `execution_decisions.csv` for fair value, edge, microstructure, and risk decisions
- `execution_lifecycle_events.csv` for every order transition
- `execution_fills.csv`, `execution_markouts.csv`, and `execution_account.csv` for post-trade evaluation
