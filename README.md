# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a research and execution framework for Polymarket-style binary markets, with a paper-trading-first BTC path and an offline football pricing/replay/sweep demo.

The implemented scope is intentionally narrow and explicit:

- **BTC 5-minute up/down** is still the only end-to-end paper/live execution path
- **Football** is now an offline fair-value, replay, calibration, and strategy-comparison demo

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

## Football Demo Paths

For the quick static football pricing snapshot:

```bash
pmfe football-demo --run-id football-demo
```

That command:

- loads bundled bookmaker 1X2 sample data from `data/sample_football_markets.json`
- normalizes fixtures, bookmaker snapshots, and Polymarket-style binary football markets
- removes overround from the 1X2 prices and builds a simple bookmaker consensus
- maps 1X2 fair probabilities into binary YES probabilities such as `home_win`, `draw`, `home_or_draw`, and `either_team_wins`
- computes directional edges such as `buy_edge_vs_ask`, `sell_edge_vs_bid`, and `max_actionable_edge`
- writes deterministic artifacts under `runs/<run_id>/`

For the replayable football pricing/evaluation path:

```bash
pmfe football-replay --sample --config configs/football_strategy_baseline.json --run-id football-replay
pmfe report --run-id football-replay
```

That command:

- loads bundled synthetic replay frames from `data/sample_football_replay.jsonl`
- re-prices each frame from the bundled bookmaker 1X2 snapshots
- maps the consensus 1X2 fair value into binary YES probabilities for each football market
- applies explicit no-trade rules for missing books, wide spreads, stale sources, recent goals/red cards, and suspended/finished match states
- writes replay quotes, markouts, calibration summaries, state-change rows, and a markdown report under `runs/<run_id>/`
- can optionally load a JSON pricing config override for research runs

For the football strategy-comparison path:

```bash
pmfe football-sweep --sample --config configs/football_sweep.json --run-id football-sweep
pmfe report --run-id football-sweep
```

That command:

- runs multiple named pricing/no-trade configurations against the same replay sample
- ranks them on directional capture metrics rather than raw midpoint drift
- writes a strategy leaderboard, regime slices, a short markdown report, and a nested detailed replay for the selected best strategy

Football remains an offline pricing/evaluation path. It is not a live football trading implementation.

A tighter explanation of the replay flow lives in `docs/football_replay_walkthrough.md`.
The strategy comparison layer is documented in `docs/football_strategy_sweep_walkthrough.md`.

## Architecture

```text
Data -> Model -> Strategy -> Risk -> Order Manager -> Execution -> Reporting
```

- `Data`: market discovery, order books, and reference prices
- `Model`: baseline fair-value estimate for `P(YES)`
- `Strategy`: passive YES / NO quote intents around fair value, or offline candidate quotes around football fair value
- `Risk`: market, gross, series, and open-order limits
- `Order Manager`: reconcile desired quotes against current open orders
- `Execution`: paper fills by replay/live market state, or an offline stop at pricing, quote decisions, markouts, and reporting for football
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
- rank football markets by directional buy/sell edges versus midpoint, best bid, and best ask
- replay bundled football frames with explicit match state, state changes, and no-trade rules
- compute raw midpoint drift and directional capture metrics from the replay sample
- compare multiple football strategy configurations with deterministic winner selection and regime breakdowns
- export offline football pricing, replay, and strategy-sweep artifacts for interview/demo walkthroughs

The repo still only implements BTC for end-to-end execution. Football stops at offline fair value formation, quote decisions, replay evaluation, and strategy comparison. That is deliberate.

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

`pmfe football-replay --sample` writes:

```text
runs/<run_id>/
  summary.json
  football_replay_quotes.csv
  football_markouts.csv
  football_calibration.csv
  football_state_changes.csv
  football_no_trade_reasons.csv
  football_report.md
```

`pmfe football-sweep --sample` writes:

```text
runs/<run_id>/
  summary.json
  football_strategy_results.csv
  football_strategy_slices.csv
  football_strategy_report.md
  football_strategy_best.json
  best_strategy/
    summary.json
    football_replay_quotes.csv
    football_markouts.csv
    football_calibration.csv
    football_state_changes.csv
    football_no_trade_reasons.csv
    football_report.md
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
  cli.py                 # scan / quote / backtest / demo / football-demo / football-replay / football-sweep / report / cancel-all
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

configs/
  football_strategy_baseline.json
  football_sweep.json

scripts/
  demo.sh
  demo.ps1
```

## What To Demo In Interview

One straightforward interview walkthrough is:

1. Run `pmfe football-demo --run-id interview-football-demo` to show the static pricing snapshot.
2. Run `pmfe football-replay --sample --config configs/football_strategy_baseline.json --run-id interview-football-replay`.
3. Run `pmfe football-sweep --sample --config configs/football_sweep.json --run-id interview-football-sweep`.
4. Inspect `summary.json` and `football_report.md` in `runs/interview-football-replay/`.
5. Inspect `football_strategy_results.csv`, `football_strategy_slices.csv`, and `football_strategy_report.md` in `runs/interview-football-sweep/`.
6. Explain how bookmaker 1X2 odds are de-vigged, mapped into binary Polymarket probabilities, turned into directional quote decisions, and then compared across multiple strategy settings.
7. Explain how you would extend the replay/sweep path toward live football pricing/execution later, without claiming that path exists today.

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
- football is an offline pricing/replay/strategy-comparison demo only, not a live trading path
- the football sweep is an evaluation/tooling exercise on synthetic data, not production validation
