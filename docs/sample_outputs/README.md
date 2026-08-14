# Sample Outputs

Committed football reference packs are generated from the bundled sample inputs so the offline football path can be inspected on GitHub without writing new `runs/<run_id>/` directories.

The execution reference pack is generated separately from the bundled binary CLOB replay and records the fair-value-to-execution assumptions and outcomes described in the execution research path.

- Refresh command: `python scripts/refresh_sample_outputs.py`
- Dashboard: [docs/football_research_dashboard.md](../football_research_dashboard.md)
- Companion note: [docs/football_trading_research_note.md](../football_trading_research_note.md)
- Decision casebook: [docs/football_decision_casebook.md](../football_decision_casebook.md)
- Strategy config note: [docs/football_strategy_configuration_note.md](../football_strategy_configuration_note.md)
- Post-trade analysis note: [docs/football_post_trade_analysis_note.md](../football_post_trade_analysis_note.md)
- Match-state reaction note: [docs/football_match_state_reaction_note.md](../football_match_state_reaction_note.md)
- Execution casebook: [docs/execution_casebook.md](../execution_casebook.md)
- Execution research packet: [docs/execution_research_packet.md](../execution_research_packet.md)

## Football Snapshot Reference

- Pack: [docs/sample_outputs/football_demo_reference/README.md](football_demo_reference/README.md)
- Summary: [docs/sample_outputs/football_demo_reference/summary.json](football_demo_reference/summary.json)
- Key outputs: [football_fair_values.csv](football_demo_reference/football_fair_values.csv), [football_edges.csv](football_demo_reference/football_edges.csv)

## Football Replay Reference

- Pack: [docs/sample_outputs/football_replay_reference/README.md](football_replay_reference/README.md)
- Summary: [docs/sample_outputs/football_replay_reference/summary.json](football_replay_reference/summary.json)
- Key outputs: [football_replay_quotes.csv](football_replay_reference/football_replay_quotes.csv), [football_markouts.csv](football_replay_reference/football_markouts.csv), [football_report.md](football_replay_reference/football_report.md)

## Football Strategy Sweep Reference

- Pack: [docs/sample_outputs/football_sweep_reference/README.md](football_sweep_reference/README.md)
- Summary: [docs/sample_outputs/football_sweep_reference/summary.json](football_sweep_reference/summary.json)
- Key outputs: [football_strategy_results.csv](football_sweep_reference/football_strategy_results.csv), [football_strategy_slices.csv](football_sweep_reference/football_strategy_slices.csv), [football_strategy_report.md](football_sweep_reference/football_strategy_report.md), [football_strategy_best.json](football_sweep_reference/football_strategy_best.json)

## Execution Research Reference

- Pack: [docs/sample_outputs/execution_research_reference/README.md](execution_research_reference/README.md)
- Summary: [docs/sample_outputs/execution_research_reference/summary.json](execution_research_reference/summary.json)
- Start with: [execution_report.md](execution_research_reference/execution_report.md), [execution_casebook.md](execution_research_reference/execution_casebook.md), [execution_attribution.csv](execution_research_reference/execution_attribution.csv), [execution_markout_slices.csv](execution_research_reference/execution_markout_slices.csv), and [execution_lifecycle_events.csv](execution_research_reference/execution_lifecycle_events.csv)
- Refresh command: `python scripts/refresh_execution_research.py`
