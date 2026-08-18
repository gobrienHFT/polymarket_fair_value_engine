# Football Strategy Configuration Note

## Scope

This note describes the small set of football policy settings that sits on top of the offline fair-value and replay workflow. The config does not change bookmaker normalization or binary market mapping. It controls how fair value becomes a directional quote candidate, when the system stands down, and how several settings are compared on the same replay sample.

## Baseline Configuration

The baseline lives in `configs/football_strategy_baseline.json` and is used by the replay reference. It takes the fair-value output from the pricing layer, expresses it on a `0.01` quote tick, and centers candidate quotes around fair value with a `quote_base_half_spread` of `0.02`. It does not cross the market or add a separate predictive signal. It turns the existing fair-value estimate into buy/sell intent only when the displayed book is meaningfully away from it.

The same config defines the restraint layer. Baseline requires at least two bookmaker sources, treats source data older than 180 seconds as stale, and rejects books that are too wide (`wide_yes_spread_threshold = 0.12`) or too uncertain (`high_uncertainty_threshold = 0.08`, `high_disagreement_threshold = 0.08`). Goals add a `0.04` uncertainty boost and a 3-minute cooldown; red cards add a `0.05` boost and a 5-minute cooldown; suspended states add a `0.10` uncertainty boost. Together, these settings decide when fair value is allowed to become an action and when it is blocked.

## What The Sweep Changes

The sweep in `configs/football_sweep.json` varies the same small set of policy knobs. It does not introduce new models. The main dimensions are:

- quote aggressiveness through `quote_base_half_spread`
- source-quality gating through `minimum_bookmaker_sources` and `stale_source_data_seconds`
- book-quality and uncertainty gating through `wide_yes_spread_threshold`, `high_uncertainty_threshold`, and `high_disagreement_threshold`
- state handling through goal/red-card cooldown lengths and uncertainty boosts, plus the suspended-state boost

The differences are concrete in the configs. `tighter_quotes` reduces the half-spread to `0.015` but tightens stale-source and disagreement thresholds. `more_conservative` widens the half-spread to `0.025`, shortens the stale cutoff to 120 seconds, and extends goal/red-card cooldowns to 5 and 7 minutes. `more_aggressive` does the opposite: it allows one bookmaker source, extends the stale cutoff to 300 seconds, widens the acceptable YES spread to `0.16`, loosens uncertainty thresholds to `0.12`, and shortens cooldowns to 1 and 2 minutes.

## How The Winner Is Chosen

The sweep ranks strategies on directional evaluation rather than raw midpoint drift. The selection block in `configs/football_sweep.json` requires at least 8 quoteable snapshots, uses `average_directional_next_capture` as the primary metric, and applies tie-breakers in this order: `average_directional_2step_capture`, `positive_capture_rate`, and `-average_max_adverse_move`. The winner therefore needs both direction-correct post-decision movement and enough quoteable observations to be useful for comparison.

The sweep writes three useful views. `football_strategy_results.csv` is the leaderboard, `football_strategy_slices.csv` breaks behavior down by phase, side, market type, and state regime, and `football_strategy_best.json` records the winner and comparison reason. The best-strategy summary selects `more_aggressive` because it ranks first under the configured directional-capture rule on this synthetic sample, not because it proves production alpha.

| Strategy | Quoteable snapshots | Avg directional next capture | Avg directional 2-step capture | Positive capture rate |
| --- | ---: | ---: | ---: | ---: |
| `more_aggressive` | 19 | 0.095556 | 0.088824 | 0.722222 |
| `baseline` | 17 | 0.05625 | 0.028667 | 0.6875 |
| `more_conservative` | 17 | 0.05625 | 0.028667 | 0.6875 |
| `tighter_quotes` | 17 | 0.05625 | 0.028667 | 0.6875 |

The table is small on purpose. Four settings on a small replay sample are enough to show the comparison method, not enough to support a broader conclusion.

## Why It Matters

The config surface makes strategy ownership explicit rather than stopping at the pricing model. A small set of knobs is varied under fixed inputs, then evaluated with declared metrics. That separates fair-value construction, trading restraint, and configuration comparison instead of blending them into one preference.

In practical terms, this is parameter ownership, calibration discipline, and fixed-input strategy comparison. The winner is not "the best model"; it is the configuration that scored best under the declared rule set on the bundled sample.

## Limits

The football replay sample is bundled and synthetic. Football remains offline-only. The sweep compares quote-decision quality on a fixed replay sample; it is not evidence of production alpha or live football readiness.
