"""UserMemory retrieval tests (MockEmbedding + temp Chroma)."""

from __future__ import annotations

from pathlib import Path

import pytest
from llama_index.core.embeddings import MockEmbedding

from foresight_x.config import Settings
from foresight_x.harness.improvement_loop import apply_outcome_to_memory
from foresight_x.orchestration.pipeline import PipelineContext, run_pipeline
from foresight_x.retrieval.memory import UserMemory
from foresight_x.schemas import (
    DecisionOutcome,
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
    # Force env so pydantic-settings + .env cannot point Chroma at a shared ./data/chroma.
    chroma = tmp_path / "chroma"
    data = tmp_path / "data"
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(chroma))
    monkeypatch.setenv("FORESIGHT_DATA_DIR", str(data))
    monkeypatch.setenv("TAVILY_API_KEY", "")
    return Settings()


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


def test_pipeline_persist_does_not_index_without_outcome(
    embed_model: MockEmbedding,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persisted trace JSON exists, but UserMemory stays empty until an outcome is recorded."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    mem = UserMemory(settings.foresight_user_id, settings=settings, embed_model=embed_model)
    ctx = PipelineContext(settings=settings, llm=None, user_memory=mem)
    run_pipeline(
        ctx,
        "remote work policy negotiation timeline and manager expectations",
        decision_id="pre-outcome-only",
        persist_trace=True,
    )
    assert settings.traces_dir.joinpath("pre-outcome-only.json").is_file()
    ids = {r.decision_id for r in mem.list_all_past_decisions()}
    assert "pre-outcome-only" not in ids


def test_apply_outcome_twice_reindexes_single_entry(
    embed_model: MockEmbedding,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recording an outcome twice is safe: remove + re-add leaves one logical row per decision_id."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    mem = UserMemory(settings.foresight_user_id, settings=settings, embed_model=embed_model)
    run_pipeline(
        PipelineContext(settings=settings, llm=None, user_memory=mem),
        "deadline extension request wording",
        decision_id="double-apply-1",
        persist_trace=True,
    )
    o1 = DecisionOutcome(
        decision_id="double-apply-1",
        user_took_recommended_action=True,
        actual_outcome="First report.",
        user_reported_quality=3,
        reversed_later=False,
        timestamp="2026-01-01T00:00:00Z",
    )
    apply_outcome_to_memory("double-apply-1", o1, settings=settings, user_memory=mem)
    o2 = DecisionOutcome(
        decision_id="double-apply-1",
        user_took_recommended_action=True,
        actual_outcome="Updated report.",
        user_reported_quality=5,
        reversed_later=False,
        timestamp="2026-02-01T00:00:00Z",
    )
    apply_outcome_to_memory("double-apply-1", o2, settings=settings, user_memory=mem)
    rows = [r for r in mem.list_all_past_decisions() if r.decision_id == "double-apply-1"]
    assert len(rows) == 1
    assert rows[0].outcome == "Updated report."
    assert rows[0].outcome_quality == 5


def test_pipeline_persist_indexes_for_subsequent_retrieval(
    embed_model: MockEmbedding,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After an outcome is recorded, the decision is indexed; a later run can retrieve it."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    mem = UserMemory(settings.foresight_user_id, settings=settings, embed_model=embed_model)
    ctx = PipelineContext(settings=settings, llm=None, user_memory=mem)
    run_pipeline(
        ctx,
        "career internship deadline anxiety offer versus wait",
        decision_id="carry-a",
        persist_trace=True,
    )
    apply_outcome_to_memory(
        "carry-a",
        DecisionOutcome(
            decision_id="carry-a",
            user_took_recommended_action=True,
            actual_outcome="Chose offer A.",
            user_reported_quality=4,
            reversed_later=False,
            timestamp="2026-01-10T00:00:00Z",
        ),
        settings=settings,
        user_memory=mem,
    )
    trace_b = run_pipeline(
        ctx,
        "career internship follow-up should I renege on acceptance",
        decision_id="carry-b",
        persist_trace=True,
    )
    bundle = mem.retrieve(trace_b.user_state, top_k=12)
    ids = {p.decision_id for p in bundle.similar_past_decisions}
    assert "carry-a" in ids


def test_list_all_past_decisions_returns_unique_newest_first(
    embed_model: MockEmbedding,
    settings: Settings,
) -> None:
    mem = UserMemory("list_user", settings=settings, embed_model=embed_model)
    mem.add_past_decision(
        PastDecision(
            decision_id="d-old",
            situation_summary="older one",
            chosen_option="wait",
            outcome="ok",
            outcome_quality=3,
            timestamp="2026-01-01T00:00:00Z",
        )
    )
    mem.add_past_decision(
        PastDecision(
            decision_id="d-new",
            situation_summary="newer one",
            chosen_option="act",
            outcome="great",
            outcome_quality=5,
            timestamp="2026-03-01T00:00:00Z",
        )
    )
    # Re-insert same decision id with newer timestamp to verify dedupe keeps newest.
    mem.add_past_decision(
        PastDecision(
            decision_id="d-old",
            situation_summary="older one updated",
            chosen_option="wait",
            outcome="better",
            outcome_quality=4,
            timestamp="2026-02-01T00:00:00Z",
        )
    )

    rows = mem.list_all_past_decisions()
    assert [r.decision_id for r in rows] == ["d-new", "d-old"]
    assert rows[1].outcome == "better"
