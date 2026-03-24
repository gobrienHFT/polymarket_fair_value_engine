from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
FOOTBALL_CASEBOOK = REPO_ROOT / "docs" / "football_decision_casebook.md"
FOOTBALL_RESEARCH_DASHBOARD = REPO_ROOT / "docs" / "football_research_dashboard.md"
FOOTBALL_MATCH_STATE_REACTION_NOTE = REPO_ROOT / "docs" / "football_match_state_reaction_note.md"
FOOTBALL_POST_TRADE_ANALYSIS_NOTE = REPO_ROOT / "docs" / "football_post_trade_analysis_note.md"
FOOTBALL_STRATEGY_CONFIGURATION_NOTE = REPO_ROOT / "docs" / "football_strategy_configuration_note.md"
FOOTBALL_RESEARCH_NOTE = REPO_ROOT / "docs" / "football_trading_research_note.md"
SAMPLE_OUTPUTS_ROOT = REPO_ROOT / "docs" / "sample_outputs"
SAMPLE_OUTPUTS_INDEX = SAMPLE_OUTPUTS_ROOT / "README.md"
FOOTBALL_REPLAY_WALKTHROUGH = REPO_ROOT / "docs" / "football_replay_walkthrough.md"
FOOTBALL_SWEEP_WALKTHROUGH = REPO_ROOT / "docs" / "football_strategy_sweep_walkthrough.md"

PACKS = {
    "football_demo_reference": {
        "dir": SAMPLE_OUTPUTS_ROOT / "football_demo_reference",
        "required_files": (
            "README.md",
            "summary.json",
            "football_fair_values.csv",
            "football_edges.csv",
        ),
    },
    "football_replay_reference": {
        "dir": SAMPLE_OUTPUTS_ROOT / "football_replay_reference",
        "required_files": (
            "README.md",
            "summary.json",
            "football_replay_quotes.csv",
            "football_markouts.csv",
            "football_calibration.csv",
            "football_state_changes.csv",
            "football_no_trade_reasons.csv",
            "football_report.md",
        ),
    },
    "football_sweep_reference": {
        "dir": SAMPLE_OUTPUTS_ROOT / "football_sweep_reference",
        "required_files": (
            "README.md",
            "summary.json",
            "football_strategy_results.csv",
            "football_strategy_slices.csv",
            "football_strategy_report.md",
            "football_strategy_best.json",
            "best_strategy/summary.json",
            "best_strategy/football_replay_quotes.csv",
            "best_strategy/football_markouts.csv",
            "best_strategy/football_calibration.csv",
            "best_strategy/football_state_changes.csv",
            "best_strategy/football_no_trade_reasons.csv",
            "best_strategy/football_report.md",
        ),
    },
}

MARKDOWN_LINK_PATTERN = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
TEMP_PATH_MARKERS = ("AppData", "\\Temp\\", "/tmp/", "C:\\Users\\", "C:/Users/")
SUMMARY_PATH_MARKERS = TEMP_PATH_MARKERS + ("runs\\", "runs/")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _repo_relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def _iter_repo_relative_links(path: Path) -> list[str]:
    links: list[str] = []
    for link in MARKDOWN_LINK_PATTERN.findall(_read_text(path)):
        if "://" in link or link.startswith("#"):
            continue
        links.append(link)
    return links


def _resolve_repo_relative_link(path: Path, link: str) -> Path:
    return (path.parent / link.split("#", 1)[0]).resolve()


def _verify_markdown_links() -> list[str]:
    issues: list[str] = []
    audit_files = [
        README,
        FOOTBALL_CASEBOOK,
        FOOTBALL_RESEARCH_DASHBOARD,
        FOOTBALL_MATCH_STATE_REACTION_NOTE,
        FOOTBALL_POST_TRADE_ANALYSIS_NOTE,
        FOOTBALL_STRATEGY_CONFIGURATION_NOTE,
        FOOTBALL_RESEARCH_NOTE,
        SAMPLE_OUTPUTS_INDEX,
        FOOTBALL_REPLAY_WALKTHROUGH,
        FOOTBALL_SWEEP_WALKTHROUGH,
        *(pack["dir"] / "README.md" for pack in PACKS.values()),
    ]
    for path in audit_files:
        if not path.exists():
            issues.append(f"Missing markdown file for audit: {_repo_relative(path)}")
            continue
        for link in _iter_repo_relative_links(path):
            target = _resolve_repo_relative_link(path, link)
            if not target.exists():
                issues.append(f"Broken markdown link in {_repo_relative(path)}: {link}")
    return issues


