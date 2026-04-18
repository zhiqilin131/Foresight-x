"""Tests for recommender."""

from __future__ import annotations

from typing import Any

from foresight_x.decision.recommender import composite_score, recommend, DEFAULT_EVALUATION_WEIGHTS
from foresight_x.schemas import (
    EvidenceBundle,
    MemoryBundle,
    Option,
    OptionEvaluation,
    Recommendation,
    Reversibility,
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


def _ctx() -> tuple[UserState, MemoryBundle, EvidenceBundle]:
    st = UserState(
        raw_input="r",
        goals=["g"],
        time_pressure=TimePressure.MEDIUM,
        stress_level=5,
        workload=5,
        current_behavior="x",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
    )
    return st, MemoryBundle(similar_past_decisions=[], behavioral_patterns=[], prior_outcomes_summary=""), EvidenceBundle(facts=[], base_rates=[], recent_events=[])


def test_composite_score_monotonic() -> None:
    high_ev = OptionEvaluation(
        option_id="1",
        expected_value_score=10.0,
        risk_score=0.0,
        regret_score=0.0,
        uncertainty_score=0.0,
        goal_alignment_score=10.0,
        rationale="",
    )
    low_ev = OptionEvaluation(
        option_id="2",
        expected_value_score=0.0,
        risk_score=10.0,
        regret_score=10.0,
        uncertainty_score=10.0,
        goal_alignment_score=0.0,
        rationale="",
    )
    assert composite_score(high_ev, DEFAULT_EVALUATION_WEIGHTS) > composite_score(
        low_ev, DEFAULT_EVALUATION_WEIGHTS
    )


def test_recommend_picks_higher_composite() -> None:
    _, mem, ev = _ctx()
    options = [
        Option(option_id="a", name="A", description="", key_assumptions=[], cost_of_reversal="low"),
        Option(option_id="b", name="B", description="", key_assumptions=[], cost_of_reversal="low"),
    ]
    evaluations = [
        OptionEvaluation(
            option_id="a",
            expected_value_score=2.0,
            risk_score=8.0,
            regret_score=8.0,
            uncertainty_score=8.0,
            goal_alignment_score=2.0,
            rationale="",
        ),
        OptionEvaluation(
            option_id="b",
            expected_value_score=9.0,
            risk_score=2.0,
            regret_score=2.0,
            uncertainty_score=2.0,
            goal_alignment_score=9.0,
            rationale="",
        ),
    ]
    rec = recommend(evaluations, options, ev, mem, llm=None)
    assert rec.chosen_option_id == "b"


def test_recommend_llm_path() -> None:
    _, mem, ev = _ctx()
    options = [
        Option(option_id="x", name="X", description="", key_assumptions=[], cost_of_reversal="low"),
    ]
    evaluations = [
        OptionEvaluation(
            option_id="x",
            expected_value_score=5.0,
            risk_score=5.0,
            regret_score=5.0,
            uncertainty_score=5.0,
            goal_alignment_score=5.0,
            rationale="",
        ),
    ]
    rec_obj = Recommendation(
        chosen_option_id="x",
        reasoning="Because evidence supports it.",
        next_actions=[],
        reassessment_triggers=["t1"],
    )
    rec = recommend(evaluations, options, ev, mem, llm=FakeLLM(rec_obj))
    assert rec.reasoning.startswith("Because")


def test_recommend_invalid_chosen_id_snapped() -> None:
    _, mem, ev = _ctx()
    options = [
        Option(option_id="ok", name="OK", description="", key_assumptions=[], cost_of_reversal="low"),
    ]
    evaluations = [
        OptionEvaluation(
            option_id="ok",
            expected_value_score=5.0,
            risk_score=5.0,
            regret_score=5.0,
            uncertainty_score=5.0,
            goal_alignment_score=5.0,
            rationale="",
        ),
    ]
    bad = Recommendation(
        chosen_option_id="nope",
        reasoning="x",
        next_actions=[],
        reassessment_triggers=[],
    )
    rec = recommend(evaluations, options, ev, mem, llm=FakeLLM(bad))
    assert rec.chosen_option_id == "ok"


def test_recommend_requires_options() -> None:
    try:
        recommend([], [], EvidenceBundle(facts=[], base_rates=[], recent_events=[]), MemoryBundle(similar_past_decisions=[], behavioral_patterns=[], prior_outcomes_summary=""))
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "at least one option" in str(e).lower()
