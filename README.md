# Polymarket Fair Value Engine

`polymarket_fair_value_engine` is a research and execution framework for Polymarket-style binary markets, with an offline football pricing/replay/sweep research path and a secondary BTC execution sandbox.

The implemented scope is intentionally narrow and explicit:

- **Football** is an offline fair-value, replay, calibration, and strategy-comparison workflow built from bundled sample inputs
- **BTC 5-minute up/down** is still the only end-to-end paper/live execution path

That keeps the repo explainable, testable, and honest. It does not claim that live football trading is already implemented.

## Football Research Path

The football front door is an offline pricing/replay/sweep research workflow built from bundled sample data. It does not claim live football trading, and its replay outputs do not claim queue-position realism.

Committed zero-click football reference packs:

- Index: [docs/sample_outputs/README.md](docs/sample_outputs/README.md)
- Research note: [docs/football_trading_research_note.md](docs/football_trading_research_note.md)
- Decision casebook: [docs/football_decision_casebook.md](docs/football_decision_casebook.md)
- Strategy config note: [docs/football_strategy_configuration_note.md](docs/football_strategy_configuration_note.md)
- Snapshot reference: [docs/sample_outputs/football_demo_reference/README.md](docs/sample_outputs/football_demo_reference/README.md)
- Replay reference: [docs/sample_outputs/football_replay_reference/README.md](docs/sample_outputs/football_replay_reference/README.md)
- Strategy sweep reference: [docs/sample_outputs/football_sweep_reference/README.md](docs/sample_outputs/football_sweep_reference/README.md)

Regenerate those committed packs from the bundled inputs with:

```bash
python scripts/refresh_sample_outputs.py
```

The underlying CLI paths remain:

```bash
pmfe football-demo --input data/sample_football_markets.json --run-id football-demo-reference
pmfe football-replay --sample --config configs/football_strategy_baseline.json --run-id football-replay-reference
pmfe football-sweep --sample --config configs/football_sweep.json --run-id football-sweep-reference
```

Those paths:

- price the bundled football snapshot sample from `data/sample_football_markets.json`
- replay the bundled football frame sample from `data/sample_football_replay.jsonl`
- compare committed pricing/no-trade configurations from `configs/football_sweep.json`

A tighter explanation of the replay flow lives in `docs/football_replay_walkthrough.md`.
The strategy comparison layer is documented in `docs/football_strategy_sweep_walkthrough.md`.

## Football Reviewer Path

For a sports-trading review, start with the committed football artifacts rather than generated `runs/<run_id>/` directories.

Concrete examples: [docs/football_decision_casebook.md](docs/football_decision_casebook.md)

### 60-Second Path

1. [docs/sample_outputs/football_demo_reference/README.md](docs/sample_outputs/football_demo_reference/README.md)
2. [docs/sample_outputs/football_demo_reference/football_edges.csv](docs/sample_outputs/football_demo_reference/football_edges.csv)
3. [docs/football_trading_research_note.md](docs/football_trading_research_note.md)
4. [docs/sample_outputs/football_replay_reference/football_report.md](docs/sample_outputs/football_replay_reference/football_report.md)

### 5-Minute Path

1. [docs/sample_outputs/README.md](docs/sample_outputs/README.md)
2. [docs/sample_outputs/football_demo_reference/README.md](docs/sample_outputs/football_demo_reference/README.md)
3. [docs/sample_outputs/football_replay_reference/README.md](docs/sample_outputs/football_replay_reference/README.md)
4. [docs/sample_outputs/football_replay_reference/football_report.md](docs/sample_outputs/football_replay_reference/football_report.md)
5. [docs/sample_outputs/football_sweep_reference/README.md](docs/sample_outputs/football_sweep_reference/README.md)
6. [docs/sample_outputs/football_sweep_reference/football_strategy_report.md](docs/sample_outputs/football_sweep_reference/football_strategy_report.md)
7. [docs/sample_outputs/football_sweep_reference/football_strategy_best.json](docs/sample_outputs/football_sweep_reference/football_strategy_best.json)
8. [docs/football_trading_research_note.md](docs/football_trading_research_note.md)
9. Only then regenerate the packs with `pmfe football-demo --input data/sample_football_markets.json --run-id football-demo-reference`, `pmfe football-replay --sample --config configs/football_strategy_baseline.json --run-id football-replay-reference`, and `pmfe football-sweep --sample --config configs/football_sweep.json --run-id football-sweep-reference`.

## Football Research Note

[docs/football_trading_research_note.md](docs/football_trading_research_note.md) is the short narrative layer over the committed football snapshot, replay, and sweep packs. It explains fair-value construction, no-trade discipline, replay evaluation, strategy comparison, and limits without relying on local `runs/<run_id>/` outputs.

For concrete market and decision examples from the same committed packs, open [docs/football_decision_casebook.md](docs/football_decision_casebook.md).

## BTC Execution Sandbox

The BTC path remains the secondary execution sandbox and the only end-to-end paper/live implementation in the repo.

Fresh clone:

```bash
python -m pip install -e .[dev]
pmfe demo
```

That one command runs fully offline against the bundled BTC replay sample in `data/sample_replay.jsonl`, writes artifacts under `runs/<run_id>/`, and prints a JSON summary with the output directory and artifact paths.

The alternate explicit BTC form is:

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
- export offline football pricing, replay, and strategy-sweep artifacts for inspection and review

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

Committed sample-output packs for those football paths live under [docs/sample_outputs/README.md](docs/sample_outputs/README.md) and are generated from the bundled sample inputs.

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
- football is an offline pricing/replay/strategy-comparison workflow only, not a live trading path
- the football sweep is an evaluation/tooling exercise on synthetic data, not production validation