def _verify_pack_files() -> list[str]:
    issues: list[str] = []
    for pack_name, pack in PACKS.items():
        pack_dir = pack["dir"]
        if not pack_dir.exists():
            issues.append(f"Missing sample-output pack directory: {_repo_relative(pack_dir)}")
            continue
        for relative_path in pack["required_files"]:
            if not (pack_dir / relative_path).exists():
                issues.append(f"Missing committed sample-output file: {_repo_relative(pack_dir / relative_path)}")
    return issues


def _verify_front_door_links() -> list[str]:
    issues: list[str] = []
    readme = _read_text(README)
    football_research_index = readme.find("## Football Research Path")
    football_reviewer_index = readme.find("## Football Reviewer Path")
    football_notes_index = readme.find("## Football Research Notes")
    football_regeneration_index = readme.find("## Regeneration Commands")
    btc_index = readme.find("## BTC Execution Sandbox")
    if "## Fastest Demo" in readme:
        issues.append("README.md still contains the old Fastest Demo heading")
    if min(football_research_index, football_reviewer_index, football_notes_index, football_regeneration_index, btc_index) == -1:
        issues.append("README.md is missing one or more football-first front-door sections")
    elif not (
        football_research_index
        < football_reviewer_index
        < football_notes_index
        < football_regeneration_index
        < btc_index
    ):
        issues.append("README.md front-door sections are not ordered football-first before BTC")
    if "| At a glance | Committed value |" not in readme:
        issues.append("README.md is missing the football at-a-glance summary table")
    demo_index = readme.find("pmfe demo")
    if demo_index != -1 and btc_index != -1 and demo_index < btc_index:
        issues.append("README.md mentions `pmfe demo` before the BTC Execution Sandbox section")
    refresh_index = readme.find("python scripts/refresh_sample_outputs.py")
    if (
        refresh_index != -1
        and football_reviewer_index != -1
        and refresh_index < football_reviewer_index
    ):
        issues.append("README.md still places football regeneration commands before the Football Reviewer Path")

    expected_readme_links = [
        "docs/football_decision_casebook.md",
        "docs/football_research_dashboard.md",
        "docs/football_match_state_reaction_note.md",
        "docs/football_post_trade_analysis_note.md",
        "docs/football_strategy_configuration_note.md",
        "docs/football_trading_research_note.md",
        "docs/sample_outputs/README.md",
        "docs/sample_outputs/football_demo_reference/README.md",
        "docs/sample_outputs/football_replay_reference/README.md",
        "docs/sample_outputs/football_sweep_reference/README.md",
    ]
    for link in expected_readme_links:
        if link not in readme:
            issues.append(f"Missing sample-output link in README.md: {link}")
    if "runs/review-football" in readme:
        issues.append("README.md still routes the primary football reviewer path through runs/review-football-* outputs")

    index = _read_text(SAMPLE_OUTPUTS_INDEX)
    for heading in (
        "## Football Snapshot Reference",
        "## Football Replay Reference",
        "## Football Strategy Sweep Reference",
    ):
        if heading not in index:
            issues.append(f"Missing sample-output index heading: {heading}")
    for link in (
        "../football_decision_casebook.md",
        "../football_research_dashboard.md",
        "../football_match_state_reaction_note.md",
        "../football_post_trade_analysis_note.md",
        "../football_strategy_configuration_note.md",
        "../football_trading_research_note.md",
        "football_demo_reference/README.md",
        "football_replay_reference/README.md",
        "football_sweep_reference/README.md",
    ):
        if link not in index:
            issues.append(f"Missing pack link in docs/sample_outputs/README.md: {link}")

    if not FOOTBALL_CASEBOOK.exists():
        issues.append("Missing docs/football_decision_casebook.md")
    if not FOOTBALL_RESEARCH_DASHBOARD.exists():
        issues.append("Missing docs/football_research_dashboard.md")
    if not FOOTBALL_MATCH_STATE_REACTION_NOTE.exists():
        issues.append("Missing docs/football_match_state_reaction_note.md")
    if not FOOTBALL_POST_TRADE_ANALYSIS_NOTE.exists():
        issues.append("Missing docs/football_post_trade_analysis_note.md")
    if not FOOTBALL_STRATEGY_CONFIGURATION_NOTE.exists():
        issues.append("Missing docs/football_strategy_configuration_note.md")
    if not FOOTBALL_RESEARCH_NOTE.exists():
        issues.append("Missing docs/football_trading_research_note.md")

    replay_doc = _read_text(FOOTBALL_REPLAY_WALKTHROUGH)
    if "docs/sample_outputs/football_replay_reference/README.md" not in replay_doc:
        issues.append("Missing replay reference link in docs/football_replay_walkthrough.md")
    if "docs/football_trading_research_note.md" not in replay_doc:
        issues.append("Missing research note link in docs/football_replay_walkthrough.md")

    sweep_doc = _read_text(FOOTBALL_SWEEP_WALKTHROUGH)
    if "docs/sample_outputs/football_sweep_reference/README.md" not in sweep_doc:
        issues.append("Missing sweep reference link in docs/football_strategy_sweep_walkthrough.md")
    if "docs/football_trading_research_note.md" not in sweep_doc:
        issues.append("Missing research note link in docs/football_strategy_sweep_walkthrough.md")
    if "docs/football_strategy_configuration_note.md" not in sweep_doc:
        issues.append("Missing strategy configuration note link in docs/football_strategy_sweep_walkthrough.md")
    return issues


