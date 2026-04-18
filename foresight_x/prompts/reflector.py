"""Prompt builder for post-hoc reflection on a full decision trace."""

from __future__ import annotations

from foresight_x.schemas import DecisionTrace


def reflector_prompt(trace: DecisionTrace) -> str:
    return (
        "You are the Reflector of Foresight-X.\n"
        "Objective: critique this decision trace and surface failure modes for the Harness.\n"
        "Output a Reflection with:\n"
        "- possible_errors: where the reasoning may be wrong.\n"
        "- uncertainty_sources: what drove score uncertainty.\n"
        "- model_limitations: what the model cannot know.\n"
        "- information_gaps: missing data the user should seek.\n"
        "- self_improvement_signal: one sentence for memory/prompt tuning.\n\n"
        f"DecisionTrace: {trace.model_dump_json()}\n"
    )
