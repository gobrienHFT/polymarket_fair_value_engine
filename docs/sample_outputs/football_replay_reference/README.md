# Football Replay Reference

- Generated from bundled input: `data/sample_football_replay.jsonl`
- Pricing config: `configs/football_strategy_baseline.json`
- Refresh command: `python scripts/refresh_sample_outputs.py`
- Source command:

```bash
pmfe football-replay --sample --config configs/football_strategy_baseline.json --run-id football-replay-reference
```

## Files

- `summary.json`
- `football_replay_quotes.csv`
- `football_markouts.csv`
- `football_calibration.csv`
- `football_state_changes.csv`
- `football_no_trade_reasons.csv`
- `football_report.md`

This pack is an offline replay/evaluation reference generated from bundled sample data. It does not imply live football trading.
