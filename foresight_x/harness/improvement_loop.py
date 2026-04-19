"""Minimal self-improvement loop: write outcomes back into memory."""

from __future__ import annotations

from pathlib import Path

from foresight_x.config import Settings, load_settings
from foresight_x.harness.trace import load_decision_trace
from foresight_x.memory.profile_store import load_profile as load_tier3_profile
from foresight_x.memory.profile_summarizer import summarize_profile
from foresight_x.orchestration.llm_factory import build_openai_llm
from foresight_x.retrieval.memory import UserMemory
from foresight_x.schemas import DecisionOutcome, DecisionTrace


def _maybe_refresh_tier3_profile(
    memory: UserMemory,
    settings: Settings,
) -> None:
    """After a new indexed decision, optionally refresh Tier 3 profile (same thresholds as former pipeline hook)."""
    try:
        n = int(getattr(settings, "tier3_auto_update_every", 5) or 0)
        min_n = int(getattr(settings, "tier3_min_decisions", 3) or 3)
        if n <= 0 or not (settings.openai_api_key or "").strip():
            return
        if not hasattr(memory, "list_all_past_decisions"):
            return
        past = memory.list_all_past_decisions()
        if len(past) < min_n:
            return
        prior = load_tier3_profile(settings.foresight_user_id)
        summarized_before = int(prior.n_decisions_summarized) if prior else 0
        if len(past) - summarized_before < n:
            return
        llm = build_openai_llm(settings)
        summarize_profile(settings.foresight_user_id, past, llm=llm)
    except Exception:
        # Never fail outcome recording because profile refresh failed.
        pass


def apply_outcome_to_memory(
    decision_id: str,
    outcome: DecisionOutcome,
    *,
    settings: Settings | None = None,
    user_memory: UserMemory | None = None,
    traces_dir: Path | None = None,
) -> DecisionTrace:
    """Load the trace and index it with the provided outcome (primary vector-memory write path)."""
    s = settings or load_settings()
    trace = load_decision_trace(decision_id, settings=s, traces_dir=traces_dir)
    memory = user_memory or UserMemory(s.foresight_user_id, settings=s)
    memory.remove_by_decision_id(decision_id)
    memory.add_decision(trace, outcome=outcome)
    _maybe_refresh_tier3_profile(memory, s)
    return trace
