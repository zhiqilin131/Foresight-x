"""Prompt builder for option generation."""

from __future__ import annotations

from foresight_x.schemas import EvidenceBundle, MemoryBundle, UserState


def option_generator_prompt(
    user_state: UserState,
    memory: MemoryBundle,
    evidence: EvidenceBundle,
) -> str:
    return (
        "You are the Option Generator of Foresight-X.\n"
        "Objective: propose 2-4 distinct options for the user's decision.\n"
        "Constraints:\n"
        "- At least one option should expand beyond explicit user wording.\n"
        "- Options must be mutually distinct, not paraphrases.\n"
        "- cost_of_reversal must be one of {low, medium, high}.\n"
        "- Keep options actionable, concise, and realistic.\n\n"
        f"UserState: {user_state.model_dump_json()}\n"
        f"MemoryBundle: {memory.model_dump_json()}\n"
        f"EvidenceBundle: {evidence.model_dump_json()}\n"
    )
