# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a paper-trading-first prediction-market research and execution repo built to be explainable in a quant trading or market-making interview.

It is deliberately not a hype project. The point is to show a clean trading stack:

- normalized market discovery
- reference-price ingestion
- a baseline fair-value model
- passive quoting logic
- inventory and risk limits
- order reconciliation
- paper execution and replay backtesting
- guarded live execution

The first implemented market family is **BTC 5-minute up/down Polymarket markets**. That choice is intentional: the contracts are simple, the horizon is short, and an external reference price exists. It is a better first proving ground for architecture than pretending a serious sports pricer already exists.

## What Is Actually Implemented

Today the repo can:

- discover and normalize BTC short-dated up/down markets
- pull BTC spot and recent minute closes from Coinbase
- estimate a baseline `P(up)` with a short-horizon diffusion approximation
- blend that estimate with market midpoint and apply an uncertainty buffer
- generate passive YES / NO quote intents around fair value
- skew quoting behavior based on current YES / NO inventory
- enforce simple hard limits before quoting
- reconcile quote updates in paper mode
- simulate paper fills with a documented touch-or-cross or strict-cross-only rule
- replay stored market states from JSONL and write out artifacts
- gate live execution behind explicit flags and config

The repo also ships a committed deterministic replay sample at `data/sample_replay.jsonl` so the backtest/report flow works from a clean checkout.

## What Is Only Scaffolding

The repo is structured so it can later support sports and other event markets, but those pieces are scaffolding today:

- bookmaker consensus adapters
- sports event normalization
- team-rating / Poisson-style model hooks
- websocket market-data plumbing

This is **not** a claim that sports pricing alpha is implemented.

## Fair-Value Model

The current BTC model is intentionally simple and honest:

1. pull a BTC reference price
2. estimate realized volatility from recent 1-minute closes
3. use a short-horizon diffusion-style approximation for `P(up)`
4. optionally blend with market midpoint
5. apply an uncertainty buffer before quoting

This is a **baseline fair-value model**, not a production alpha claim.

## Strategy

The default strategy is passive market making around fair value, not blind taker buying.

For each market:

1. estimate fair value
2. read YES / NO order books
3. compute quote targets around fair value
4. skew quoting based on current YES-minus-NO exposure
5. quantize to market ticks
6. run the quotes through risk checks
7. reconcile cancels / replacements

The first market family stays narrow on purpose: BTC 5-minute up/down markets are easier to reason about, easier to sanity-check, and a cleaner first demo than forcing broad market coverage too early.

## Paper Fill Model

Paper fills are intentionally simple and explicitly documented:

- `PMFE_TOUCH_FILL_ONLY=1` means a paper order fills when the market **touches or crosses** the quoted price.
- `PMFE_TOUCH_FILL_ONLY=0` means the simulator requires a **strict cross**.
- The simulator does **not** model queue position, adverse selection, hidden liquidity, or partial matching dynamics beyond immediate full fills on the selected rule.

That is a feature, not a bug: the simulator is meant to be explainable and honest, not cosmetically sophisticated.

## Live Execution

Live mode is heavily gated:

- paper mode is the default
- `--live` is required
- `--ack-live-risk` is required
- `PMFE_LIVE_ENABLED=1` must be set
- auth failures raise loudly

The current live quote loop only tracks orders placed by the current process. Stale or replaced live quotes are cancelled **targetedly** when possible. `cancel-all` remains available as the manual kill-switch path and is also used when the configured kill-switch file is present.

## Install

Editable install with test dependencies:

```bash
python -m pip install -e .[dev]
```

If you want live execution support as well:

```bash
python -m pip install -e .[dev,live]
```

## Demo Commands

Deterministic offline demo:

```bash
pytest -q
pmfe backtest --input data/sample_replay.jsonl --run-id sample-demo
pmfe report --run-id sample-demo
```

There is also a short demo script:

```bash
scripts/demo.sh
```

Public-endpoint scan / paper-quote commands:

```bash
pmfe scan --series btc-updown-5m
pmfe quote --series btc-updown-5m --paper --iterations 10
```

Those two commands use live public market data. The deterministic demo path is the replay sample above.

## Output Artifacts

Backtests and paper runs write readable artifacts under `runs/<run_id>/`:

- `orders.csv`
- `fills.csv`
- `inventory.csv`
- `pnl.csv`
- `summary.json`

## Repository Layout

```text
src/polymarket_fair_value_engine/
  config.py              # env/config loading
  cli.py                 # scan / quote / backtest / report / cancel-all
  data/                  # Gamma, CLOB REST, external prices
  markets/               # normalization + discovery
  models/                # fair-value models
  strategy/              # passive quoting logic
  risk/                  # limits + inventory
  execution/             # paper + live execution
  analytics/             # exports + reports
  backtest/              # replay loader + simulator
  sports/                # scaffolding only
  legacy/                # wrapper around the original prototype
```

## Known Limitations

- the BTC model is a baseline fair-value approximation
- the default scan and quote commands still depend on public Polymarket / Coinbase endpoints
- the paper fill model is deterministic and deliberately simple
- live quote management only knows about orders placed by the current process
- websocket ingestion is scaffolded rather than productionized
- sports support is architecture-only at this stage

## Why This Shape Works In Interview

The repo is easy to walk through end-to-end:

1. discover and normalize a market
2. fetch reference prices and order books
3. estimate fair value
4. generate passive quote intents
5. apply inventory and risk limits
6. reconcile desired quotes vs open orders
7. simulate or place execution
8. export fills, inventory, and PnL

That is the core story: a clean, defensible market-making research framework with honest scope and clear extension points.
