# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a research and execution framework for Polymarket-style binary markets, with a paper-trading-first BTC path and an offline football pricing demo.

The implemented scope is intentionally narrow and explicit:

- **BTC 5-minute up/down** is still the only end-to-end paper/live execution path
- **Football** is now an offline fair-value, calibration, and opportunity-ranking demo

That keeps the repo explainable, testable, and honest. It does not claim that live football trading is already implemented.

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

## Football Demo

For the offline football pricing path:

```bash
pmfe football-demo --run-id football-demo
```

That command:

- loads bundled bookmaker 1X2 sample data from `data/sample_football_markets.json`
- normalizes fixtures, bookmaker snapshots, and Polymarket-style binary football markets
- removes overround from the 1X2 prices and builds a simple bookmaker consensus
- maps 1X2 fair probabilities into binary YES probabilities such as `home_win`, `draw`, `home_or_draw`, and `either_team_wins`
- writes deterministic artifacts under `runs/<run_id>/`

This is an offline pricing and calibration demo. It is not a live football trading implementation.

## Architecture

```text
Data -> Model -> Strategy -> Risk -> Order Manager -> Execution -> Reporting
```

- `Data`: market discovery, order books, and reference prices
- `Model`: baseline fair-value estimate for `P(YES)`
- `Strategy`: passive YES / NO quote intents around fair value, or offline candidate quotes around football fair value
- `Risk`: market, gross, series, and open-order limits
- `Order Manager`: reconcile desired quotes against current open orders
- `Execution`: paper fills by replay/live market state, or an offline stop at ranking/reporting for football
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
- load bundled football fixtures with bookmaker 1X2 odds and binary market snapshots
- compute vig-adjusted football fair probabilities from bookmaker consensus
- map football 1X2 fair value into binary YES probabilities for Polymarket-style markets
- rank football markets by edge versus midpoint, best bid, and best ask
- export offline football pricing artifacts for interview/demo walkthroughs

The repo still only implements BTC for end-to-end execution. Football stops at offline fair value, edge ranking, and candidate quote generation. That is deliberate.

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

`pmfe football-demo` writes:

```text
runs/<run_id>/
  summary.json
  football_fair_values.csv
  football_edges.csv
```

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

Those guardrails apply to the BTC execution path. Live football execution is not implemented.

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
  sports/                # offline football pricing + sports helpers

legacy/
  polymarket_bot.py      # archived single-file prototype

scripts/
  demo.sh
  demo.ps1
```

## What To Demo In Interview

One straightforward interview walkthrough is:

1. Run `pmfe football-demo --run-id interview-football`.
2. Inspect `summary.json`.
3. Inspect `football_fair_values.csv` and `football_edges.csv`.
4. Explain how bookmaker 1X2 odds are normalized, de-vigged, averaged into a consensus, and mapped into binary Polymarket probabilities.
5. Explain how you would extend the offline pricing demo toward live football pricing and execution later, without claiming that path exists today.

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
- football is an offline pricing/calibration demo only, not a live trading path
