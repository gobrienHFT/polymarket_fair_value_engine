# Football Research Dashboard

## Scope

This is a one-page summary of the repo's football pricing, replay, and strategy-comparison workflow built only from the committed football artifacts under `docs/sample_outputs/`. It is intended as a fast inspection page for the offline football path rather than as evidence of live execution or production validation.

## Snapshot Pricing

- The committed snapshot pack prices `12` binary football markets across `4` fixtures in [docs/sample_outputs/football_demo_reference/football_fair_values.csv](sample_outputs/football_demo_reference/football_fair_values.csv).
- `5` of those `12` markets show positive actionable edge in [docs/sample_outputs/football_demo_reference/football_edges.csv](sample_outputs/football_demo_reference/football_edges.csv) when ranked on `max_actionable_edge`.
- The largest committed snapshot edge is `Real Madrid avoid defeat vs Barcelona` with `fair_yes = 0.67526`, `best_ask_yes = 0.64`, and `buy_edge_vs_ask = 0.03526`.
- The committed snapshot also shows both buy and sell directions: `Liverpool vs Tottenham either_team_wins` has `buy_edge_vs_ask = 0.025262`, while `Juventus win at Inter` has `fair_yes = 0.32289`, `best_bid_yes = 0.34`, and `sell_edge_vs_bid = 0.01711`.

## Replay Evaluation

- The committed replay report covers `4` fixtures and `32` frame snapshots, producing `64` priced market snapshots and `17` quoteable snapshots under the baseline configuration.
- Average raw next-mid change is `0.04125`, while average directional next capture is `0.05625` with a positive capture rate of `0.6875`. That split matters because directional capture scores the move in the direction of the chosen action rather than treating all midpoint drift the same way.
- The committed calibration output shows that the `0.01-0.02` edge bucket has `n = 8`, average directional next capture `0.0875`, and hit rate `1.0`, while the `0.02-0.05` bucket has `n = 9`, average directional next capture `0.025`, and hit rate `0.375`.
- No-trade restraint is visible in the replay artifacts: `cooldown_after_goal = 16`, `fair_inside_spread = 11`, and `finished_match_state = 8` are the largest committed no-trade buckets.

## Strategy Sweep

- The committed sweep winner is `more_aggressive`, recorded in [docs/sample_outputs/football_sweep_reference/football_strategy_best.json](sample_outputs/football_sweep_reference/football_strategy_best.json).
- It wins on `average_directional_next_capture` under the configured quote-count filter, with the committed reason recorded as: first on the primary metric, then tie-breakers on `average_directional_2step_capture`, `positive_capture_rate`, and `-average_max_adverse_move`.

| Strategy | Quoteable snapshots | Avg directional next capture | Positive capture rate |
| --- | --- | --- | --- |
| `more_aggressive` | `19` | `0.095556` | `0.722222` |
| `baseline` | `17` | `0.05625` | `0.6875` |
| `more_conservative` | `17` | `0.05625` | `0.6875` |

- This is a fixed-input configuration comparison, not a production-alpha claim. The value is in showing how the repo compares strategy settings on the same replay sample and records why one row ranked above another.

## Notes To Read Next

- [docs/football_trading_research_note.md](football_trading_research_note.md)
- [docs/football_decision_casebook.md](football_decision_casebook.md)
- [docs/football_strategy_configuration_note.md](football_strategy_configuration_note.md)
- [docs/football_post_trade_analysis_note.md](football_post_trade_analysis_note.md)
- [docs/football_match_state_reaction_note.md](football_match_state_reaction_note.md)

## Limits

- football is an offline-only workflow in this repo
- replay fills have no queue-position realism
- bundled sample inputs and committed sample-output packs are for inspection, not production validation
