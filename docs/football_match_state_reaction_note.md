# Football Match-State And Reaction Note

## Scope

This note follows the reaction-risk decisions in the football replay under `docs/sample_outputs/`. It looks at what the match-state changes are, how they affect quoting, and why an apparent edge is not always tradable immediately after an event.

## What State Changes Are Tracked

The replay tracks both the event itself and the regime that follows it. In `football_state_changes.csv`, the sample records `kickoff`, `goal_home`, `goal_away`, `equalizer`, `red_card_home`, `lead_change`, and `finish`. The quote rows turn those events into regimes such as `recent_goal`, `recent_red_card`, `suspended`, `stable`, and `finished`.

The distinction is useful. Event labels say what happened; the regime says how the trading layer responds. The sample has 4 kickoffs, 4 finishes, 3 home-goal events, 5 away-goal events, 2 equalizers, 1 home red card, and 1 lead change. The no-trade summary shows the policy that follows: `cooldown_after_goal` appears 16 times, `cooldown_after_red_card` 2 times, `suspended_match_state` 2 times, and `finished_match_state` 8 times.

## Goal And Equalizer Reactions

Goals and equalizers are the clearest reaction-risk case in the replay. They change fair value and trigger a temporary stand-down. At frame `ars-che-20260412-06`, Arsenal vs Chelsea is 1-1 in the 61st minute immediately after a Chelsea goal and equalizer. The draw market has `fair_yes = 0.499962`, `best_ask_yes = 0.48`, and `buy_edge_vs_ask = 0.019962`, so price alone suggests a small buy.

The system still does not quote. The row is tagged with `goal_away` and `equalizer`, the regime is `recent_goal`, uncertainty is `0.04`, and `no_trade_reason` is `cooldown_after_goal`. Liverpool vs Tottenham at frame `liv-tot-20260412-05` shows the same choice: after a `goal_home` and `lead_change` at minute 52, `away_or_draw` still has `buy_edge_vs_ask = 0.025075`, but the row is `no_trade` inside the post-goal cooldown.

Immediately after a goal or equalizer, visible prices can move sharply while information is still being digested. The repo treats that period as reaction-risk, not as a free edge.

## Red Cards And Suspensions

Red cards and suspensions use the same restraint. At frame `int-juv-20260413-04`, Inter vs Juventus reaches minute 27 with a home red card. The event log records `red_card_home`, the quote row moves into `recent_red_card`, uncertainty rises to `0.05`, and both markets are `no_trade` with `cooldown_after_red_card`. For `int-juv-away-win`, fair value is `0.379993` and the market sits around `0.38`, but the engine still stands down rather than quoting into the immediate aftermath of the card.

Suspensions are stricter. At frame `rm-bar-20260414-06`, Real Madrid vs Barcelona is suspended at minute 58 with the score level at 1-1. The quote rows move to `suspended`, uncertainty jumps to `0.1`, and `no_trade_reason` becomes `suspended_match_state`. The draw and `either_team_wins` markets are both blocked even though the books are present. The issue is not only price; it is whether the trading state is reliable enough to act on.

## Why Apparent Edge Is Not Always Actionable

The replay makes the core point clearly: edge and action are not the same thing. The Arsenal-Chelsea draw row at frame `ars-che-20260412-06` combines all three ingredients. The market shows a positive buy edge, the fair-to-mid relationship is supportive, and yet the decision is still `no_trade`. The pricing layer did not fail; the reaction layer recognized the equalizer as a state shock.

Other rows show the same logic for different causes. Liverpool-Tottenham `away_or_draw` at frame `liv-tot-20260412-05` has `max_actionable_edge = 0.025075` but is blocked by `cooldown_after_goal`. Inter-Juventus `away_win` at frame `int-juv-20260413-05` has `max_actionable_edge = 0.014998` but is blocked by `insufficient_bookmaker_sources` because only one bookmaker is present. Tradability cannot be reduced to one fair-minus-price number.

## Why It Matters

Football markets are stateful, not just numerical. The replay tracks match-state shocks, reacts with explicit cooldowns or hard no-trade states, and records the decision for later analysis. Around goals, cards, suspensions, and other regime breaks, reaction-time discipline matters as much as pricing accuracy.

In practical terms, the workflow keeps four habits visible: match-state awareness, reaction-time discipline, restraint under unstable information, and no forced action just because a displayed edge exists. Any later live extension would need to preserve those habits.

## Limits

This is an offline-only football workflow. Replay does not model queue position or realistic fills. The bundled inputs and sample packs are useful for following the mechanics, not for production validation or evidence of persistent alpha.
