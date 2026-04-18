"""UserMemory retrieval tests (MockEmbedding + temp Chroma)."""

from __future__ import annotations

from pathlib import Path

import pytest
from llama_index.core.embeddings import MockEmbedding

from foresight_x.config import Settings
from foresight_x.retrieval.memory import UserMemory
from foresight_x.schemas import (
    PastDecision,
    Reversibility,
    TimePressure,
    UserState,
)


@pytest.fixture
def embed_model() -> MockEmbedding:
    return MockEmbedding(embed_dim=1536)


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    # Ensure a local .env does not override isolated Chroma dirs.
    monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
    monkeypatch.delenv("FORESIGHT_DATA_DIR", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    return Settings(
        chroma_persist_dir=tmp_path / "chroma",
        foresight_data_dir=tmp_path / "data",
        openai_api_key="test",
        tavily_api_key="test",
    )


def test_add_and_retrieve_round_trip(embed_model: MockEmbedding, settings: Settings) -> None:
    mem = UserMemory("demo_user", settings=settings, embed_model=embed_model)
    p1 = PastDecision(
        decision_id="d1",
        situation_summary="Career offer from Company A versus waiting for Company B.",
        chosen_option="Negotiate deadline extension",
        outcome="Got extension and better information.",
        outcome_quality=5,
        timestamp="2026-03-01T00:00:00Z",
    )
    p2 = PastDecision(
        decision_id="d2",
        situation_summary="Unrelated academic course drop decision.",
        chosen_option="Stayed enrolled",
        outcome="Passed",
        outcome_quality=4,
        timestamp="2026-02-01T00:00:00Z",
    )
    mem.add_past_decision(p1, behavioral_patterns=["Seeks more data under uncertainty"])
    mem.add_past_decision(p2)

    state = UserState(
        raw_input="I have an offer from Company X and an interview with Y next week. What should I do?",
        goals=["good long-term fit"],
        time_pressure=TimePressure.HIGH,
        stress_level=8,
        workload=5,
        current_behavior="anxious",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
        deadline_hint="Friday",
    )
    bundle = mem.retrieve(state, top_k=3)
    assert len(bundle.similar_past_decisions) >= 1
    ids = {d.decision_id for d in bundle.similar_past_decisions}
    assert "d1" in ids
    assert any("uncertainty" in p.lower() for p in bundle.behavioral_patterns) or bundle.behavioral_patterns


def test_add_decision_from_trace(embed_model: MockEmbedding, settings: Settings) -> None:
    from foresight_x.schemas import (
        DecisionTrace,
        EvidenceBundle,
        MemoryBundle,
        NextAction,
        Option,
        OptionEvaluation,
        RationalityReport,
        Recommendation,
        Reflection,
        SimulatedFuture,
    )

    mem = UserMemory("u2", settings=settings, embed_model=embed_model)
    us = UserState(
        raw_input="choose internship",
        goals=["learn"],
        time_pressure=TimePressure.LOW,
        stress_level=2,
        workload=3,
        current_behavior="calm",
        decision_type="career",
        reversibility=Reversibility.REVERSIBLE,
    )
    opt = Option(
        option_id="o1",
        name="Accept",
        description="take offer",
        key_assumptions=["stable"],
        cost_of_reversal="low",
    )
    trace = DecisionTrace(
        decision_id="t-1",
        timestamp="2026-04-18T00:00:00Z",
        user_state=us,
        memory=MemoryBundle(
            similar_past_decisions=[],
            behavioral_patterns=[],
            prior_outcomes_summary="",
        ),
        evidence=EvidenceBundle(facts=[], base_rates=[], recent_events=[]),
        rationality=RationalityReport(
            is_rational_state=True,
            detected_biases=[],
            confidence=0.9,
            recommended_slowdowns=[],
        ),
        options=[opt],
        futures=[
            SimulatedFuture(
                option_id="o1",
                time_horizon="3mo",
                scenarios=[],
            )
        ],
        evaluations=[
            OptionEvaluation(
                option_id="o1",
                expected_value_score=5.0,
                risk_score=3.0,
                regret_score=2.0,
                uncertainty_score=4.0,
                goal_alignment_score=6.0,
                rationale="ok",
            )
        ],
        recommendation=Recommendation(
            chosen_option_id="o1",
            reasoning="Accept fits goals.",
            next_actions=[NextAction(action="Sign offer letter")],
            reassessment_triggers=[],
        ),
        reflection=Reflection(
            possible_errors=[],
            uncertainty_sources=[],
            model_limitations=[],
            information_gaps=[],
            self_improvement_signal="",
        ),
    )
    mem.add_decision(trace)
    bundle = mem.retrieve(us, top_k=2)
    assert any(t.decision_id == "t-1" for t in bundle.similar_past_decisions)
