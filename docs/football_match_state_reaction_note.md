# Football Match-State And Reaction Note

## Scope

This note is a state-change and reaction-risk summary built from the committed football replay artifacts under `docs/sample_outputs/`. It focuses on how the repo records match-state shocks, how those shocks affect whether the system quotes or stands down, and why an apparent edge is not always tradable immediately after a football event.

## What State Changes Are Tracked

The committed replay artifacts track both explicit event changes and broader state regimes. In `football_state_changes.csv`, the sample records `kickoff`, `goal_home`, `goal_away`, `equalizer`, `red_card_home`, `lead_change`, and `finish`. The replay quotes then convert those events into higher-level regimes such as `recent_goal`, `recent_red_card`, `suspended`, `stable`, and `finished`.

That split matters. The raw event labels show what happened in the match, while the state regime shows how the trading layer should react. In the committed sample there are 4 kickoffs, 4 finishes, 3 home-goal events, 5 away-goal events, 2 equalizers, 1 home red card, and 1 lead change. The no-trade summary then shows the corresponding reaction policy: `cooldown_after_goal` appears 16 times, `cooldown_after_red_card` 2 times, `suspended_match_state` 2 times, and `finished_match_state` 8 times.

## Goal And Equalizer Reactions

Goals and equalizers are the clearest reaction-risk case in the committed replay. They do not just change fair value; they also trigger a temporary stand-down. The strongest example is already visible in the decision casebook: at frame `ars-che-20260412-06`, Arsenal vs Chelsea is 1-1 in the 61st minute immediately after a Chelsea goal and equalizer. The draw market has `fair_yes = 0.499962`, `best_ask_yes = 0.48`, and `buy_edge_vs_ask = 0.019962`, so price alone suggests a small buy.

The system still does not quote. That same row is tagged with `goal_away` and `equalizer`, the regime is `recent_goal`, uncertainty is `0.04`, and the recorded `no_trade_reason` is `cooldown_after_goal`. The same pattern appears elsewhere in the committed replay. Liverpool vs Tottenham at frame `liv-tot-20260412-05` has a `goal_home` and `lead_change` at minute 52; the `away_or_draw` market still shows `buy_edge_vs_ask = 0.025075`, but the row is again `no_trade` because the engine is inside the post-goal cooldown.

That is the right interpretation for football markets. Immediately after a goal or equalizer, visible prices can move sharply while information is still being digested. The repo treats that period as reaction-risk rather than as a free edge.

## Red Cards And Suspensions

Red cards and suspensions are handled with the same explicit restraint. At frame `int-juv-20260413-04`, Inter vs Juventus reaches minute 27 with a home red card. The event log records `red_card_home`, the replay quote row moves into `recent_red_card`, uncertainty rises to `0.05`, and both tracked markets are `no_trade` with `cooldown_after_red_card`. For `int-juv-away-win`, fair value is `0.379993` and the market sits around `0.38`, but the engine still stands down rather than quoting into the immediate aftermath of the card.

Suspensions are even stricter. At frame `rm-bar-20260414-06`, Real Madrid vs Barcelona is suspended at minute 58 with the score level at 1-1. The replay quote rows move to state regime `suspended`, uncertainty jumps to `0.1`, and `no_trade_reason` becomes `suspended_match_state`. The draw and `either_team_wins` markets are both blocked even though the books are present. That is the correct posture for an interrupted football market: the issue is not only price, but whether the trading state itself is reliable enough to act on.

## Why Apparent Edge Is Not Always Actionable

The committed replay makes the core point very clearly: edge and action are not the same thing. The Arsenal-Chelsea draw row at frame `ars-che-20260412-06` is the cleanest example because it combines all three ingredients at once. The market shows a positive buy edge, the fair-to-mid relationship is supportive, and yet the decision is still `no_trade`. The reason is not that the pricing layer failed; it is that the reaction layer correctly recognized the equalizer as a state shock.

Other committed rows show the same logic for different causes. Liverpool-Tottenham `away_or_draw` at frame `liv-tot-20260412-05` has `max_actionable_edge = 0.025075` but is blocked by `cooldown_after_goal`. Inter-Juventus `away_win` at frame `int-juv-20260413-05` has `max_actionable_edge = 0.014998` but is blocked by `insufficient_bookmaker_sources` because only one bookmaker is present. The point is that a sports-trading workflow should not collapse tradability into a single fair-minus-price number.

## What This Demonstrates

This note shows that the repo treats football markets as stateful, not just numerical. It tracks match-state shocks, reacts to them with explicit cooldowns or hard no-trade states, and records those decisions in a way that can be reviewed after the fact. That is useful for sports-trading work because reaction-time discipline matters just as much as pricing accuracy around goals, cards, suspensions, and other regime breaks.

More practically, the repo demonstrates four things: match-state awareness, reaction-time discipline, explicit restraint under unstable information, and a refusal to force action through state shocks just because a displayed edge exists. Those are all qualities a reviewer would want to see before thinking about any live football extension.

## Limits

This is still an offline-only football workflow. Replay outputs do not model queue position or realistic fills. The bundled sample inputs and committed sample-output packs are inspection artifacts, not production validation or evidence of persistent alpha.
