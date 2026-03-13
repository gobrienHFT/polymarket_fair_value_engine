# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a paper-trading-first research and execution framework for short-dated Polymarket binary markets. The current implementation focuses on BTC 5-minute up/down markets and is organized so the same stack can later price and quote sports, macro, or other event contracts.

This repo is intentionally not a hypey betting bot. The goal is to show disciplined trading architecture:

- normalized market metadata
- explicit fair-value models
- passive quoting around fair value
- inventory-aware risk controls
- paper execution, replay, and reporting
- guarded live execution paths

## What Is Implemented

The first market family is `btc-updown-5m`.

The baseline fair-value model:

- pulls a reference BTC spot price from Coinbase
- estimates realized volatility from recent 1-minute closes
- uses a short-horizon diffusion approximation for `P(up)`
- applies an uncertainty buffer and optional market-mid blend
- reports diagnostics instead of pretending the model is production alpha

The default strategy is passive market making. Instead of blindly buying perceived value, it:

- discovers eligible active markets
- computes `p_yes`
- reads YES/NO order books and market midpoint
- builds passive quotes around fair value
- converts the YES ask into an equivalent `BUY NO` quote
- skews quotes based on existing YES/NO inventory
- throttles cancel/replace activity
- stops quoting near expiry, on stale data, or when limits are hit

## Project Layout

```text
polymarket-fair-value-engine/
  README.md
  pyproject.toml
  .env.example
  src/polymarket_fair_value_engine/
    config.py
    cli.py
    types.py
    logging_utils.py
    data/
    markets/
    models/
    strategy/
    execution/
    risk/
    analytics/
    backtest/
    legacy/
    sports/
  tests/
```

## CLI

Install the package first:

```bash
python -m pip install -e .[dev]
```

For live execution support, install the optional live dependency set:

```bash
python -m pip install -e .[dev,live]
```

```bash
pmfe scan --series btc-updown-5m
pmfe quote --series btc-updown-5m --paper --iterations 25
pmfe backtest --input data/sample_replay.jsonl
pmfe cancel-all --live --ack-live-risk
pmfe report --run-id latest
```

### `scan`

Discovers eligible markets and prints fair value, midpoint, spread, inventory-neutral quote targets, and model diagnostics.

### `quote --paper`

Runs the passive quoting loop with the paper execution engine. It exports:

- orders
- fills
- inventory snapshots
- PnL snapshots
- summary metadata

under `runs/<run_id>/`.

### `backtest`

Replays stored JSONL snapshots through the same strategy, order manager, paper engine, and reporting stack.

### `--live`

Live execution is intentionally gated:

- paper mode is the default
- `--live` is required
- `--ack-live-risk` is required
- the config must explicitly allow live trading
- auth errors fail loudly instead of silently degrading

## Risk Controls

The engine applies hard controls before quoting or replacing orders:

- max notional per market
- max gross exposure
- max net YES-minus-NO exposure by series
- max order size
- max open orders
- stale data checks
- no-trade window near expiry
- cancel-all and kill-switch paths

## Config And Secrets

The repo keeps compatibility with the legacy env names already used in the prototype, including:

- `POLY_PRIVATE_KEY`
- `POLY_FUNDER`
- `POLY_SIGNATURE_TYPE`
- `CLOB_API_KEY`
- `CLOB_SECRET`
- `CLOB_PASSPHRASE`
- `POLYGON_RPC`
- legacy `BOT_*` fields

Real keys belong only in your local `.env`. This repo ships a safe `.env.example`, and `.env` is gitignored so it does not get pushed remotely.

## Current Limitations

- the BTC model is a baseline diffusion model, not a source of claimed alpha
- paper fills are deterministic touch-or-cross approximations, not queue-position simulation
- websocket ingestion is scaffolded, but the default implementation uses polling REST snapshots
- live execution is intentionally conservative and only lightly abstracted beyond the Polymarket client

## Sports Extension Path

The repo already includes extension points for:

- bookmaker consensus odds adapters
- team-rating or Poisson-style sports models
- sports event normalization

Those scaffolds are not production sports pricers yet. They exist to keep the architecture obviously extensible from crypto binaries into broader event markets.

## Future Work

- websocket-driven market data and lower-latency order management
- richer fill models for replay and paper simulation
- settlement-aware realized PnL for resolved markets
- bookmaker / exchange consensus adapters for sports
- event-specific pricing models beyond short-dated crypto directionals
