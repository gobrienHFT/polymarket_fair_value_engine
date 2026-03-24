# Football Post-Trade Analysis Note

## Scope

This note is a post-trade and post-quote review of the committed football replay and sweep artifacts under `docs/sample_outputs/`. It does not use local runs. Its purpose is to show what the repo measures after a quote decision, why the engine stands down in certain states, and what the outputs suggest to tune next.

## What The Replay Measures

The replay pack records five related views of the same process. `football_replay_quotes.csv` shows whether a market snapshot produced a `buy_yes`, `sell_yes`, or `no_trade` decision. `football_markouts.csv` measures what happened next in both raw midpoint terms and decision-aligned terms such as `directional_next_capture`, `directional_2step_capture`, and `directional_eventual_capture`. `football_calibration.csv` buckets those outcomes by edge bucket, market type, and match phase. `football_no_trade_reasons.csv` counts why the engine stood down. `football_state_changes.csv` records kickoff, goals, equalizers, cards, lead changes, and finishes so the analysis can be tied back to match-state transitions.

## Markout And Directional Capture

The committed replay report covers 64 priced market snapshots, of which 17 are quoteable under the baseline config. Across those quoteable rows, the average raw next-mid move is `0.04125`, the average directional next capture is `0.05625`, and the positive capture rate is `0.6875`. Those numbers are small-sample diagnostics, not performance claims, but they are enough to compare whether the sign of the decision and the sign of the subsequent move line up.

Two committed rows show why both short-horizon and eventual metrics matter. In `football_markouts.csv`, `int-juv-away-win` at frame `int-juv-20260413-01` is a pregame `buy_yes` with `fair_yes = 0.279976` versus `current_mid_yes = 0.24`. The next midpoint moves to `0.29`, so `directional_next_capture = 0.05`; two steps later it reaches `0.33`, so `directional_2step_capture = 0.09`; and the eventual settlement is `1.0`, which gives `directional_eventual_capture = 0.76`. That is the clean version of the workflow working as intended.

The opposite shape also appears in the committed sample. `ars-che-home-win` at frame `ars-che-20260412-04` is an in-play `buy_yes` with `fair_yes = 0.44999` versus `current_mid_yes = 0.41`. The next midpoint jumps to `0.72`, so `directional_next_capture = 0.31`. Two steps later the capture is already negative at `-0.09`, and by settlement `directional_eventual_capture = -0.41`. That is why the repo tracks next-snapshot, multi-step, and settlement-aligned outcomes separately instead of collapsing everything into one markout number.

The sweep results push the same idea one level higher. In the committed sweep, `more_aggressive` improves average directional next capture from the baseline's `0.05625` to `0.095556` and improves average directional 2-step capture from `0.028667` to `0.088824`, while also reducing average max adverse move from `0.212353` to `0.19`. The sweep is not proof of edge, but it does show that the repo can compare post-decision quality metrics across configurations.

## Calibration

The committed calibration file gives a useful caution. Edge bucket `0.01-0.02` has 8 observations with `average_directional_next_capture = 0.0875` and `positive_capture_rate = 1.0`. Edge bucket `0.02-0.05` has 9 observations, but `average_directional_next_capture` drops to `0.025` and `positive_capture_rate` drops to `0.375`. That does not prove smaller edges are better in general, but it is enough to challenge the assumption that a bigger displayed edge automatically means a better trade on this tiny sample.

The phase split is also informative. Pregame has 9 observations with `average_directional_next_capture = 0.057778` and `positive_capture_rate = 1.0`, while in-play has 8 observations with `average_directional_next_capture = 0.054286` and `positive_capture_rate = 0.285714`. The means are similar, but the hit-rate shape is very different. That is an argument for treating pregame and in-play restraint separately, not for claiming one phase is solved.

## No-Trade Reasons And Restraint

The committed no-trade counts show that most skipped states are deliberate, not accidental. `cooldown_after_goal` is the largest bucket at `16`, followed by `fair_inside_spread` at `11` and `finished_match_state` at `8`. Smaller but still meaningful buckets include `cooldown_after_red_card`, `high_uncertainty`, `insufficient_bookmaker_sources`, `stale_source_data`, and `suspended_match_state`.

This matters because post-trade analysis in sports markets is not just about the rows that traded. In a football setting, choosing not to quote immediately after goals, cards, or during stale-book conditions is part of the trading policy, not missing data. The replay artifacts make that restraint auditable instead of implicit.

## State Changes

The committed state-change file records 4 kickoffs, 4 finishes, 3 home-goal events, 5 away-goal events, 2 equalizers, 1 home red card, and 1 lead change.

The sweep slices show how strong the restraint still is around those states. Under the baseline config, `stable` has 17 quoteable snapshots, while `recent_goal`, `recent_red_card`, `suspended`, and `finished` all have zero. Even `more_aggressive` keeps that shape for state regimes: it increases quoteable stable snapshots to 19, but `recent_goal`, `recent_red_card`, and `suspended` still remain at zero. The first loosened configuration still refuses to trade directly through the most unstable match-state transitions.

## What This Suggests To Tune Next

The committed artifacts suggest a few narrow next questions. First, the pregame/in-play split argues for separate threshold tuning rather than one shared calibration story, because the pregame hit rate is much cleaner than the in-play hit rate in this sample. Second, the edge-bucket split suggests revisiting spread or uncertainty thresholds before assuming larger displayed edges deserve more weight. Third, the sweep slices show that `more_aggressive` improved directional capture mostly by quoting more stable snapshots and allowing one-source rows, so source-count and stable-state gating are the most defensible places to test next.

At the same time, the artifacts argue against a few overreaches. The one-source slice for `more_aggressive` shows only 2 observations, even though both are favorable, so it is too small to justify a strong relaxation claim. The state-regime slices show zero quoteable recent-goal and recent-red-card rows even in the looser configuration, which suggests cooldown policy should only be loosened after collecting much richer replay data.

## Limits

This is an offline-only football workflow. Replay outputs do not model queue position or realistic fills. The bundled sample inputs and committed sample-output packs are inspection artifacts, not production validation or evidence of persistent alpha.
