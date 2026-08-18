# Football Trading Research Note

## Scope

This note follows the offline football workflow from bookmaker prices through fair value, replay, and strategy comparison. Everything comes from the bundled sample inputs and the reference packs under `docs/sample_outputs/`. The aim is to make the pricing and trading decisions easy to follow; live football execution is not part of the path.

For a one-page summary from the same packs, see [docs/football_research_dashboard.md](football_research_dashboard.md).
For concrete market-by-market examples from the same packs, see [docs/football_decision_casebook.md](football_decision_casebook.md).
For post-trade replay evaluation and calibration commentary, see [docs/football_post_trade_analysis_note.md](football_post_trade_analysis_note.md).
For match-state shock and reaction-risk commentary, see [docs/football_match_state_reaction_note.md](football_match_state_reaction_note.md).

## Fair Value Construction

I start with bookmaker 1X2 odds for each fixture. The engine converts decimal odds into implied probabilities, measures the bookmaker overround, and removes it with proportional normalization. That leaves a de-vigged triplet for home, draw, and away. Multiple bookmaker snapshots are then averaged into a simple consensus fair view rather than treated as separate models.

That 1X2 consensus is mapped into Polymarket-style binary YES probabilities for markets such as `home_win`, `away_win`, `draw`, `home_or_draw`, `away_or_draw`, and `either_team_wins`. The snapshot reference shows fair YES and fair NO beside the market midpoint, best bid, and best ask. The engine then computes `buy_edge_vs_ask = fair_yes - best_ask_yes`, `sell_edge_vs_bid = best_bid_yes - fair_yes`, and `edge_vs_mid = fair_yes - market_mid_yes`. On this sample, that gives 12 priced markets across 4 fixtures and 5 with positive actionable edge. The sample is small; its value is the transparent path from bookmaker prices to a binary trading comparison.

## No-Trade Discipline

The football workflow spells out when not to quote. A market can be rejected because the YES book is missing, the YES spread is too wide, fair value sits inside the spread, bookmaker coverage is too thin, or source data is stale. Goals and red cards add temporary cooldowns; suspended and finished states are no-trade conditions outright.

That matters because a fair-value discrepancy is not automatically a trade. Fair value sits inside a gating layer that reacts to book quality and match-state instability. In the replay report, the largest no-trade buckets are `cooldown_after_goal`, `fair_inside_spread`, and `finished_match_state`: the system would rather miss a quote than force one through an unstable state.

## Replay Evaluation

The replay asks a narrower question than live trading: given a fixed stream of football snapshots, did the quote decision line up with the next few observations and with final settlement? The quote file records fair value, market context, uncertainty, candidate action, and no-trade reason at each priced frame. The markout file measures what happened next in raw terms and with direction-correct metrics such as `directional_next_capture` and `directional_2step_capture`. Calibration buckets those observations by edge size, market type, and phase, while separate files record state changes and no-trade counts.

On the replay sample, the baseline configuration covers 4 fixtures and 32 time snapshots, yielding 64 priced market snapshots and 17 quoteable snapshots. Its average directional next capture is `0.05625` with a positive capture rate of `0.6875`. Those figures are illustrative only. The useful part is the loop: fair value produces a candidate action, gating removes states that should not be quoted, and post-decision outputs show whether the chosen direction aligned with later market movement.

## Strategy Comparison

The strategy sweep holds the replay data fixed and changes only configuration. It compares four named pricing/no-trade profiles, including `baseline` and `more_aggressive`. It is a way to see how parameter changes move the balance between selectivity and subsequent directional capture, not a way to discover a production strategy.

Directional capture matters more than raw midpoint drift because the sign should depend on the intended action. A higher midpoint is favorable after a `BUY_YES` decision and unfavorable after a `SELL_YES` decision. The sweep therefore ranks strategies on directional capture metrics rather than raw market moves alone. In the comparison, `more_aggressive` clears the minimum quoteable threshold and ranks first on `average_directional_next_capture`, with configured tie-breakers on 2-step capture, hit rate, and adverse move. It is the best row in this synthetic comparison, not a production winner or proof of alpha.

## Why It Matters

The chain is complete even though it is narrow. Fair value comes from de-vigged bookmaker inputs. Those 1X2 probabilities are mapped into binary market forms an exchange could display. Quote decisions carry explicit no-trade rules for book quality and state changes. Replay then separates raw movement from action-aware post-trade analysis, while the sweep compares policy choices without changing the data at the same time.

## Limits

Football remains offline-only. Replay does not model queue position or live fill realism. The bundled inputs and reference packs are useful for following the mechanics, not for production validation or a claim of persistent edge.
