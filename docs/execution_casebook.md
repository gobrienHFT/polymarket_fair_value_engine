# Binary Execution Casebook

This casebook follows five decisions through the same execution replay. Each one starts with a fair-value discrepancy and ends with a fill, no fill, risk rejection, race, or markout. The numbers are sample-path accounting outputs, not live performance results.

## Case A: A Passive Fill Keeps Some Edge

- **At the decision:** `base/passive` `fill-000002` had fair YES `0.3600`, decision midpoint `0.3700`, raw model edge `0.0100`, and execution price `0.3900`.
- **What the replay assumes:** Half of the visible queue is ahead of the order, participation is moderate, and the fill is evaluated against the fill-time midpoint rather than the decision midpoint.
- **What happened:** `1.00` of `5.00` contracts filled. The signed next markout was `0.0250` and net realized edge was `0.0292`.
- **What it does not tell us:** The visible-depth proxy is not participant-level FIFO, hidden liquidity, or historical fill truth.

## Case B: A Passive Fill Loses The Move

- **At the decision:** `base/passive` `fill-000001` had raw model edge `0.1000`, decision midpoint `0.5200`, fill-time midpoint `0.3900`, and execution price `0.5000`.
- **What the replay assumes:** The quote waits behind the modeled queue, so visible-depth movement can change the fill before it arrives.
- **What happened:** The signed next markout was `-0.1300`; spread paid/captured was `-0.1100` and net realized edge was `0.1190`. The positive model discrepancy did not prevent an adverse post-fill move.
- **What it does not tell us:** The queue is a visible-depth proxy, not participant-level FIFO, hidden liquidity, or historical fill truth.

## Case C: Aggressive Execution Has Room

- **At the decision:** `base/aggressive` `fill-000003` had raw model edge `0.1150`, best-quote context `0.5000` / `0.5300`, and execution price `0.4100`.
- **What the replay assumes:** The order crosses the opposing quote at the configured participation fraction and pays the modeled fee.
- **What happened:** `3.00` of `5.00` contracts filled, fees were `0.0025`, and net realized edge was `0.2192`. On this path, the larger discrepancy had room to pay the immediate execution cost.
- **What it does not tell us:** The depth model is still a visible-depth proxy, not participant-level FIFO, hidden liquidity, or historical fill truth.

## Case D: Apparent Edge, No Fill

- **At the decision:** Order `base-passive-order-0007` was submitted with fair YES `0.6800`, decision midpoint `0.6100`, and raw model edge `0.0700`.
- **What the replay assumes:** Passive participation is limited by visible queue/depth and the configured expiry window; a missing market event does not become an inferred fill.
- **What happened:** The order expired as `no_fill_expired` with `5.00` contracts unfilled. The discrepancy was real in the input, but this path never converted it into an execution.
- **What it does not tell us:** A no-fill here says something about the modeled assumptions, not whether the opportunity was tradable elsewhere.

## Case E: Cancel/Fill Race

- **What the order did:** `base-passive-order-0002` emitted `submit, acknowledge, rest, cancel_request, cancel_fill_race, partial_fill, cancel_acknowledge`; the race event occurred at `2026-01-01T12:00:09+00:00`.
- **What the replay assumes:** A fill remains eligible until the cancel acknowledgement boundary, so event ordering decides whether cancellation or execution wins.
- **What happened:** The race was recorded before the fill event for `fill-000002`, and accounting retained the fill rather than silently dropping it.
- **What it does not tell us:** This is deterministic event ordering, not a venue-measured race probability or latency result.

## Fail-Closed And Risk Restraint

- Invalid state: source row `5` is classified `crossed`, so it cannot submit a new order.
- Risk rejection: `conservative/aggressive` decision `conservative-aggressive-decision-0012` stood down on `max_position` with fair YES `0.6400` and quote `0.5800`.

## Baseline Outcome

The base passive scenario finished with `9.00` filled contracts, a `25.7%` fill rate, `0.007630` in fees, position `-3.00`, and marked PnL `-1.172630`. The base aggressive scenario finished with `8.00` filled contracts and marked PnL `0.952160`. These are sample-path accounting outputs, not a production estimate.

## Follow-Up Files

- `execution_replay_validity.csv` for input-state classification
- `execution_decisions.csv` for fair value, edge, microstructure, and risk decisions
- `execution_lifecycle_events.csv` for every order transition
- `execution_attribution.csv` for model-edge to fill/PnL decomposition
- `execution_markout_slices.csv` for coverage and edge/spread/inventory/latency slices
- `execution_fills.csv`, `execution_markouts.csv`, and `execution_account.csv` for post-trade evaluation
