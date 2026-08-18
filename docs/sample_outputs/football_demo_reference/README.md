# Football Snapshot Reference

- Generated from bundled input: `data/sample_football_markets.json`
- Refresh command: `python scripts/refresh_sample_outputs.py`
- Source command:

```bash
pmfe football-demo --input data/sample_football_markets.json --run-id football-demo-reference
```

## Files

- `summary.json`
- `football_fair_values.csv`
- `football_edges.csv`

This is an offline football pricing run generated from the bundled sample input. It stops at fair value and market comparison; live football execution is not implemented.
