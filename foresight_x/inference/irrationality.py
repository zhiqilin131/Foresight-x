"""Irrationality detection: deterministic rules plus optional LLM refinement."""

from __future__ import annotations

from typing import Any, Protocol

from foresight_x.structured_predict import structured_predict
from foresight_x.prompts.irrationality import irrationality_prompt
from foresight_x.schemas import MemoryBundle, RationalityReport, Reversibility, TimePressure, UserState


class StructuredPredictLLM(Protocol):
    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def detect_rule_flags(user_state: UserState, memory: MemoryBundle) -> tuple[list[str], list[str]]:
    flags: list[str] = []
    slowdowns: list[str] = []

    if (
        user_state.stress_level >= 8
        and user_state.reversibility == Reversibility.IRREVERSIBLE
    ):
        flags.append("high_stress_irreversible")
        slowdowns.append("Sleep on the decision before committing.")

    if (
        user_state.time_pressure == TimePressure.HIGH
        and user_state.reversibility != Reversibility.REVERSIBLE
    ):
        flags.append("rushed_high_stakes")
        slowdowns.append("Ask for a brief deadline extension to collect one more data point.")

    if memory.similar_past_decisions and "regret" in memory.prior_outcomes_summary.lower():
        flags.append("regret_pattern_detected")
        slowdowns.append("Write a short pre-mortem: what would make this decision fail?")

    if user_state.workload >= 8:
        flags.append("cognitive_overload_risk")
        slowdowns.append("Defer non-critical tasks and decide in a focused 30-minute block.")

    return _unique(flags), _unique(slowdowns)


def _rule_only_report(user_state: UserState, memory: MemoryBundle) -> RationalityReport:
    flags, slowdowns = detect_rule_flags(user_state, memory)
    return RationalityReport(
        is_rational_state=len(flags) == 0,
        detected_biases=flags,
        confidence=0.65 if flags else 0.85,
        recommended_slowdowns=slowdowns,
    )


def detect_irrationality(
    user_state: UserState,
    memory: MemoryBundle,
    llm: StructuredPredictLLM | None = None,
) -> RationalityReport:
    """Blend deterministic signals with optional LLM judgment."""
    base = _rule_only_report(user_state, memory)
    if llm is None:
        return base

    prompt = irrationality_prompt(user_state, memory, base.detected_biases)
    try:
        llm_out = structured_predict(llm, RationalityReport, prompt)
        llm_report = llm_out if isinstance(llm_out, RationalityReport) else RationalityReport.model_validate(llm_out)
    except Exception:
        return base

    merged_biases = _unique(base.detected_biases + llm_report.detected_biases)
    merged_slowdowns = _unique(base.recommended_slowdowns + llm_report.recommended_slowdowns)
    merged_conf = max(0.0, min(1.0, (base.confidence + llm_report.confidence) / 2.0))

    return RationalityReport(
        is_rational_state=base.is_rational_state and llm_report.is_rational_state and not merged_biases,
        detected_biases=merged_biases,
        confidence=merged_conf,
        recommended_slowdowns=merged_slowdowns,
    )
