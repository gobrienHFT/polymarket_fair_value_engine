# Football Replay Walkthrough

This walkthrough is for the offline football replay path only.

It does not describe live football trading, because live football trading is not implemented in this repo.

For zero-click inspection on GitHub, start with [docs/sample_outputs/football_replay_reference/README.md](sample_outputs/football_replay_reference/README.md). That committed pack is generated from the bundled replay sample.

## Run It

```bash
python -m pip install -e .[dev]
pmfe football-replay --sample --config configs/football_strategy_baseline.json --run-id verify-football-replay
pmfe report --run-id verify-football-replay
```

Artifacts are written under `runs/<run_id>/`.

## 1. Input Replay Frame Structure

The bundled sample lives in `data/sample_football_replay.jsonl`.

Each replay frame contains:

- `timestamp_utc`
- fixture metadata
- match state
- bookmaker 1X2 odds snapshots
- one or more Polymarket-style binary YES books

The match state is explicit:

- `status`: `pregame`, `inplay`, `finished`, or `suspended`
- `minute` and `added_time`
- `home_goals` / `away_goals`
- `home_red_cards` / `away_red_cards`

The replay sample is synthetic but deterministic. Some frames intentionally skip intermediate microstates so state changes can be observed between snapshots.

## 2. Bookmaker De-Vigging

For each bookmaker 1X2 snapshot:

1. convert decimal odds into implied probabilities
2. measure the overround
3. remove the overround with proportional normalization

That produces a fairer 1X2 probability triplet:

- `P(home)`
- `P(draw)`
- `P(away)`

## 3. 1X2 To Binary Market Mapping

The football snapshot/replay path supports these binary market mappings:

- `home_win`
- `away_win`
- `draw`
- `home_or_draw`
- `away_or_draw`
- `either_team_wins`

Examples:

- `home_win` -> `P(home)`
- `home_or_draw` -> `P(home) + P(draw)`
- `either_team_wins` -> `1 - P(draw)`

This keeps football fair value formation honest and explicit: the repo is not pretending to have a deeper in-play football model yet.

## 4. Uncertainty And No-Trade Logic

The replay path computes an uncertainty score from:

- average bookmaker overround
- bookmaker disagreement
- YES-book spread
- state-change boosts after goals/red cards
- a suspended-state boost

The replay path also applies explicit no-trade rules, including:

- `missing_yes_book`
- `wide_yes_spread`
- `fair_inside_spread`
- `high_uncertainty`
- `insufficient_bookmaker_sources`
- `stale_source_data`
- `cooldown_after_goal`
- `cooldown_after_red_card`
- `suspended_match_state`
- `finished_match_state`

## 5. State-Change Handling

Between replay frames the engine detects:

- kickoff
- home goal
- away goal
- equalizer
- lead change
- home red card
- away red card
- finish

Detected changes do two things:

- they are written to `football_state_changes.csv`
- they feed uncertainty boosts and temporary quote cooldown rules

## 6. Quote Decision Fields

For each binary market snapshot the replay computes:

- `fair_yes`
- `fair_no`
- `market_mid_yes`
- `best_bid_yes`
- `best_ask_yes`
- `buy_edge_vs_ask = fair_yes - best_ask_yes`
- `sell_edge_vs_bid = best_bid_yes - fair_yes`
- `edge_vs_mid = fair_yes - market_mid_yes`
- `max_actionable_edge = max(buy_edge_vs_ask, sell_edge_vs_bid, 0.0)`

That makes the direction of the edge explicit:

- positive `buy_edge_vs_ask` means the ask looks cheap versus fair value
- positive `sell_edge_vs_bid` means the bid looks rich versus fair value

## 7. Markout Definitions

The replay writes `football_markouts.csv` with explicit definitions:

- `next_snapshot_mid_yes`: midpoint at the next replay frame
- `raw_next_mid_change`: next midpoint minus current midpoint
- `directional_next_capture`: next midpoint move expressed in the chosen decision direction
- `raw_2step_mid_change`: midpoint change two frames forward versus the current midpoint
- `directional_2step_capture`: two-step midpoint move expressed in the chosen decision direction
- `max_favorable_move`: best later midpoint move in the chosen direction
- `max_adverse_move`: worst later midpoint move in the chosen direction
- `eventual_settlement_yes`: final binary settlement when the sample has a final result
- `raw_eventual_resolution_change`: final settlement minus current midpoint
- `directional_eventual_capture`: final settlement move expressed in the chosen decision direction

Legacy fields such as `next_snapshot_markout` are still present for backward compatibility, but the newer raw/directional split is the clearer way to explain the output.

These are simple, inspectable evaluation outputs rather than claims of statistical significance.

## 8. Calibration Outputs

The replay also writes `football_calibration.csv` with small aggregated summaries such as:

- average next-snapshot markout by edge bucket
- average 2-step markout by edge bucket
- average markout by market type
- average markout by pregame vs in-play
- sign hit-rate by bucket

`football_no_trade_reasons.csv` summarizes why frames were skipped.

`football_report.md` pulls the main pieces together into a short human-readable report.

## 9. Limitations

- the replay sample is small and synthetic
- fair value still comes from bookmaker snapshots, not an independent in-play football model
- there is no live football market discovery, live football execution, or live football order management here
- markouts are useful for repo review and inspection, but not strong enough to support broad claims

## 10. How This Could Extend Later

An honest next extension path would be:

1. record richer live football replay data with timestamped bookmaker and exchange snapshots
2. add explicit event-state ingestion and latency handling
3. improve no-trade logic around suspensions, cards, goals, and stale market books
4. plug the pricing layer into a guarded football order/execution adapter
5. evaluate the live path with the same markout and calibration outputs before claiming anything broader
