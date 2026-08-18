# Football Decision Casebook

## Scope

This note works through four football decisions using the snapshot, replay, and sweep outputs under `docs/sample_outputs/`. The examples follow the path from bookmaker fair value to a trading decision, a stand-down, a markout, and a configuration comparison.

For match-state shock and reaction-risk commentary from the same replay, see [docs/football_match_state_reaction_note.md](football_match_state_reaction_note.md).

## Example 1: Fair Value To Actionable Edge

The clearest snapshot example is `real-madrid-vs-barcelona-home-or-draw` in the football snapshot reference. The fixture is Real Madrid vs Barcelona, and the market asks whether Real Madrid avoids defeat. The row in `football_edges.csv` gives `fair_yes = 0.67526`, `market_mid_yes = 0.625`, `best_bid_yes = 0.61`, and `best_ask_yes = 0.64`. That produces `buy_edge_vs_ask = 0.03526`, `edge_vs_mid = 0.05026`, and `max_actionable_edge = 0.03526`, so the decision side is `buy_yes`.

This is a useful fair-value example because the ask sits a little more than three points below the de-vigged bookmaker consensus. The edge is modest, but the decision is easy to reconstruct: normalize 1X2 odds, map home-or-draw into a binary YES probability, compare fair value with the displayed ask, and only then call the row actionable.

## Example 2: Explicit No-Trade State

The replay reference contains a stronger example of restraint than a missing-data row. At frame `ars-che-20260412-06` in `football_replay_quotes.csv`, Arsenal vs Chelsea is 1-1 in the 61st minute immediately after a Chelsea goal and equalizer. The draw market has `fair_yes = 0.499962`, `best_bid_yes = 0.44`, `best_ask_yes = 0.48`, and `buy_edge_vs_ask = 0.019962`. On price alone that looks like a small buy.

The system still stands down. The row is tagged with `goal_away` and `equalizer`, the regime is `recent_goal`, uncertainty is boosted to `0.04`, and `no_trade_reason` is `cooldown_after_goal`. Recent state transitions can dominate the next few snapshots, so the engine prefers a temporary no-trade to forcing a quote through a match-state shock. The positive edge is deliberately ignored.

## Example 3: Replay Evaluation

For a concrete decision-and-evaluation chain, the replay markouts for Inter vs Juventus provide a clean example. At frame `int-juv-20260413-01` in `football_markouts.csv`, the market is `away_win` and the decision side is `buy_yes`. The row shows `fair_yes = 0.279976` against `current_mid_yes = 0.24`, so the market is below fair value when the decision is taken.

The next observation moves in the same direction: `next_snapshot_mid_yes = 0.29`, so `raw_next_mid_change = 0.05` and `directional_next_capture = 0.05`. Two frames out, the midpoint reaches `0.33`, giving `directional_2step_capture = 0.09`. The eventual settlement for that binary market is `1.0`, which produces `directional_eventual_capture = 0.76`. This is one sample path, not evidence of a stable edge, but it shows the evaluation loop clearly: the repo records the chosen side, the next market move, the multi-step move, and the eventual resolution, all in the same directional sign convention.

## Example 4: Strategy Comparison

The sweep compares four configurations on the same replay sample and writes both a leaderboard and a winner-selection record. In `football_strategy_results.csv`, `more_aggressive` is the top row with `quoteable_snapshots = 19`, `average_directional_next_capture = 0.095556`, `average_directional_2step_capture = 0.088824`, and `positive_capture_rate = 0.722222`. The baseline row is lower on the primary comparison metric, with `quoteable_snapshots = 17` and `average_directional_next_capture = 0.05625`.

`football_strategy_best.json` records the selection rule: at least 8 quoteable snapshots are required, the primary metric is `average_directional_next_capture`, and tie-breakers are `average_directional_2step_capture`, `positive_capture_rate`, and `-average_max_adverse_move`. Under that rule, `more_aggressive` wins. This does not identify a production configuration; it shows how to compare quoting and gating choices under fixed inputs and retain the reason one row ranked first.

## Why It Matters

These examples show the parts of a sports-trading workflow that matter before live execution. Fair value comes from de-vigged bookmaker 1X2 odds and is mapped into the binary forms a prediction venue could display. Action depends on bid, ask, and spread context, not just fair value minus midpoint. No-trade decisions are explicit and state-aware. Replay shows whether the chosen side aligned with later market movement, and the sweep compares parameters without changing the underlying data.

The four questions are straightforward: how is the market priced, when does the system refuse to quote, how did a decision mark out, and what changed when the quoting policy changed?

## Limits

This is an offline-only football workflow. Replay does not model queue position or realistic fill behavior. The sample packs are small and synthetic: they explain the mechanics, but they are not production validation or evidence of alpha.
