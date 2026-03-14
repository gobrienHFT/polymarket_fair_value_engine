# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a paper-trading-first research and execution framework for Polymarket binary markets.

The implemented scope is intentionally narrow: **BTC 5-minute up/down markets**. That keeps the repo explainable, testable, and honest. The codebase preserves extension points for sports and other event markets, but it does not claim that those paths are implemented pricers today.

## Fastest Demo

Fresh clone:

```bash
python -m pip install -e .[dev]
pmfe demo
```

That one command runs fully offline against the bundled replay sample in `data/sample_replay.jsonl`, writes artifacts under `runs/<run_id>/`, and prints a JSON summary with the output directory and artifact paths.

The alternate explicit form is:

```bash
pmfe backtest --sample --run-id sample-demo
pmfe report --run-id sample-demo
```

Convenience wrappers are available at `scripts/demo.sh` and `scripts/demo.ps1`. They install the editable package, run `pytest`, run the sample backtest, run `pmfe report`, and print the output directory. The canonical interface remains `pmfe ...`.

## Architecture

```text
Data -> Model -> Strategy -> Risk -> Order Manager -> Execution -> Reporting
```

- `Data`: market discovery, order books, and reference prices
- `Model`: baseline fair-value estimate for `P(YES)`
- `Strategy`: passive YES / NO quote intents around fair value
- `Risk`: market, gross, series, and open-order limits
- `Order Manager`: reconcile desired quotes against current open orders
- `Execution`: paper fills by replay/live market state or guarded live posting
- `Reporting`: CSV artifacts and JSON summaries under `runs/<run_id>/`

## What The Repo Actually Implements

Today the package can:

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

The repo also includes extension scaffolding for sportsbook adapters, sports normalization, rating models, and websocket ingestion. Those are architecture hooks, not claims of implemented sports pricing.

## Replay And Output Artifacts

Backtests, demos, and paper runs write:

```text
runs/<run_id>/
  summary.json
  orders.csv
  fills.csv
  inventory.csv
  pnl.csv
```

`pmfe report --run-id <run_id>` reads the stored summary and prints the run location plus the artifact paths again.

Paper fill behavior is intentionally simple:

- `PMFE_TOUCH_FILL_ONLY=1`: fill only when the quoted price touches or crosses the best quote
- `PMFE_TOUCH_FILL_ONLY=0`: allow more permissive replay fills within `PMFE_REPLAY_FILL_SLACK`
- no queue-position realism
- no hidden-liquidity modeling
- no claim that replay fills equal live fills

## Live Execution Guardrails

The live path is present but deliberately guarded:

- paper mode is the default
- `--live` and `--ack-live-risk` are required
- `PMFE_LIVE_ENABLED=1` must be set
- auth or config failures raise loudly
- `cancel-all` remains the explicit kill-switch path

## Repository Layout

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
  sports/                # extension scaffolding

legacy/
  polymarket_bot.py      # archived single-file prototype

scripts/
  demo.sh
  demo.ps1
```

## What To Demo In Interview

One straightforward interview walkthrough is:

1. Run `pmfe demo` or `pmfe backtest --sample --run-id interview-demo`.
2. Show the JSON summary and the generated `runs/<run_id>/` directory.
3. Open `summary.json`, `fills.csv`, and `pnl.csv` to show the replay outcome.
4. Walk the pipeline from data ingestion to fair value, strategy, risk, order reconciliation, execution, and reporting.
5. Point out that the live path is guarded and that the current implemented scope is BTC 5-minute up/down only.
6. Mention that sports is an extension path in the package layout, not a completed public claim.

## Install

Editable install with tests:

```bash
python -m pip install -e .[dev]
```

If you want the optional live dependency too:

```bash
python -m pip install -e .[dev,live]
```

## Limitations

- the BTC fair-value model is a baseline, not a claim of persistent alpha
- scan and live-data paper quoting still depend on public Polymarket and Coinbase endpoints
- the paper fill model is intentionally simple
- live order management only knows about orders placed by the current running process
- websocket ingestion is still scaffolding
- sports support remains an extension path rather than an implemented public pricer
