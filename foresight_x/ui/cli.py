"""Command-line interface for running Foresight-X and recording outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from foresight_x.config import Settings, load_settings
from foresight_x.harness.outcome_tracker import ask_outcome
from foresight_x.orchestration.llm_factory import build_openai_llm
from foresight_x.orchestration.pipeline import PipelineContext, run_pipeline
from foresight_x.retrieval.memory import UserMemory
from foresight_x.retrieval.world_cache import WorldKnowledge
from foresight_x.schemas import DecisionTrace


def _build_context(settings: Settings) -> tuple[PipelineContext, list[str]]:
    notes: list[str] = []
    llm = None
    user_memory = None
    world = None
    if settings.openai_api_key:
        try:
            llm = build_openai_llm(settings)
        except Exception as exc:
            notes.append(f"LLM unavailable: {exc}")
        try:
            user_memory = UserMemory(settings.foresight_user_id, settings=settings)
        except Exception as exc:
            notes.append(f"Memory unavailable: {exc}")
        try:
            world = WorldKnowledge(settings=settings)
        except Exception as exc:
            notes.append(f"World retrieval unavailable: {exc}")
    else:
        notes.append("OPENAI_API_KEY missing; running without vector retrieval.")
    if not settings.tavily_api_key:
        notes.append("TAVILY_API_KEY missing; live web retrieval is disabled.")
    return PipelineContext(settings=settings, llm=llm, user_memory=user_memory, world=world), notes


def render_trace_sections(trace: DecisionTrace) -> str:
    """Render the required 7 demo sections for CLI/UI."""
    insights = []
    insights.append(
        f"Decision type: {trace.user_state.decision_type}; time pressure: {trace.user_state.time_pressure.value}"
    )
    insights.append(f"Stress/workload: {trace.user_state.stress_level}/10, {trace.user_state.workload}/10")
    if trace.rationality.detected_biases:
        insights.append("Bias risks: " + ", ".join(trace.rationality.detected_biases))
    if trace.memory.behavioral_patterns:
        insights.append("Memory patterns: " + "; ".join(trace.memory.behavioral_patterns[:3]))

    options_block = "\n".join(
        f"- [{o.option_id}] {o.name}: {o.description}" for o in trace.options
    )

    eval_map = {e.option_id: e for e in trace.evaluations}
    tradeoffs = []
    for opt in trace.options:
        ev = eval_map.get(opt.option_id)
        if ev is None:
            continue
        tradeoffs.append(
            f"- {opt.name}: EV={ev.expected_value_score:.1f}, "
            f"Risk={ev.risk_score:.1f}, Regret={ev.regret_score:.1f}, "
            f"Uncertainty={ev.uncertainty_score:.1f}, GoalAlign={ev.goal_alignment_score:.1f}"
        )
    tradeoffs_block = "\n".join(tradeoffs) if tradeoffs else "- No evaluation scores available."

    actions = "\n".join(
        f"- {a.action}" + (f" (deadline: {a.deadline})" if a.deadline else "")
        for a in trace.recommendation.next_actions
    )
    reflection = "\n".join(
        [
            "- Possible errors: " + ", ".join(trace.reflection.possible_errors[:3]),
            "- Uncertainty sources: " + ", ".join(trace.reflection.uncertainty_sources[:3]),
            "- Information gaps: " + ", ".join(trace.reflection.information_gaps[:3]),
            f"- Self-improvement signal: {trace.reflection.self_improvement_signal}",
        ]
    )

    return (
        "== Situation ==\n"
        f"{trace.user_state.raw_input}\n\n"
        "== Insights ==\n"
        + "\n".join(f"- {line}" for line in insights)
        + "\n\n== Options ==\n"
        + options_block
        + "\n\n== Trade-offs ==\n"
        + tradeoffs_block
        + "\n\n== Recommendation ==\n"
        + f"{trace.recommendation.reasoning}\n"
        + f"Chosen option: {trace.recommendation.chosen_option_id}\n\n"
        + "== Actions ==\n"
        + actions
        + "\n\n== Reflection ==\n"
        + reflection
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Foresight-X CLI")
    parser.add_argument("raw_input", nargs="?", help="Decision text to analyze")
    parser.add_argument(
        "--record-outcome",
        metavar="DECISION_ID",
        help="Record outcome for a previously saved decision id.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full DecisionTrace JSON after the 7 sections.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    if args.record_outcome:
        out = ask_outcome(args.record_outcome, settings=settings)
        print(f"Outcome saved for {out.decision_id} at {settings.outcomes_dir / (out.decision_id + '.json')}")
        return 0

    if not args.raw_input:
        parser.error("raw_input is required unless --record-outcome is used")

    ctx, notes = _build_context(settings)
    trace = run_pipeline(ctx, args.raw_input, persist_trace=True)

    for note in notes:
        print(f"[note] {note}")
    print(render_trace_sections(trace))
    print(f"\nTrace saved: {settings.traces_dir / (trace.decision_id + '.json')}")
    if args.json:
        print("\n== Trace JSON ==")
        print(json.dumps(trace.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
