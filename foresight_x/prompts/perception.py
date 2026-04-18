"""Prompt builder for Perception -> UserState extraction."""

from __future__ import annotations


def perception_prompt(raw_input: str) -> str:
    return (
        "You are the Perception module of Foresight-X.\n"
        "Objective: convert the user's free-form decision text into a UserState JSON object.\n"
        "Constraints:\n"
        "- Infer stress_level and workload from language cues if not explicit.\n"
        "- Keep goals concrete and user-centric.\n"
        "- Use one of: time_pressure={low,medium,high}.\n"
        "- Use one of: reversibility={reversible,partial,irreversible}.\n\n"
        "User input:\n"
        f"{raw_input.strip()}\n"
    )