def _verify_no_temp_paths() -> list[str]:
    issues: list[str] = []
    markdown_files = [
        FOOTBALL_CASEBOOK,
        FOOTBALL_RESEARCH_DASHBOARD,
        FOOTBALL_MATCH_STATE_REACTION_NOTE,
        FOOTBALL_POST_TRADE_ANALYSIS_NOTE,
        FOOTBALL_STRATEGY_CONFIGURATION_NOTE,
        FOOTBALL_RESEARCH_NOTE,
        SAMPLE_OUTPUTS_INDEX,
        *(pack["dir"] / "README.md" for pack in PACKS.values()),
    ]
    for path in markdown_files:
        text = _read_text(path)
        for marker in TEMP_PATH_MARKERS:
            if marker in text:
                issues.append(f"Temporary path marker '{marker}' leaked into {_repo_relative(path)}")

    committed_text_artifacts = [
        path
        for path in SAMPLE_OUTPUTS_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in {".md", ".json", ".csv"}
    ]
    for path in committed_text_artifacts:
        text = _read_text(path)
        for marker in TEMP_PATH_MARKERS:
            if marker in text:
                issues.append(f"Temporary path marker '{marker}' leaked into {_repo_relative(path)}")

    summary_files = [
        pack["dir"] / "summary.json" for pack in PACKS.values()
    ] + [PACKS["football_sweep_reference"]["dir"] / "best_strategy" / "summary.json"]
    for path in summary_files:
        if not path.exists():
            continue
        text = _read_text(path)
        for marker in SUMMARY_PATH_MARKERS:
            if marker in text:
                issues.append(f"Non-committed path marker '{marker}' leaked into {_repo_relative(path)}")
        summary = json.loads(text)
        output_dir = str(summary.get("output_dir", ""))
        if "docs/sample_outputs/" not in output_dir:
            issues.append(f"Committed summary output_dir is not repo-relative in {_repo_relative(path)}")
    return issues


def collect_artifact_issues() -> list[str]:
    issues: list[str] = []
    issues.extend(_verify_pack_files())
    issues.extend(_verify_front_door_links())
    issues.extend(_verify_no_temp_paths())
    issues.extend(_verify_markdown_links())
    return issues


def main() -> int:
    issues = collect_artifact_issues()
    if issues:
        print("Committed artifact verification failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print("Committed artifact verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
