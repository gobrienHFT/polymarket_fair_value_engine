"""Deterministic fair-value-to-execution research utilities."""

from polymarket_fair_value_engine.execution_research.config import load_execution_research_config
from polymarket_fair_value_engine.execution_research.engine import run_execution_research

__all__ = ["load_execution_research_config", "run_execution_research"]
