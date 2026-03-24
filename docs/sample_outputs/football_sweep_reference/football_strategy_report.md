# Football Strategy Sweep Report

## Overview
- This sweep compares multiple offline football quote/no-trade configurations on the same bundled synthetic replay dataset.
- The ranking uses directional capture metrics, not raw midpoint drift alone.

## Compared Strategies
- `more_aggressive`: Shorter cooldowns and looser source/spread gating
- `baseline`: Current default config
- `more_conservative`: Longer cooldowns and stricter stale/uncertainty gating
- `tighter_quotes`: Smaller base half-spread and stricter disagreement gating

## Selection Rule
- Minimum quoteable snapshots: `8`
- Primary metric: `average_directional_next_capture`
- Tie-breakers: `average_directional_2step_capture, positive_capture_rate, -average_max_adverse_move`

## Leaderboard
- `more_aggressive`: quoteable=19, avg_dir_next=0.095556, avg_dir_2step=0.088824, hit_rate=0.722222, note=None
- `baseline`: quoteable=17, avg_dir_next=0.05625, avg_dir_2step=0.028667, hit_rate=0.6875, note=None
- `more_conservative`: quoteable=17, avg_dir_next=0.05625, avg_dir_2step=0.028667, hit_rate=0.6875, note=None
- `tighter_quotes`: quoteable=17, avg_dir_next=0.05625, avg_dir_2step=0.028667, hit_rate=0.6875, note=None

## Regime Breakdowns
- `decision_side` `buy_yes`: n=11, quoteable=11, avg_dir_next=0.119, avg_dir_2step=0.057
- `decision_side` `sell_yes`: n=8, quoteable=8, avg_dir_next=0.06625, avg_dir_2step=0.134286
- `market_type` `away_or_draw`: n=8, quoteable=2, avg_dir_next=0.165, avg_dir_2step=-0.03
- `market_type` `away_win`: n=8, quoteable=4, avg_dir_next=0.09, avg_dir_2step=0.196667
- `market_type` `draw`: n=16, quoteable=3, avg_dir_next=0.025, avg_dir_2step=0.05
- `market_type` `either_team_wins`: n=8, quoteable=2, avg_dir_next=0.005, avg_dir_2step=0.08
- `market_type` `home_or_draw`: n=8, quoteable=4, avg_dir_next=0.1225, avg_dir_2step=0.18
- `market_type` `home_win`: n=16, quoteable=4, avg_dir_next=0.12, avg_dir_2step=0.0325

## Best Strategy
- Winner: `more_aggressive`

## Why It Won
- Required at least 8 quoteable snapshots. Winner `more_aggressive` ranked first on `average_directional_next_capture` with tie-breakers `average_directional_2step_capture, positive_capture_rate, -average_max_adverse_move`.

## Important Caveats
- The replay sample is synthetic and small.
- This is a tooling/evaluation exercise, not production validation or proof of alpha.
- The sweep compares quote-decision quality metrics and does not claim realistic live fill behavior.
