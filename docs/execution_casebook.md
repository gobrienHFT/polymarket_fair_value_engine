# Binary Execution Casebook

This casebook is generated from the committed execution replay. It separates fair-value edge from fill assumptions, lifecycle outcomes, and post-fill evaluation; it is not a production performance claim.

## Case A: Passive Edge Survives

- **Observed input:** `base/passive` `fill-000002` had fair YES `0.3600`, decision midpoint `0.3700`, raw model edge `0.0100`, and execution price `0.3900`.
- **Modeling assumption:** The base passive profile uses a half-visible queue-ahead fraction and moderate visible-depth participation; the fill is evaluated at the fill-time midpoint rather than the decision midpoint.
- **Execution outcome:** It filled `1.00` of `5.00` contracts. Signed next markout was `0.0250` and net realized edge was `0.0292`.
- **Limitation:** Visible-depth replay proxy; no participant-level FIFO, hidden liquidity, or historical fill truth.

## Case B: Passive Edge Disappears

- **Observed input:** `base/passive` `fill-000001` had raw model edge `0.1000`, decision midpoint `0.5200`, fill-time midpoint `0.3900`, and execution price `0.5000`.
- **Modeling assumption:** The passive quote waits behind the modeled queue and can be affected by visible-depth movement before the fill.
- **Execution outcome:** The signed next markout was `-0.1300`; spread paid/captured was `-0.1100` and net realized edge was `0.1190`. A positive model discrepancy therefore did not guarantee benign post-fill movement.
- **Limitation:** Visible-depth replay proxy; no participant-level FIFO, hidden liquidity, or historical fill truth.

## Case C: Aggressive Execution Is Justified

- **Observed input:** `base/aggressive` `fill-000003` had raw model edge `0.1150`, best-quote context `0.5000` / `0.5300`, and execution price `0.4100`.
- **Modeling assumption:** Aggressive execution crosses the opposing quote with the configured aggressive participation fraction and pays the modeled fee.
- **Execution outcome:** It filled `3.00` of `5.00` contracts, paid `0.0025` in fees, and recorded net realized edge `0.2192`. This is a conditional example of a larger edge surviving the modeled immediate cost.
- **Limitation:** Visible-depth replay proxy; no participant-level FIFO, hidden liquidity, or historical fill truth.

## Case D: Apparent Edge Is Not Tradeable

- **Observed input:** Order `base-passive-order-0007` was submitted with fair YES `0.6800`, decision midpoint `0.6100`, and raw model edge `0.0700`.
- **Modeling assumption:** Passive participation is constrained by visible queue/depth assumptions and the configured order-expiry window; no fill is inferred from a missing market event.
- **Execution outcome:** The order outcome was `no_fill_expired` with `5.00` contracts unfilled. The apparent discrepancy remained a no-fill outcome under this modeled execution path.
- **Limitation:** No fill in this replay is evidence about the modeled assumptions, not proof that the opportunity was never tradable elsewhere.

## Case E: Cancel/Fill Race

- **Observed input:** Order `base-passive-order-0002` emitted the lifecycle sequence `submit, acknowledge, rest, cancel_request, cancel_fill_race, partial_fill, cancel_acknowledge`; the race event occurred at `2026-01-01T12:00:09+00:00`.
- **Modeling assumption:** A fill remains eligible through the configured cancel acknowledgement boundary, so event ordering determines whether cancellation or execution wins.
- **Execution outcome:** The fill/cancel race was recorded explicitly before the fill event for `fill-000002`; accounting retains the fill rather than silently dropping it.
- **Limitation:** This is deterministic replay ordering, not a venue-measured race probability or latency result.

## Fail-Closed And Risk Restraint

- Invalid state: source row `5` is classified `crossed` with reasons `crossed` and cannot submit a new order.
- Risk rejection: `conservative/aggressive` decision `conservative-aggressive-decision-0012` stood down with `max_position` at fair YES `0.6400` and quote `0.5800`.

## Baseline Outcome

The base passive scenario finished with `9.00` filled contracts, `25.7%` fill rate, `0.007630` fees, position `-3.00`, and marked PnL `-1.172630`. The base aggressive scenario finished with `8.00` filled contracts and marked PnL `0.952160`. These are sample-path accounting outputs, not a production estimate.

## Read With

- `execution_replay_validity.csv` for input-state classification
- `execution_decisions.csv` for fair value, edge, microstructure, and risk decisions
- `execution_lifecycle_events.csv` for every order transition
- `execution_attribution.csv` for model-edge to fill/PnL decomposition
- `execution_markout_slices.csv` for coverage and edge/spread/inventory/latency slices
- `execution_fills.csv`, `execution_markouts.csv`, and `execution_account.csv` for post-trade evaluation
