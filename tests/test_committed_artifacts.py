from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.verify_committed_artifacts import collect_artifact_issues


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "verify_committed_artifacts.py"
README = REPO_ROOT / "README.md"
FOOTBALL_CASEBOOK = REPO_ROOT / "docs" / "football_decision_casebook.md"
FOOTBALL_MATCH_STATE_REACTION_NOTE = REPO_ROOT / "docs" / "football_match_state_reaction_note.md"
FOOTBALL_POST_TRADE_ANALYSIS_NOTE = REPO_ROOT / "docs" / "football_post_trade_analysis_note.md"
FOOTBALL_STRATEGY_CONFIGURATION_NOTE = REPO_ROOT / "docs" / "football_strategy_configuration_note.md"
FOOTBALL_RESEARCH_NOTE = REPO_ROOT / "docs" / "football_trading_research_note.md"
SAMPLE_OUTPUTS_INDEX = REPO_ROOT / "docs" / "sample_outputs" / "README.md"
FOOTBALL_REPLAY_WALKTHROUGH = REPO_ROOT / "docs" / "football_replay_walkthrough.md"
FOOTBALL_SWEEP_WALKTHROUGH = REPO_ROOT / "docs" / "football_strategy_sweep_walkthrough.md"


def test_committed_artifacts_have_no_integrity_issues() -> None:
    issues = collect_artifact_issues()
    assert not issues, "\n".join(f"- {issue}" for issue in issues)


def test_verify_committed_artifacts_script_runs_cleanly() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "Committed artifact verification passed." in result.stdout


def test_readme_links_sample_output_index_and_packs() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "## Fastest Demo" not in readme
    assert readme.index("## Football Research Path") < readme.index("## Football Reviewer Path")
    assert readme.index("## Football Reviewer Path") < readme.index("## Football Research Notes")
    assert readme.index("## Football Research Notes") < readme.index("## Regeneration Commands")
    assert readme.index("## Regeneration Commands") < readme.index("## BTC Execution Sandbox")
    assert "| At a glance | Committed value |" in readme
    assert readme.index("## BTC Execution Sandbox") < readme.index("pmfe demo")
    assert readme.index("## Football Reviewer Path") < readme.index("python scripts/refresh_sample_outputs.py")
    assert "docs/football_decision_casebook.md" in readme
    assert "docs/football_match_state_reaction_note.md" in readme
    assert "docs/football_post_trade_analysis_note.md" in readme
    assert "docs/football_strategy_configuration_note.md" in readme
    assert "docs/football_trading_research_note.md" in readme
    assert "docs/sample_outputs/README.md" in readme
    assert "docs/sample_outputs/football_demo_reference/README.md" in readme
    assert "docs/sample_outputs/football_replay_reference/README.md" in readme
    assert "docs/sample_outputs/football_sweep_reference/README.md" in readme
    assert "runs/review-football" not in readme


def test_sample_output_index_links_all_football_reference_packs() -> None:
    index = SAMPLE_OUTPUTS_INDEX.read_text(encoding="utf-8")

    assert "../football_decision_casebook.md" in index
    assert "../football_match_state_reaction_note.md" in index
    assert "../football_post_trade_analysis_note.md" in index
    assert "../football_strategy_configuration_note.md" in index
    assert "../football_trading_research_note.md" in index
    assert "## Football Snapshot Reference" in index
    assert "## Football Replay Reference" in index
    assert "## Football Strategy Sweep Reference" in index
    assert "football_demo_reference/README.md" in index
    assert "football_replay_reference/README.md" in index
    assert "football_sweep_reference/README.md" in index


def test_walkthrough_docs_link_replay_and_sweep_reference_packs() -> None:
    replay_doc = FOOTBALL_REPLAY_WALKTHROUGH.read_text(encoding="utf-8")
    sweep_doc = FOOTBALL_SWEEP_WALKTHROUGH.read_text(encoding="utf-8")

    assert "docs/football_trading_research_note.md" in replay_doc
    assert "docs/football_trading_research_note.md" in sweep_doc
    assert "docs/football_strategy_configuration_note.md" in sweep_doc
    assert "docs/sample_outputs/football_replay_reference/README.md" in replay_doc
    assert "docs/sample_outputs/football_sweep_reference/README.md" in sweep_doc


def test_research_note_exists() -> None:
    assert FOOTBALL_RESEARCH_NOTE.exists()


def test_decision_casebook_exists() -> None:
    assert FOOTBALL_CASEBOOK.exists()


def test_match_state_reaction_note_exists() -> None:
    assert FOOTBALL_MATCH_STATE_REACTION_NOTE.exists()


def test_post_trade_analysis_note_exists() -> None:
    assert FOOTBALL_POST_TRADE_ANALYSIS_NOTE.exists()


def test_strategy_configuration_note_exists() -> None:
    assert FOOTBALL_STRATEGY_CONFIGURATION_NOTE.exists()
