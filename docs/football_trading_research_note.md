# Football Trading Research Note

## Scope

This note summarizes the repo's offline football pricing, replay, and strategy-sweep workflow using only the committed reference packs under `docs/sample_outputs/`. The workflow is generated from bundled sample inputs and is intended for inspection of pricing, restraint, and evaluation mechanics rather than any claim of live football execution or production validation.

For a one-page summary from the same committed packs, see [docs/football_research_dashboard.md](football_research_dashboard.md).
For concrete market-by-market examples from the same committed packs, see [docs/football_decision_casebook.md](football_decision_casebook.md).
For post-trade replay evaluation and calibration commentary, see [docs/football_post_trade_analysis_note.md](football_post_trade_analysis_note.md).
For match-state shock and reaction-risk commentary, see [docs/football_match_state_reaction_note.md](football_match_state_reaction_note.md).

## Fair Value Construction

The starting point is bookmaker 1X2 odds for each fixture. The engine converts decimal odds into implied probabilities, measures the bookmaker overround, and removes that overround with proportional normalization. That produces a de-vigged triplet for home, draw, and away outcomes. Multiple bookmaker snapshots are then averaged into a simple consensus fair view rather than treated as separate models.

That 1X2 consensus is mapped into Polymarket-style binary YES probabilities for supported football markets such as `home_win`, `away_win`, `draw`, `home_or_draw`, `away_or_draw`, and `either_team_wins`. The snapshot reference pack shows the resulting fair YES and fair NO levels alongside market midpoint, best bid, and best ask. From there the engine computes directional trading fields: `buy_edge_vs_ask = fair_yes - best_ask_yes`, `sell_edge_vs_bid = best_bid_yes - fair_yes`, and `edge_vs_mid = fair_yes - market_mid_yes`. On the committed snapshot sample, that process prices 12 markets across 4 fixtures and flags 5 markets with positive actionable edge. The point is not to claim signal strength from a tiny sample; it is to show a transparent path from bookmaker prices to binary fair value and then to tradable comparisons versus the displayed market.

## No-Trade Discipline

The football workflow is deliberately explicit about when not to quote. The replay reference shows that a market can be rejected because the YES book is missing, the YES spread is too wide, fair value sits inside the spread, bookmaker coverage is too thin, or source data is stale. It also applies state-aware restraint: goals and red cards trigger temporary cooldowns, while suspended and finished states are treated as no-trade conditions outright.

That matters because the football path is not trying to present every apparent edge as actionable. It is using fair value as one input inside a gating layer that reacts to book quality and state instability. In the committed replay report, the largest no-trade buckets are `cooldown_after_goal`, `fair_inside_spread`, and `finished_match_state`, which is consistent with a conservative research harness that prefers to miss trades rather than force action through unstable states.

## Replay Evaluation

The replay artifacts answer a narrower question than live trading: given a fixed stream of bundled football snapshots, did the quote decision look useful on the next few observations and at final settlement? The quote file records fair value, market book context, uncertainty, candidate action, and no-trade reason at each priced frame. The markout file then measures what happened next with both raw market movement and direction-correct metrics such as `directional_next_capture` and `directional_2step_capture`. The calibration file buckets those observations by edge size, market type, and phase. Separate files record detected state changes and aggregate no-trade counts.

On the committed replay sample, the baseline configuration covers 4 fixtures and 32 time snapshots, yielding 64 priced market snapshots and 17 quoteable snapshots. Its average directional next capture is `0.05625` with a positive capture rate of `0.6875`. Those figures are illustrative only, but they demonstrate the evaluation loop: fair value produces a candidate action, explicit gating reduces the set of quoteable states, and post-decision outputs make it possible to inspect whether the action direction aligned with subsequent market movement.

## Strategy Comparison

The strategy sweep holds the replay data fixed and changes only configuration. In the committed pack it compares four named pricing/no-trade profiles, including `baseline` and `more_aggressive`. The sweep does not claim to discover a production strategy. Its job is to compare how parameter changes alter the balance between selectivity and subsequent directional capture.

Directional capture matters more than raw midpoint drift because the sign should depend on the intended action. A higher midpoint is favorable after a `BUY_YES` decision and unfavorable after a `SELL_YES` decision. The sweep therefore ranks strategies on directional capture metrics rather than on raw market moves alone. In the committed comparison, `more_aggressive` is selected because it clears the minimum quoteable threshold and ranks first on `average_directional_next_capture`, with configured tie-breakers on 2-step capture, hit rate, and adverse move. That makes it the best row within this synthetic comparison setup, not a production winner or proof of alpha.

## What This Demonstrates

This workflow demonstrates a complete trading-research chain that is narrow but inspectable. Fair value is formed from de-vigged bookmaker inputs rather than opaque heuristics. Football 1X2 probabilities are mapped into the binary market forms that an exchange would actually trade. Quote decisions are paired with explicit no-trade rules that react to market quality and state changes. Replay outputs expose both raw movement and action-aware post-trade analysis, and the sweep layer shows how to compare parameter choices under fixed inputs instead of changing data and policy at the same time.

## Limits

Football remains offline-only in this repo. The replay outputs do not model queue position or claim live fill realism. The bundled sample inputs and committed reference packs are for inspection and tooling validation, not for production validation or any broad claim of persistent edge.
