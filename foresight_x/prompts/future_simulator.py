"""Prompt builder for multi-future simulation."""

from __future__ import annotations

from foresight_x.schemas import EvidenceBundle, Option, UserState


def future_simulator_prompt(
    option: Option,
    user_state: UserState,
    evidence: EvidenceBundle,
) -> str:
    return (
        "You are the Future Simulator of Foresight-X.\n"
        "Objective: for the given option, describe best / base / worst plausible futures over a time horizon.\n"
        "Constraints:\n"
        "- Output a SimulatedFuture with exactly three scenarios: labels best, base, worst.\n"
        "- Probabilities must sum to 1.0 (+/- 0.05).\n"
        "- Ground narratives in EvidenceBundle facts where possible; do not invent external facts.\n"
        "- time_horizon should be concrete (e.g. '3 months', '6 months').\n"
        "- key_drivers must be short phrases.\n\n"
        f"Option: {option.model_dump_json()}\n"
        f"UserState: {user_state.model_dump_json()}\n"
        f"EvidenceBundle: {evidence.model_dump_json()}\n"
    )
