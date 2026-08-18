# Design Note

## Research Thesis

The question behind the repo is what happens between a fair-value estimate and a trade. A model can point to a discrepancy; the execution layer decides how much survives spread, visible depth, queue uncertainty, latency, fees, inventory, fills, and post-fill movement.

```text
Fair value -> apparent edge -> execution choice -> fill / no fill -> markout / inventory / PnL -> realized edge
```

The repository keeps probability formation and execution evaluation as separate layers. BTC supplies the end-to-end paper/live-capable execution path. Football is a separate offline fair-value, replay, and calibration case study.

## Current Market Family

The implemented end-to-end market family is **BTC 5-minute up/down Polymarket markets**.

This is a deliberate first target:

- contracts are binary and easy to normalize
- expiry is short, so time-to-resolution matters in a visible way
- an external reference price exists
- the market family is narrow enough to support an honest end-to-end execution workflow

Other event markets can be added later, but the end-to-end execution path today is this BTC family only.

## Football Fair-Value Case Study

Football has its own narrow path, kept offline so the pricing and evaluation steps stay visible.

It does not attempt live football trading. Instead it:

- loads bundled football fixtures plus bookmaker 1X2 odds snapshots
- removes overround from each bookmaker snapshot
- averages those fair probabilities into a simple bookmaker consensus
- maps 1X2 fair probabilities into binary football markets such as `home_win`, `draw`, `home_or_draw`, and `either_team_wins`
- compares fair value versus sample best bid / best ask / midpoint using explicit directional edges such as `buy_edge_vs_ask` and `sell_edge_vs_bid`
- replays bundled football frames with match state, state-change detection, no-trade rules, and markout/calibration outputs
- compares multiple pricing/no-trade configurations on the same replay sample using directional capture metrics
- writes deterministic CSV, JSON, and Markdown files that make the path easy to follow

The replay input is bundled and synthetic. The documentation says so plainly: this is a pricing and evaluation workflow, not live football trading.

That makes football useful as a market-normalization and evaluation case study without turning it into a pretend live execution system.

## Fair Value Model

The current fair-value model is a short-horizon diffusion baseline.

Inputs:

- reference spot price
- recent 1-minute closes for realized volatility
- replay metadata when running historical/offline paths
- current market midpoint

Process:

1. estimate short-horizon drift/volatility inputs
2. translate those into a baseline `P(YES)`
3. optionally blend with market midpoint
4. apply an uncertainty buffer before strategy quoting

Outputs:

- `p_yes`
- `p_no`
- uncertainty buffer
- diagnostics for inspection

This is a baseline fair-value model for the execution and replay layers. It is not intended to support a durable-alpha claim.

## Strategy

The default strategy is passive quoting around fair value.

Conceptually:

- build a fair value for YES
- center quotes around that value rather than around last trade alone
- widen or suppress quoting when uncertainty or microstructure quality is poor
- skew quoting when inventory becomes unbalanced

The strategy can express the other side of the market through `NO` quotes when appropriate instead of assuming only a single YES leg matters.

## Inventory Management And Skew

Inventory is tracked explicitly in YES and NO contracts.

The strategy uses net YES exposure to skew quoting:

- long YES reduces willingness to add more YES
- long YES increases willingness to sell YES
- long NO pushes the strategy the opposite way

This is not meant to be sophisticated optimal control. It is an inventory-aware quoting rule that is easy to follow.

## Risk Controls

The pre-trade risk layer enforces hard checks on:

- max notional per market
- max gross exposure
- max net exposure per series
- max order size
- max open orders

Projected exposure is accumulated across already-approved quotes in the same pass so the second or third quote in a batch cannot ignore the earlier ones.

## Replay And Paper Execution

Replay makes the stack deterministic and removes live dependencies from the evaluation loop.

The paper engine intentionally uses simple fill rules:

- touch-or-cross fills
- optional replay-fill slack for more permissive sample/replay fills

It does not claim queue-position realism, hidden-liquidity realism, or live-equivalent fill quality.

The important thing is that the fill assumptions stay visible.

For football specifically, replay is used differently from the BTC execution path:

