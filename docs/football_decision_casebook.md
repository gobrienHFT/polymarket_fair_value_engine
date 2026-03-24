# Football Decision Casebook

## Scope

This note is a concrete, example-based companion to the committed football sample-output packs under `docs/sample_outputs/`. It uses only those checked-in snapshot, replay, and sweep artifacts to show how the repo moves from bookmaker fair value to trading action, restraint, evaluation, and parameter comparison.

## Example 1: Fair Value To Actionable Edge

The clearest snapshot example is `real-madrid-vs-barcelona-home-or-draw` from the committed football snapshot reference. The fixture is Real Madrid vs Barcelona, and the market asks whether Real Madrid avoids defeat. The committed row in `football_edges.csv` gives `fair_yes = 0.67526`, `market_mid_yes = 0.625`, `best_bid_yes = 0.61`, and `best_ask_yes = 0.64`. That produces `buy_edge_vs_ask = 0.03526`, `edge_vs_mid = 0.05026`, and `max_actionable_edge = 0.03526`, so the decision side is `buy_yes`.

This is a clean fair-value example because the market is not just slightly away from the model midpoint; the ask is below the de-vigged bookmaker consensus by a little more than three points. The row is still modest rather than dramatic, which is appropriate for an inspection repo. The point is that the trading decision is explainable from first principles: normalize 1X2 odds, map home-or-draw into a binary YES probability, compare that fair value to the displayed ask, and only then label the opportunity actionable.

## Example 2: Explicit No-Trade State

The replay reference contains a stronger example of restraint than a missing-data row. At frame `ars-che-20260412-06` in `football_replay_quotes.csv`, Arsenal vs Chelsea is 1-1 in the 61st minute immediately after a Chelsea goal and equalizer. The draw market has `fair_yes = 0.499962`, `best_bid_yes = 0.44`, `best_ask_yes = 0.48`, and `buy_edge_vs_ask = 0.019962`. On price alone that looks like a small buy.

The system still stands down. The same row is tagged with state changes `goal_away` and `equalizer`, the regime is `recent_goal`, uncertainty is boosted to `0.04`, and the recorded `no_trade_reason` is `cooldown_after_goal`. That is the right kind of failure mode for a sports-trading workflow: recent state transitions can dominate the next few snapshots, so the engine prefers a temporary no-trade over forcing a quote through a match-state shock. The case is useful precisely because it shows a positive edge that is deliberately ignored.

## Example 3: Replay Evaluation

For a concrete decision-and-evaluation chain, the replay markouts for Inter vs Juventus provide a clean example. At frame `int-juv-20260413-01` in `football_markouts.csv`, the market is `away_win` and the decision side is `buy_yes`. The committed row shows `fair_yes = 0.279976` against `current_mid_yes = 0.24`, so the market is below fair value when the decision is taken.

The next committed observation moves in the same direction: `next_snapshot_mid_yes = 0.29`, so `raw_next_mid_change = 0.05` and `directional_next_capture = 0.05`. Two frames out, the midpoint reaches `0.33`, giving `directional_2step_capture = 0.09`. The eventual settlement for that binary market is `1.0`, which produces `directional_eventual_capture = 0.76`. This is still only one sample path, not evidence of a stable edge, but it shows the evaluation loop clearly: the repo records the chosen side, the next market move, the multi-step move, and the eventual resolution, all in the same directional sign convention.

## Example 4: Strategy Comparison

The committed sweep reference compares four configurations on the same replay sample and writes both a leaderboard and a winner-selection record. In `football_strategy_results.csv`, `more_aggressive` is the top row with `quoteable_snapshots = 19`, `average_directional_next_capture = 0.095556`, `average_directional_2step_capture = 0.088824`, and `positive_capture_rate = 0.722222`. The baseline row is lower on the primary comparison metric, with `quoteable_snapshots = 17` and `average_directional_next_capture = 0.05625`.

`football_strategy_best.json` makes the selection rule explicit: at least 8 quoteable snapshots are required, the primary metric is `average_directional_next_capture`, and tie-breakers are `average_directional_2step_capture`, `positive_capture_rate`, and `-average_max_adverse_move`. Under that rule, `more_aggressive` wins. The important point is not that the repo has discovered a production configuration. The point is that it can compare quoting and gating choices under fixed inputs with a deterministic rule and produce an audit trail for why one row ranked first.

## What This Demonstrates

These examples show a narrow but credible sports-trading workflow. Fair value is formed from de-vigged bookmaker 1X2 odds and mapped into the binary market forms that a prediction venue would actually display. Trading action is not just a fair-minus-midpoint number; it is a directional comparison versus bid, ask, and spread context. No-trade decisions are explicit and state-aware rather than implicit omissions. Replay outputs make it possible to inspect whether the chosen side aligned with later market movement, and the sweep layer compares parameter sets without changing the underlying data.

In other words, the repo can answer four practical questions with committed artifacts: how a football market is priced, when the system refuses to quote, how a decision is evaluated after the fact, and how two quoting policies are compared on the same sample.

## Limits

This is still an offline-only football workflow. Replay outputs do not model queue position or claim realistic fill behavior. The committed sample packs are small, synthetic inspection artifacts, so they are useful for explaining pricing and evaluation mechanics but not for production validation or claims of alpha.
