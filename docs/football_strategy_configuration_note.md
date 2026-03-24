# Football Strategy Configuration Note

## Scope

This note describes the football configuration surface that sits on top of the repo's offline fair-value and replay workflow. The config does not change the underlying bookmaker normalization or binary market mapping. It controls how fair value is turned into directional quote candidates, how aggressively the system stands down, and how multiple parameter sets are compared on the same bundled replay sample.

## Baseline Configuration

The baseline lives in `configs/football_strategy_baseline.json` and is also the config used by the committed replay reference. Its purpose is straightforward: take the fair-value output from the football pricing layer, express it on a `0.01` quote tick, and center candidate quotes around fair value with a `quote_base_half_spread` of `0.02`. That means the baseline is not trying to cross the market or manufacture a separate predictive signal. It is taking the existing fair-value estimate and turning it into directional buy/sell intent only when the displayed book is meaningfully away from that estimate.

The same config also defines the restraint layer. Baseline requires at least two bookmaker sources, treats source data older than 180 seconds as stale, and rejects books that are too wide (`wide_yes_spread_threshold = 0.12`) or too uncertain (`high_uncertainty_threshold = 0.08`, `high_disagreement_threshold = 0.08`). It then adds explicit state-aware handling: goals add a `0.04` uncertainty boost and a 3-minute cooldown, red cards add a `0.05` boost and a 5-minute cooldown, and suspended states add a `0.10` uncertainty boost. In other words, the baseline config is a policy for when fair value should be allowed to become an action and when it should be blocked.

## What The Sweep Changes

The sweep in `configs/football_sweep.json` varies the same small set of policy knobs rather than introducing new models. The main dimensions are:

- quote aggressiveness through `quote_base_half_spread`
- source-quality gating through `minimum_bookmaker_sources` and `stale_source_data_seconds`
- book-quality and uncertainty gating through `wide_yes_spread_threshold`, `high_uncertainty_threshold`, and `high_disagreement_threshold`
- state handling through goal/red-card cooldown lengths and uncertainty boosts, plus the suspended-state boost

Those differences are concrete in the committed configs. `tighter_quotes` reduces the half-spread to `0.015` but also tightens stale-source and disagreement thresholds. `more_conservative` widens the half-spread to `0.025`, shortens the stale cutoff to 120 seconds, and extends goal/red-card cooldowns to 5 and 7 minutes. `more_aggressive` does the opposite: it allows one bookmaker source, extends the stale cutoff to 300 seconds, widens the acceptable YES spread to `0.16`, loosens uncertainty thresholds to `0.12`, and shortens cooldowns to 1 and 2 minutes.

## How The Winner Is Chosen

The committed sweep ranks strategies on directional evaluation rather than raw midpoint drift. The selection block in `configs/football_sweep.json` requires at least 8 quoteable snapshots, uses `average_directional_next_capture` as the primary metric, and applies tie-breakers in this order: `average_directional_2step_capture`, `positive_capture_rate`, and `-average_max_adverse_move`. That means the winner is chosen for producing better direction-correct post-decision movement while still generating enough opportunities to matter.

The sweep outputs also keep the diagnostic layers visible. `football_strategy_results.csv` provides the strategy-level leaderboard, `football_strategy_slices.csv` breaks behavior down by phase, side, market type, and state regime, and `football_strategy_best.json` records the winner plus the exact comparison reason. The committed best-strategy summary selects `more_aggressive`, not because it proves production alpha, but because it ranked first on the configured directional-capture rule set within this synthetic sample.

| Strategy | Quoteable snapshots | Avg directional next capture | Avg directional 2-step capture | Positive capture rate |
| --- | ---: | ---: | ---: | ---: |
| `more_aggressive` | 19 | 0.095556 | 0.088824 | 0.722222 |
| `baseline` | 17 | 0.05625 | 0.028667 | 0.6875 |
| `more_conservative` | 17 | 0.05625 | 0.028667 | 0.6875 |
| `tighter_quotes` | 17 | 0.05625 | 0.028667 | 0.6875 |

That table is intentionally small. It shows the committed comparison surface without pretending that a four-strategy sweep on a small replay sample is enough to support a stronger claim.

## What This Demonstrates

This configuration surface shows ownership of strategy parameters rather than just ownership of a pricing model. The repo defines a bounded set of knobs, varies them under fixed inputs, and evaluates the result with explicit metrics instead of narrative preference. That is useful because it separates three tasks that often get blurred together: fair-value construction, trading restraint, and configuration comparison. The committed artifacts show that those layers can be inspected independently.

In practical terms, the repo demonstrates parameter ownership, calibration discipline, and fixed-input strategy comparison. The winner is not "the best model"; it is the configuration that scored best under the declared rule set on the declared bundled sample.

## Limits

The football replay sample is bundled and synthetic. Football remains offline-only in this repo. The sweep compares quote-decision quality metrics on a fixed replay sample and should not be read as a claim of production alpha or live football trading readiness.
