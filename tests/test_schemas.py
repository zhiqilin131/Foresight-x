"""Contract tests for foresight_x.schemas."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from foresight_x.schemas import (
    DecisionOutcome,
    DecisionTrace,
    EvidenceBundle,
    Fact,
    MemoryBundle,
    NextAction,
    Option,
    OptionEvaluation,
    PastDecision,
    RationalityReport,
    Recommendation,
    Reflection,
    Scenario,
    SimulatedFuture,
    UserState,
    Reversibility,
    TimePressure,
)


class TestUserState:
    def test_valid_minimal(self, sample_user_state_dict: dict) -> None:
        state = UserState.model_validate(sample_user_state_dict)
        assert state.decision_type == "career"
        assert state.time_pressure is TimePressure.HIGH
        assert state.reversibility is Reversibility.PARTIAL

    def test_stress_level_bounds(self, sample_user_state_dict: dict) -> None:
        sample_user_state_dict["stress_level"] = 11
        with pytest.raises(ValidationError):
            UserState.model_validate(sample_user_state_dict)

    def test_json_round_trip(self, sample_user_state_dict: dict) -> None:
        s = UserState.model_validate(sample_user_state_dict)
        raw = s.model_dump(mode="json")
        restored = UserState.model_validate(raw)
        assert restored == s


class TestPastDecision:
    def test_outcome_quality_optional(self) -> None:
        pd = PastDecision(
            decision_id="d1",
            situation_summary="Internship choice",
            chosen_option="accept",
            timestamp="2026-01-01T00:00:00Z",
        )
        assert pd.outcome_quality is None

    def test_outcome_quality_range(self) -> None:
        with pytest.raises(ValidationError):
            PastDecision(
                decision_id="d1",
                situation_summary="x",
                chosen_option="y",
                outcome_quality=6,
                timestamp="2026-01-01T00:00:00Z",
            )


class TestSimulatedFuture:
    def test_probabilities_must_sum(self) -> None:
        base = dict(
            option_id="opt1",
            time_horizon="3 months",
            scenarios=[
                Scenario(
                    label="best",
                    trajectory="up",
                    probability=0.34,
                    key_drivers=["a"],
                ),
                Scenario(
                    label="base",
                    trajectory="flat",
                    probability=0.33,
                    key_drivers=["b"],
                ),
                Scenario(
                    label="worst",
                    trajectory="down",
                    probability=0.33,
                    key_drivers=["c"],
                ),
            ],
        )
        SimulatedFuture.model_validate(base)

    def test_probabilities_sum_out_of_tolerance(self) -> None:
        with pytest.raises(ValidationError) as exc:
            SimulatedFuture(
                option_id="opt1",
                time_horizon="1 month",
                scenarios=[
                    Scenario(
                        label="best",
                        trajectory="x",
                        probability=0.5,
                        key_drivers=[],
                    ),
                    Scenario(
                        label="base",
                        trajectory="y",
                        probability=0.5,
                        key_drivers=[],
                    ),
                    Scenario(
                        label="worst",
                        trajectory="z",
                        probability=0.5,
                        key_drivers=[],
                    ),
                ],
            )
        assert "probabilities must sum" in str(exc.value).lower()

    def test_empty_scenarios_allowed(self) -> None:
        SimulatedFuture(option_id="o", time_horizon="t", scenarios=[])


class TestNextAction:
    def test_artifacts_default(self) -> None:
        na = NextAction(action="Email recruiter")
        assert na.artifacts == []


class TestDecisionTrace:
    def test_full_trace_round_trip(self) -> None:
        us = UserState(
            raw_input="test",
            goals=["g"],
            time_pressure=TimePressure.LOW,
            stress_level=1,
            workload=1,
            current_behavior="calm",
            decision_type="academic",
            reversibility=Reversibility.REVERSIBLE,
        )
        mem = MemoryBundle(
            similar_past_decisions=[],
            behavioral_patterns=[],
            prior_outcomes_summary="none",
        )
        ev = EvidenceBundle(
            facts=[Fact(text="f1", confidence=0.9)],
            base_rates=[],
            recent_events=[],
        )
        rat = RationalityReport(
            is_rational_state=True,
            detected_biases=[],
            confidence=0.8,
            recommended_slowdowns=[],
        )
        opts = [
            Option(
                option_id="o1",
                name="A",
                description="d",
                key_assumptions=["k"],
                cost_of_reversal="low",
            )
        ]
        fut = SimulatedFuture(
            option_id="o1",
            time_horizon="1w",
            scenarios=[
                Scenario(
                    label="best",
                    trajectory="t",
                    probability=1.0,
                    key_drivers=["x"],
                ),
            ],
        )
        eva = OptionEvaluation(
            option_id="o1",
            expected_value_score=5.0,
            risk_score=3.0,
            regret_score=2.0,
            uncertainty_score=4.0,
            goal_alignment_score=7.0,
            rationale="because",
        )
        rec = Recommendation(
            chosen_option_id="o1",
            reasoning="cites memory and evidence",
            next_actions=[NextAction(action="call")],
            reassessment_triggers=["if new info"],
        )
        refl = Reflection(
            possible_errors=[],
            uncertainty_sources=["u"],
            model_limitations=[],
            information_gaps=[],
            self_improvement_signal="need more data",
        )
        trace = DecisionTrace(
            decision_id="trace-1",
            timestamp="2026-04-18T12:00:00Z",
            user_state=us,
            memory=mem,
            evidence=ev,
            rationality=rat,
            options=opts,
            futures=[fut],
            evaluations=[eva],
            recommendation=rec,
            reflection=refl,
        )
        dumped = trace.model_dump(mode="json")
        json_str = json.dumps(dumped)
        restored = DecisionTrace.model_validate_json(json_str)
        assert restored.decision_id == trace.decision_id
        assert restored.futures[0].scenarios[0].probability == 1.0


class TestDecisionOutcome:
    def test_quality_bounds(self) -> None:
        with pytest.raises(ValidationError):
            DecisionOutcome(
                decision_id="d",
                user_took_recommended_action=True,
                actual_outcome="ok",
                user_reported_quality=0,
                reversed_later=False,
                timestamp="2026-01-01T00:00:00Z",
            )