- fair value is still formed directly from bundled bookmaker 1X2 updates
- quote decisions are generated against bundled Polymarket-style YES books
- evaluation focuses on no-trade logic, raw midpoint drift, directional capture metrics, and simple calibration summaries
- the replay report explains state changes, markout definitions, and limitations in plain language

The run summary is more useful when it explains the path to the final number. BTC replay and paper runs record observation counts, skip reasons, quote funnel counts, risk rejection categories, final open orders, and an explicit stop reason. The detailed CSV files then carry the order, fill, inventory, and PnL history.

The strategy sweep extends that replay path without trying to turn it into a live trading stack:

- each strategy is just a named pricing/no-trade configuration
- the same replay frames are reused for every configuration
- winner selection is deterministic and config-driven
- the output helps compare configuration choices; it does not establish proven edge

## Fair Value To Execution Research

The separate `execution-research` command studies binary-market execution around a fixed synthetic CLOB replay. Probability formation and execution quality stay as separate measurements:

- each frame normalizes market identity, timestamps, sequence, bid/ask depth, spread, depth imbalance, microprice, and validity state
- malformed, stale, crossed, expired, or discontinuous frames fail closed and cannot submit a new order
- each scenario records decision, risk check, submit latency, acknowledgement, resting state, partial/full fills, cancel request, cancel acknowledgement, expiry, rejection, and cancel/fill race events
- passive and aggressive styles are compared under named conservative, base, and aggressive visible-depth profiles
- fills are evaluated with fees, spread paid/captured, time resting, inventory, realised/unrealised/marked PnL, and signed markouts at multiple horizons
- `execution_attribution.csv` decomposes raw model edge into execution price, spread cost/capture, fees, queue/depth fill ratio, latency midpoint impact, fill/unfilled quantity, inventory, and net realized edge
- `execution_markout_slices.csv` reports markout coverage and signed outcomes by edge, spread, inventory, and decision-to-fill latency buckets
- a one-factor experiment matrix varies fair-value edge, spread, imbalance, visible depth, queue-ahead, participation, latency, execution profile, inventory, and fees against fixed input frames
- the evaluation config and definitions are frozen for each refresh; the synthetic fixture has no calibration/holdout split and is not used to validate production profitability

The run identity records `code_version`, `config_sha256`, `input_sha256`, and hashes for every output file in `summary.json`. The reference pack under `docs/sample_outputs/execution_research_reference/` is regenerated by `python scripts/refresh_execution_research.py` and is the reproducible public output.

The study does not establish live football execution, participant-level FIFO, hidden-liquidity knowledge, historical fill truth, venue-measured latency, or production alpha. Public snapshots support a visible-depth queue proxy only. A historical evidence pack is not included because the repo does not have deterministic historical depth, fair-value inputs, and provenance bound together; adding one without those inputs would overstate the evidence. See `docs/execution_research_packet.md` and `docs/execution_casebook.md` for the short path through the results.

## Live Execution

Live execution is present but conservative:

- opt-in only
- explicit CLI acknowledgement required
- config gate required
- auth failures are loud
- targeted cancellation is preferred for replaced/stale orders
- `cancel-all` remains the kill-switch path

This path is better thought of as a guarded execution adapter than as a finished live trading system.

## Known Limitations

- the model is a baseline approximation
- live public data can be noisy or wide for short-dated binaries
- the paper fill model is intentionally simplistic
- live order-state tracking only covers orders placed by the current process
- football fair value still comes from bookmaker snapshots rather than an independent in-play model
- football replay uses a small bundled synthetic sample, so its calibration/markout statistics are illustrative only
- football strategy sweep results are illustrative and sensitive to the small synthetic sample
- live football trading is not implemented

## Next Upgrades

- websocket-driven market data ingestion
- richer live order-state reconciliation
- more realistic replay datasets recorded from live observation
- broader event-market normalization
- live football market discovery and execution adapters, if paired with a real event-state and pricing stack later
- richer football strategy evaluation on larger recorded replay samples
- additional fair-value models beyond the BTC short-horizon baseline
