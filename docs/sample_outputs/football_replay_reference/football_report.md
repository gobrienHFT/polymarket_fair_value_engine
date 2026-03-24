# Football Replay Report

## Summary
- Run ID: `football-replay-reference`
- Fixtures: `4`
- Frame snapshots: `32`
- Priced market snapshots: `64`
- Quoteable market snapshots: `17`
- Positive-edge market snapshots: `27`
- Average raw next-mid change: `0.04125`
- Average directional next capture: `0.05625`
- Positive capture rate: `0.6875`

## Markout Definitions
- `raw_next_mid_change`: next midpoint minus current midpoint.
- `directional_next_capture`: the next midpoint move expressed in the chosen decision direction.
- `raw_2step_mid_change`: midpoint change two frames forward versus the current midpoint.
- `directional_2step_capture`: the 2-step midpoint move expressed in the chosen decision direction.
- `raw_eventual_resolution_change`: final settlement minus the current midpoint.
- `directional_eventual_capture`: final settlement move expressed in the chosen decision direction.
- Legacy fields such as `next_snapshot_markout` and `eventual_resolution_markout` are preserved as aliases for the raw metrics.

## Quote Decision Fields
- `buy_edge_vs_ask`: fair YES minus the current best ask.
- `sell_edge_vs_bid`: current best bid minus fair YES.
- `max_actionable_edge`: `max(buy_edge_vs_ask, sell_edge_vs_bid, 0.0)`.

## State Changes
- `2026-04-12T14:00:00+00:00` `ars-che-20260412` `kickoff` at minute `0`
- `2026-04-12T14:34:00+00:00` `ars-che-20260412` `goal_home` at minute `34`
- `2026-04-12T15:01:00+00:00` `ars-che-20260412` `goal_away` at minute `61`
- `2026-04-12T15:01:00+00:00` `ars-che-20260412` `equalizer` at minute `61`
- `2026-04-12T15:36:00+00:00` `ars-che-20260412` `finish` at minute `96`
- `2026-04-13T19:45:00+00:00` `int-juv-20260413` `kickoff` at minute `0`
- `2026-04-13T20:12:00+00:00` `int-juv-20260413` `red_card_home` at minute `27`
- `2026-04-13T20:54:00+00:00` `int-juv-20260413` `goal_away` at minute `69`
- `2026-04-13T21:21:00+00:00` `int-juv-20260413` `finish` at minute `96`
- `2026-04-12T16:30:00+00:00` `liv-tot-20260412` `kickoff` at minute `0`
- `2026-04-12T16:48:00+00:00` `liv-tot-20260412` `goal_away` at minute `18`
- `2026-04-12T17:22:00+00:00` `liv-tot-20260412` `goal_home` at minute `52`
- `2026-04-12T17:22:00+00:00` `liv-tot-20260412` `lead_change` at minute `52`
- `2026-04-12T18:06:00+00:00` `liv-tot-20260412` `finish` at minute `96`
- `2026-04-14T20:00:00+00:00` `rm-bar-20260414` `kickoff` at minute `0`
- `2026-04-14T20:23:00+00:00` `rm-bar-20260414` `goal_home` at minute `23`
- `2026-04-14T20:57:00+00:00` `rm-bar-20260414` `goal_away` at minute `57`
- `2026-04-14T20:57:00+00:00` `rm-bar-20260414` `equalizer` at minute `57`
- `2026-04-14T21:19:00+00:00` `rm-bar-20260414` `goal_away` at minute `79`
- `2026-04-14T21:36:00+00:00` `rm-bar-20260414` `finish` at minute `96`

## Calibration Snapshot
- `edge_bucket` `0.01-0.02`: n=8, avg_raw_next=0.025, avg_dir_next=0.0875, hit_rate=1.0
- `edge_bucket` `0.02-0.05`: n=9, avg_raw_next=0.0575, avg_dir_next=0.025, hit_rate=0.375
- `market_type` `away_or_draw`: n=2, avg_raw_next=0.115, avg_dir_next=0.165, hit_rate=1.0
- `market_type` `away_win`: n=3, avg_raw_next=0.05, avg_dir_next=-0.016667, hit_rate=0.333333
- `market_type` `draw`: n=3, avg_raw_next=-0.055, avg_dir_next=0.025, hit_rate=0.5
- `market_type` `either_team_wins`: n=2, avg_raw_next=0.035, avg_dir_next=0.005, hit_rate=0.5
- `market_type` `home_or_draw`: n=3, avg_raw_next=-0.033333, avg_dir_next=0.026667, hit_rate=0.666667
- `market_type` `home_win`: n=4, avg_raw_next=0.105, avg_dir_next=0.12, hit_rate=1.0
- `match_phase` `inplay`: n=8, avg_raw_next=0.091429, avg_dir_next=0.054286, hit_rate=0.285714
- `match_phase` `pregame`: n=9, avg_raw_next=0.002222, avg_dir_next=0.057778, hit_rate=1.0

## No-Trade Counts
- `cooldown_after_goal`: `16`
- `cooldown_after_red_card`: `2`
- `fair_inside_spread`: `11`
- `finished_match_state`: `8`
- `high_uncertainty`: `2`
- `insufficient_bookmaker_sources`: `2`
- `missing_yes_book`: `1`
- `stale_source_data`: `2`
- `suspended_match_state`: `2`
- `wide_yes_spread`: `1`

## Limitations
- Replay frames are bundled offline sample data.
- In-play fair value still comes directly from bundled bookmaker 1X2 updates rather than an independent in-play model.
- Directional capture metrics are about quote-decision quality, not about simulated fill realism.
- The sample is small, so calibration and markout statistics are illustrative rather than statistically strong.
