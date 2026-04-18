"""Prompt builder for final recommendation."""

from __future__ import annotations

from foresight_x.schemas import EvidenceBundle, MemoryBundle, Option, OptionEvaluation


def recommender_prompt(
    chosen_option: Option,
    evaluations: list[OptionEvaluation],
    options: list[Option],
    evidence: EvidenceBundle,
    memory: MemoryBundle,
    composite_by_option_id: dict[str, float],
) -> str:
    return (
        "You are the Recommender of Foresight-X.\n"
        "Objective: justify the chosen option and list concrete next actions.\n"
        "Constraints:\n"
        "- reasoning must reference memory patterns, evidence, and simulation scores at a high level.\n"
        "- next_actions must be specific (drafts, meetings, checklists) with optional deadlines.\n"
        "- reassessment_triggers are observable events that should prompt a re-run.\n"
        "- Do not invent facts outside EvidenceBundle.\n\n"
        f"Chosen option (pre-selected by composite score): {chosen_option.model_dump_json()}\n"
        f"Composite scores by option_id: {composite_by_option_id}\n"
        f"All OptionEvaluation: {[e.model_dump() for e in evaluations]}\n"
        f"Options: {[o.model_dump() for o in options]}\n"
        f"MemoryBundle: {memory.model_dump_json()}\n"
        f"EvidenceBundle: {evidence.model_dump_json()}\n"
    )
