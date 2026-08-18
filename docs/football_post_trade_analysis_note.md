# Football Post-Trade Analysis Note

## Scope

This note follows what happens after a football quote decision using the replay and sweep outputs under `docs/sample_outputs/`. It covers markouts, calibration, stand-down reasons, state changes, and the next questions those results raise.

## What The Replay Measures

The replay gives five views of the same process. `football_replay_quotes.csv` shows whether a snapshot produced a `buy_yes`, `sell_yes`, or `no_trade` decision. `football_markouts.csv` measures what happened next in raw midpoint terms and in decision-aligned terms such as `directional_next_capture`, `directional_2step_capture`, and `directional_eventual_capture`. `football_calibration.csv` groups those outcomes by edge bucket, market type, and match phase. `football_no_trade_reasons.csv` counts stand-downs, while `football_state_changes.csv` ties the decisions back to kickoffs, goals, equalizers, cards, lead changes, and finishes.

## Markout And Directional Capture

The replay report covers 64 priced market snapshots, of which 17 are quoteable under the baseline config. Across those quoteable rows, the average raw next-mid move is `0.04125`, the average directional next capture is `0.05625`, and the positive capture rate is `0.6875`. These are small-sample diagnostics, but they let us ask whether the decision sign and the next market move pointed in the same direction.

Two rows show why both short-horizon and eventual metrics matter. In `football_markouts.csv`, `int-juv-away-win` at frame `int-juv-20260413-01` is a pregame `buy_yes` with `fair_yes = 0.279976` versus `current_mid_yes = 0.24`. The next midpoint moves to `0.29`, so `directional_next_capture = 0.05`; two steps later it reaches `0.33`, so `directional_2step_capture = 0.09`; and the eventual settlement is `1.0`, which gives `directional_eventual_capture = 0.76`. That is the clean case: the next few observations and the final settlement move in the chosen direction.

The opposite shape is in the same sample. `ars-che-home-win` at frame `ars-che-20260412-04` is an in-play `buy_yes` with `fair_yes = 0.44999` versus `current_mid_yes = 0.41`. The next midpoint jumps to `0.72`, so `directional_next_capture = 0.31`. Two steps later capture is negative at `-0.09`, and by settlement `directional_eventual_capture = -0.41`. That is why the replay keeps next-snapshot, multi-step, and settlement-aligned outcomes separate instead of hiding them in one markout number.

The sweep makes the same comparison at configuration level. `more_aggressive` moves average directional next capture from the baseline's `0.05625` to `0.095556` and average directional 2-step capture from `0.028667` to `0.088824`, while average max adverse move falls from `0.212353` to `0.19`. That is a comparison within this sample, not evidence of a general edge.

## Calibration

The calibration file also provides a useful caution. Edge bucket `0.01-0.02` has 8 observations with `average_directional_next_capture = 0.0875` and `positive_capture_rate = 1.0`. Edge bucket `0.02-0.05` has 9 observations, but `average_directional_next_capture` drops to `0.025` and `positive_capture_rate` drops to `0.375`. Smaller edges are not thereby better in general, but the result is enough to question the assumption that a larger displayed edge is automatically a better trade.

The phase split points in the same direction. Pregame has 9 observations with `average_directional_next_capture = 0.057778` and `positive_capture_rate = 1.0`, while in-play has 8 observations with `average_directional_next_capture = 0.054286` and `positive_capture_rate = 0.285714`. The means are similar, but the hit-rate shape is very different. Pregame and in-play should therefore be treated separately; neither phase is solved by this sample.

## No-Trade Reasons And Restraint

The no-trade counts show that most skipped states are deliberate. `cooldown_after_goal` is the largest bucket at `16`, followed by `fair_inside_spread` at `11` and `finished_match_state` at `8`. Smaller buckets include `cooldown_after_red_card`, `high_uncertainty`, `insufficient_bookmaker_sources`, `stale_source_data`, and `suspended_match_state`.

This matters because post-trade analysis is not only about rows that traded. In football, choosing not to quote just after a goal or card, or when the book is stale, is part of the policy. The replay records that restraint instead of making it look like missing data.

## State Changes

The state-change file records 4 kickoffs, 4 finishes, 3 home-goal events, 5 away-goal events, 2 equalizers, 1 home red card, and 1 lead change.

The sweep slices show how strong the restraint still is around those states. Under the baseline config, `stable` has 17 quoteable snapshots, while `recent_goal`, `recent_red_card`, `suspended`, and `finished` all have zero. Even `more_aggressive` keeps that shape for state regimes: it increases quoteable stable snapshots to 19, but `recent_goal`, `recent_red_card`, and `suspended` still remain at zero. The first loosened configuration still refuses to trade directly through the most unstable match-state transitions.

## What This Suggests To Tune Next

The results suggest a few narrow next questions. First, the pregame/in-play split argues for separate thresholds rather than one shared calibration rule, because the pregame hit rate is much cleaner in this sample. Second, the edge buckets suggest revisiting spread or uncertainty thresholds before giving larger displayed edges more weight. Third, the sweep slices show that `more_aggressive` improved directional capture mostly by quoting more stable snapshots and allowing one-source rows, so source-count and stable-state gating are sensible places to test next.

The same results argue for restraint. The one-source slice for `more_aggressive` has only 2 observations, even though both are favorable, so it is too small to justify relaxing the gate. The state-regime slices have zero quoteable recent-goal and recent-red-card rows even in the looser configuration. Any cooldown change should wait for much richer replay data.

## Limits

This is an offline-only football workflow. Replay does not model queue position or realistic fills. The bundled inputs and sample packs are useful for following the analysis, not for production validation or evidence of persistent alpha.
