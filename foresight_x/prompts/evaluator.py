"""Prompt builder for option evaluation from simulated futures."""

from __future__ import annotations

from foresight_x.schemas import SimulatedFuture, UserState


def evaluator_prompt(
    future: SimulatedFuture,
    user_state: UserState,
) -> str:
    return (
        "You are the Evaluator of Foresight-X.\n"
        "Objective: score this option using the scenario bundle and user goals.\n"
        "Dimensions (0-10 each):\n"
        "- expected_value_score: weighted upside vs baseline.\n"
        "- risk_score: higher = riskier (tail + variance).\n"
        "- regret_score: higher = more regret if this choice is wrong.\n"
        "- uncertainty_score: higher = less confidence in the forecast.\n"
        "- goal_alignment_score: match to stated goals.\n"
        "- rationale: one short paragraph citing scenario labels.\n\n"
        f"UserState: {user_state.model_dump_json()}\n"
        f"SimulatedFuture: {future.model_dump_json()}\n"
    )
