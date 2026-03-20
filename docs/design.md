# Design Note

## Current Market Family

The implemented end-to-end market family is **BTC 5-minute up/down Polymarket markets**.

This is a deliberate first target:

- contracts are binary and easy to normalize
- expiry is short, so time-to-resolution matters in a visible way
- an external reference price exists
- the market family is narrow enough to support honest end-to-end demos

The repo is structured so other event markets can be added later. The current productionized execution path is this BTC family only.

## Football Offline Pricing And Replay Demo

The sports layer now includes a narrow football path that stays offline and inspectable.

It does not attempt live football trading. Instead it:

- loads bundled football fixtures plus bookmaker 1X2 odds snapshots
- removes overround from each bookmaker snapshot
- averages those fair probabilities into a simple bookmaker consensus
- maps 1X2 fair probabilities into binary football markets such as `home_win`, `draw`, `home_or_draw`, and `either_team_wins`
- compares fair value versus sample best bid / best ask / midpoint using explicit directional edges such as `buy_edge_vs_ask` and `sell_edge_vs_bid`
- replays bundled football frames with match state, state-change detection, no-trade rules, and markout/calibration outputs
- writes deterministic CSV, JSON, and markdown artifacts for review

The replay input is bundled and synthetic. That is stated explicitly in the docs and artifacts so the repo stays honest about what is and is not implemented.

That makes the sports path materially more relevant to football prediction markets without pretending the repo already has live football execution.

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

This is intentionally framed as a baseline fair-value model, not a claim of durable alpha.

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

The goal is not sophisticated optimal control. The goal is a clean, inspectable inventory-aware quoting rule.

## Risk Controls

The pre-trade risk layer enforces hard checks on:

- max notional per market
- max gross exposure
- max net exposure per series
- max order size
- max open orders

Projected exposure is accumulated across already-approved quotes in the same pass so the second or third quote in a batch cannot ignore the earlier ones.

## Replay And Paper Execution

Replay exists to make the stack deterministic and demoable without live dependencies.

The paper engine intentionally uses simple fill rules:

- touch-or-cross fills
- optional replay-fill slack for more permissive sample/replay fills

It does not claim queue-position realism, hidden-liquidity realism, or live-equivalent fill quality.

That keeps the assumptions explicit and defensible.

For football specifically, replay is used differently from the BTC execution path:

- fair value is still formed directly from bundled bookmaker 1X2 updates
- quote decisions are generated against bundled Polymarket-style YES books
- evaluation focuses on no-trade logic, next-snapshot markouts, 2-step markouts, and simple calibration summaries
- the replay report explains state changes, markout definitions, and limitations in plain language

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
- live football trading is not implemented

## Next Upgrades

- websocket-driven market data ingestion
- richer live order-state reconciliation
- more realistic replay datasets recorded from live observation
- broader event-market normalization
- live football market discovery and execution adapters, if paired with a real event-state and pricing stack later
- additional fair-value models beyond the BTC short-horizon baseline
