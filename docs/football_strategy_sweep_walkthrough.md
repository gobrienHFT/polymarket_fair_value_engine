# Football Strategy Sweep Walkthrough

This walkthrough explains the offline football strategy sweep only.

It does not describe live football trading, because live football trading is not implemented in this repo.

## Run It

```bash
python -m pip install -e .[dev]
pmfe football-sweep --sample --config configs/football_sweep.json --run-id verify-football-sweep
pmfe report --run-id verify-football-sweep
```

For zero-click inspection on GitHub, open [docs/sample_outputs/football_sweep_reference/README.md](sample_outputs/football_sweep_reference/README.md). That committed pack is generated from the bundled replay sample plus the committed sweep config.

## 1. Why The Sweep Exists

The replay engine already answers two useful questions:

- how fair value is formed from bookmaker 1X2 inputs
- how fair value turns into quote or no-trade decisions

The sweep adds the next research step:

- compare multiple pricing/no-trade configurations on the same replay sample
- rank them with explicit, deterministic rules
- explain why one configuration is preferred

That makes the football path more useful as a research harness without pretending it is a live trading system.

## 2. How Configs Override Behavior

`pmfe football-replay --config ...` can load a single JSON config override.

`pmfe football-sweep --config ...` loads a JSON file with multiple named strategies.

Each strategy is just a named `FootballPricingConfig`, for example:

- base quote half-spread
- minimum bookmaker sources
- stale-source threshold
- wide-spread threshold
- uncertainty threshold
- goal/red-card cooldown length
- uncertainty boosts

This means the sweep compares policy choices, not different predictive models.

## 3. Why Directional Capture Matters More Than Raw Drift

Raw midpoint drift answers:

- did the market move up or down after this frame?

Directional capture answers:

- was that move favorable for the action we actually wanted to take?

Examples:

- if the strategy wants to `BUY_YES`, an upward move is good
- if the strategy wants to `SELL_YES`, a downward move is good
- if the strategy says `NO_TRADE`, directional capture is `null`

That is why the sweep ranks strategies on directional capture metrics, not on raw midpoint drift alone.

## 4. How The Winner Is Selected

The sweep config includes:

- a minimum quoteable-snapshot threshold
- one primary metric
- an ordered list of tie-breakers

Selection rules:

1. strategies below `min_quoteable_snapshots` are disqualified unless every strategy fails the filter
2. the primary metric sorts descending
3. tie-breakers are applied in order
4. metrics with a `-` prefix mean smaller is better
5. if still tied, strategy name sorts alphabetically

The winner and the comparison reason are written to `football_strategy_best.json`.

## 5. How To Read The Regime Breakdowns

The sweep writes `football_strategy_slices.csv` with small breakdowns by:

- `match_phase`
- `decision_side`
- `market_type`
- `state_regime`
- `source_quality`

This helps answer questions like:

- was a strategy only better pregame?
- did it do worse after recent goals?
- was it relying too much on stale or one-source snapshots?

## 6. What The Output Layout Means

The top-level run contains the comparison outputs:

- `football_strategy_results.csv`
- `football_strategy_slices.csv`
- `football_strategy_report.md`
- `football_strategy_best.json`

The selected winner also gets a full nested replay run under `best_strategy/`.

That keeps the comparison layer and the detailed replay evidence in the same place.

## 7. Limitations Of The Synthetic Sample

- the replay dataset is bundled and synthetic
- fair value still comes directly from bookmaker 1X2 snapshots
- there is no fill simulation in the sweep itself
- the results are illustrative and should not be treated as production validation

The sweep is a tooling and evaluation exercise, not a claim that the best row proves real edge.

## 8. Real Next Step Later

An honest next step would be:

1. collect larger recorded replay samples from real market observation
2. keep the same directional-capture and regime-slice framework
3. compare configurations on richer datasets before making broader claims
4. only then consider adding guarded live football execution adapters
