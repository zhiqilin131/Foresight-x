"""Tests for reflector."""

from __future__ import annotations

from typing import Any

from foresight_x.decision.reflector import reflect
from foresight_x.schemas import (
    DecisionTrace,
    EvidenceBundle,
    MemoryBundle,
    Option,
    OptionEvaluation,
    RationalityReport,
    Recommendation,
    Reflection,
    Reversibility,
    SimulatedFuture,
    TimePressure,
    UserState,
)


class FakeLLM:
    def __init__(self, response: Any, *, raise_error: bool = False) -> None:
        self.response = response
        self.raise_error = raise_error

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        if self.raise_error:
            raise RuntimeError("LLM unavailable")
        return self.response


def _minimal_trace() -> DecisionTrace:
    st = UserState(
        raw_input="test",
        goals=["g"],
        time_pressure=TimePressure.LOW,
        stress_level=2,
        workload=2,
        current_behavior="ok",
        decision_type="career",
        reversibility=Reversibility.REVERSIBLE,
    )
    return DecisionTrace(
        decision_id="d1",
        timestamp="2026-04-18T12:00:00Z",
        user_state=st,
        memory=MemoryBundle(similar_past_decisions=[], behavioral_patterns=[], prior_outcomes_summary=""),
        evidence=EvidenceBundle(facts=[], base_rates=[], recent_events=[]),
        rationality=RationalityReport(
            is_rational_state=True,
            detected_biases=[],
            confidence=0.8,
            recommended_slowdowns=[],
        ),
        options=[
            Option(
                option_id="o1",
                name="O1",
                description="d",
                key_assumptions=[],
                cost_of_reversal="low",
            )
        ],
        futures=[
            SimulatedFuture(
                option_id="o1",
                time_horizon="1 month",
                scenarios=[],
            )
        ],
        evaluations=[
            OptionEvaluation(
                option_id="o1",
                expected_value_score=5.0,
                risk_score=5.0,
                regret_score=5.0,
                uncertainty_score=5.0,
                goal_alignment_score=5.0,
                rationale="r",
            )
        ],
        recommendation=Recommendation(
            chosen_option_id="o1",
            reasoning="r",
            next_actions=[],
            reassessment_triggers=[],
        ),
        reflection=Reflection(
            possible_errors=["placeholder"],
            uncertainty_sources=["placeholder"],
            model_limitations=["placeholder"],
            information_gaps=["placeholder"],
            self_improvement_signal="placeholder",
        ),
    )


def test_reflect_fallback() -> None:
    out = reflect(_minimal_trace(), llm=None)
    assert out.possible_errors
    assert out.self_improvement_signal


def test_reflect_llm() -> None:
    refl = Reflection(
        possible_errors=["e1"],
        uncertainty_sources=["u1"],
        model_limitations=["m1"],
        information_gaps=["i1"],
        self_improvement_signal="s1",
    )
    out = reflect(_minimal_trace(), llm=FakeLLM(refl))
    assert out.self_improvement_signal == "s1"


def test_reflect_llm_fallback_on_error() -> None:
    out = reflect(_minimal_trace(), llm=FakeLLM(None, raise_error=True))
    assert "tail risk" in " ".join(out.possible_errors).lower() or out.possible_errors
