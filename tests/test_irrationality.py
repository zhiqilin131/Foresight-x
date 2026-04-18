"""Tests for irrationality detection."""

from __future__ import annotations

from typing import Any

from foresight_x.inference.irrationality import detect_irrationality, detect_rule_flags
from foresight_x.schemas import (
    MemoryBundle,
    PastDecision,
    RationalityReport,
    Reversibility,
    TimePressure,
    UserState,
)


class FakeLLM:
    def __init__(self, response: Any) -> None:
        self.response = response

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        return self.response


def _state(**kwargs: Any) -> UserState:
    base = dict(
        raw_input="I must decide by Friday.",
        goals=["reduce downside"],
        time_pressure=TimePressure.HIGH,
        stress_level=9,
        workload=8,
        current_behavior="rushed",
        decision_type="career",
        reversibility=Reversibility.IRREVERSIBLE,
        deadline_hint="Friday",
    )
    base.update(kwargs)
    return UserState(**base)


def _memory() -> MemoryBundle:
    return MemoryBundle(
        similar_past_decisions=[
            PastDecision(
                decision_id="d1",
                situation_summary="Chose too fast.",
                chosen_option="Accepted immediately",
                outcome="Regret due to missing information",
                outcome_quality=2,
                timestamp="2026-01-01T00:00:00Z",
            )
        ],
        behavioral_patterns=["acts quickly under pressure"],
        prior_outcomes_summary="Pattern includes regret when deciding too fast.",
    )


def test_rule_flags_capture_high_risk_pattern() -> None:
    flags, slowdowns = detect_rule_flags(_state(), _memory())
    assert "high_stress_irreversible" in flags
    assert "rushed_high_stakes" in flags
    assert "regret_pattern_detected" in flags
    assert slowdowns


def test_detect_irrationality_without_llm_uses_rules_only() -> None:
    report = detect_irrationality(_state(), _memory(), llm=None)
    assert report.is_rational_state is False
    assert "high_stress_irreversible" in report.detected_biases
    assert report.recommended_slowdowns


def test_detect_irrationality_merges_llm_and_rules() -> None:
    llm_report = RationalityReport(
        is_rational_state=False,
        detected_biases=["loss_aversion"],
        confidence=0.6,
        recommended_slowdowns=["Ask a trusted advisor to challenge your assumptions."],
    )
    report = detect_irrationality(_state(), _memory(), llm=FakeLLM(llm_report))
    assert "loss_aversion" in report.detected_biases
    assert "high_stress_irreversible" in report.detected_biases
    assert report.is_rational_state is False
