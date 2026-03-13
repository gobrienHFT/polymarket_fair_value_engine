# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a paper-trading-first research and execution framework for short-dated binary/event markets on Polymarket.

The current implemented scope is intentionally narrow: **BTC 5-minute up/down markets**. That keeps the project explainable, testable, and honest. The repo is designed to support later extension into broader event markets, but it does not pretend to be a production sports pricer or a proven alpha engine today.

## 60-Second Demo

Fresh clone:

```bash
python -m pip install -e .[dev]
pmfe demo
```

That command:

- runs fully offline against bundled replay data
- writes artifacts under `runs/demo-<timestamp>/`
- prints a concise JSON summary
- requires no live credentials and no internet access

For a longer deterministic walkthrough:

```bash
pytest -q
pmfe backtest --input data/sample_replay.jsonl --run-id sample-demo
pmfe report --run-id sample-demo
```

Public-endpoint commands that use live market data:

```bash
pmfe scan --series btc-updown-5m
pmfe quote --series btc-updown-5m --paper --iterations 10
```

## What The Current Implementation Actually Does

Today the repo can:

- discover and normalize active BTC 5-minute up/down markets
- ingest YES / NO order books from the Polymarket CLOB REST API
- ingest a BTC reference price and recent minute closes from Coinbase
- estimate a baseline fair value for `P(YES)` using short-horizon diffusion logic
- blend that estimate with market midpoint and apply an uncertainty buffer
- turn fair value into passive YES / NO quote intents
- skew quoting based on current YES-minus-NO inventory
- enforce explicit pre-trade limits
- reconcile open orders versus desired quotes
- simulate paper fills and mark inventory to market
- replay stored JSONL market states and export run artifacts
- gate live execution behind explicit flags and config

## What Is Scaffolded But Not Yet Production-Grade

The repo includes extension points for future work, but these are deliberately described as scaffolding:

- sportsbook / bookmaker consensus adapters
- sports event normalization
- team-rating or Poisson-style sports model hooks
- websocket-driven data ingestion
- richer live order-state synchronization

That is architecture, not a claim of implemented sports pricing alpha.

## Architecture

The core flow is:

1. market discovery and normalization
2. reference-price and order-book ingestion
3. fair-value estimation
4. passive quote construction
5. inventory/risk filtering
6. order reconciliation
7. paper execution or guarded live execution
8. replay/reporting outputs

Repository layout:

```text
src/polymarket_fair_value_engine/
  cli.py                 # scan / quote / backtest / demo / report / cancel-all
  config.py              # env and runtime config
  data/                  # Gamma, CLOB REST, external prices
  markets/               # market discovery + normalization
  models/                # fair-value models
  strategy/              # passive quoting logic
  risk/                  # exposure and order limits
  execution/             # paper + live execution paths
  analytics/             # exports + run summaries
  backtest/              # replay loader + simulator
  sports/                # extension scaffolding only
  legacy/                # wrapper around the original seed script
```

## Model + Strategy Summary

### Fair value model

The current BTC model is a baseline diffusion-style fair-value model, not a production alpha claim.

Inputs:

- BTC reference spot
- recent 1-minute closes for realized volatility
- market midpoint
- replay metadata when running historical/offline paths

Output:

- a fair-value estimate for `P(YES)` and `P(NO)`
- an uncertainty buffer
- model diagnostics for inspection

In replay mode, the model uses the market state's own timestamp and replay metadata rather than current wall-clock time, so historical runs remain deterministic.

### Passive quote construction

The default strategy does not blindly cross the spread. It builds passive quote intents around fair value:

- `bid_yes = fair_value - half_spread - uncertainty - inventory_skew`
- `ask_yes = fair_value + half_spread + uncertainty + inventory_skew`

When appropriate, the strategy expresses the opposite side through `NO` quotes instead of pretending the market is only one-sided.

### Inventory skew

Inventory skew is explicit:

- if the engine is already long YES, it becomes less willing to buy more YES and more willing to sell YES
- if it is long NO, it skews the other way

That keeps the quoting logic closer to a market-making conversation than a one-way directional buyer.

### Paper execution assumptions

The paper engine is intentionally simple and honest:

- `PMFE_TOUCH_FILL_ONLY=1` fills on touch-or-cross
- `PMFE_TOUCH_FILL_ONLY=0` requires a strict cross
- no queue-position realism
- no hidden-liquidity modeling
- no claim that replay fills equal live fills

### Why replay/backtest exists

Replay exists so the repo can:

- demonstrate the full stack offline
- test model/strategy/execution behavior deterministically
- export interpretable artifacts for review

That is especially useful in interviews because it removes dependence on live APIs or market conditions.

### Live path

The live path exists, but it is intentionally conservative:

- paper mode is the default
- `--live` and `--ack-live-risk` are required
- `PMFE_LIVE_ENABLED=1` must be set
- auth/config failures raise loudly
- stale/replaced orders are cancelled target-by-target when possible
- `cancel-all` remains the explicit kill-switch path

## Output Artifacts

Backtests, demos, and paper runs write:

- `orders.csv`
- `fills.csv`
- `inventory.csv`
- `pnl.csv`
- `summary.json`

under `runs/<run_id>/`.

## Install

Editable install with test dependencies:

```bash
python -m pip install -e .[dev]
```

If you want the optional live client dependency too:

```bash
python -m pip install -e .[dev,live]
```

## Known Limitations

- the BTC fair-value model is a baseline, not a claim of persistent alpha
- scan and live-data paper quoting still depend on public Polymarket / Coinbase endpoints
- the paper fill model is deliberately simplistic
- live order management only knows about orders placed by the current running process
- websocket ingestion is still scaffolding
- sports support remains an extension path rather than a real implemented pricer

## Why This Project Works As An Interview Demo

It is easy to explain end-to-end:

1. normalize a market
2. ingest a reference price and order books
3. estimate fair value
4. generate inventory-aware passive quotes
5. enforce hard risk limits
6. reconcile orders
7. simulate execution or invoke guarded live execution
8. inspect artifacts and PnL

That is a realistic research/execution framework story without pretending this is already a production market-making system.
