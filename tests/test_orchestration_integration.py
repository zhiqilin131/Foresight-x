"""Heavy integration tests: pipeline ↔ workflow parity, Chroma stack, routing LLM."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from llama_index.core.embeddings import MockEmbedding

from foresight_x.config import Settings
from foresight_x.inference.option_generator import OptionSet
from foresight_x.orchestration.pipeline import PipelineContext, run_pipeline
from foresight_x.orchestration.workflow import ForesightStartEvent, ForesightWorkflow, run_pipeline_workflow
from foresight_x.retrieval.memory import UserMemory
from foresight_x.retrieval.seed import ingest_memory_json, ingest_world_markdown
from foresight_x.retrieval.world_cache import WorldKnowledge
from foresight_x.schemas import (
    DecisionTrace,
    EvidenceBundle,
    Fact,
    MemoryBundle,
    NextAction,
    Option,
    OptionEvaluation,
    RationalityReport,
    Recommendation,
    Reflection,
    Reversibility,
    Scenario,
    SimulatedFuture,
    TimePressure,
    UserState,
)


def _freeze_time(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = "2026-04-18T15:00:00Z"

    def _utc() -> str:
        return fixed

    monkeypatch.setattr("foresight_x.orchestration.pipeline.utc_timestamp", _utc)
    monkeypatch.setattr("foresight_x.orchestration.workflow.utc_timestamp", _utc)


@pytest.fixture
def chroma_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
    monkeypatch.delenv("FORESIGHT_DATA_DIR", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    return Settings(
        chroma_persist_dir=tmp_path / "chroma",
        foresight_data_dir=tmp_path / "data",
        openai_api_key="test",
        tavily_api_key="test",
    )


@pytest.fixture
def embed_model() -> MockEmbedding:
    return MockEmbedding(embed_dim=1536)


def test_pipeline_and_workflow_semantic_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same inputs → same structured outcome (frozen clock; no live APIs)."""
    _freeze_time(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    settings = Settings(foresight_data_dir=tmp_path)
    ctx = PipelineContext(settings=settings, llm=None)

    raw = (
        "I must choose between two internship offers; deadline Friday; "
        "I feel anxious and rushed."
    )
    did = "parity-1"

    trace_p = run_pipeline(ctx, raw, decision_id=did, persist_trace=False)

    async def _wf() -> DecisionTrace:
        return await run_pipeline_workflow(ctx, raw, decision_id=did, persist_trace=False, workflow_timeout=120.0)

    trace_w = asyncio.run(_wf())

    assert trace_p.decision_id == trace_w.decision_id == did
    assert trace_p.timestamp == trace_w.timestamp
    assert trace_p.user_state.model_dump() == trace_w.user_state.model_dump()
    assert trace_p.memory.model_dump() == trace_w.memory.model_dump()
    assert trace_p.evidence.model_dump() == trace_w.evidence.model_dump()
    assert [o.model_dump() for o in trace_p.options] == [o.model_dump() for o in trace_w.options]
    assert [f.model_dump() for f in trace_p.futures] == [f.model_dump() for f in trace_w.futures]
    assert [e.model_dump() for e in trace_p.evaluations] == [e.model_dump() for e in trace_w.evaluations]
    assert trace_p.recommendation.model_dump() == trace_w.recommendation.model_dump()
    assert trace_p.reflection.model_dump() == trace_w.reflection.model_dump()


def test_decision_trace_cross_field_invariants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scores, option ids, and scenario probabilities stay internally consistent."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    settings = Settings(foresight_data_dir=tmp_path)
    ctx = PipelineContext(settings=settings, llm=None)
    trace = run_pipeline(
        ctx,
        "Strategic career pivot with irreversible visa implications.",
        decision_id="inv-1",
        persist_trace=False,
    )

    opt_ids = {o.option_id for o in trace.options}
    assert opt_ids
    for ev in trace.evaluations:
        assert ev.option_id in opt_ids
        assert 0 <= ev.expected_value_score <= 10
    for fut in trace.futures:
        assert fut.option_id in opt_ids
        if fut.scenarios:
            total = sum(s.probability for s in fut.scenarios)
            assert abs(total - 1.0) < 1e-5
            assert {s.label for s in fut.scenarios} == {"best", "base", "worst"}
    assert trace.recommendation.chosen_option_id in opt_ids


def test_trace_persist_round_trip_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Saved JSON re-validates as DecisionTrace."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    settings = Settings(foresight_data_dir=tmp_path)
    ctx = PipelineContext(settings=settings, llm=None)
    run_pipeline(ctx, "Round-trip persistence check.", decision_id="json-1", persist_trace=True)
    path = settings.traces_dir / "json-1.json"
    assert path.is_file()
    raw_json = path.read_text(encoding="utf-8")
    data = json.loads(raw_json)
    assert "memory" in data and "evidence" in data
    again = DecisionTrace.model_validate(data)
    assert again.decision_id == "json-1"


def test_chroma_memory_and_world_feed_pipeline(
    chroma_settings: Settings,
    embed_model: MockEmbedding,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seeded UserMemory + WorldKnowledge surface in the final trace (no Tavily HTTP)."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    mem = UserMemory("integration_user", settings=chroma_settings, embed_model=embed_model)
    ingest_memory_json(mem)
    world = WorldKnowledge(settings=chroma_settings, embed_model=embed_model, tavily=None)
    ingest_world_markdown(world)

    ctx = PipelineContext(
        settings=Settings(foresight_data_dir=chroma_settings.foresight_data_dir, chroma_persist_dir=chroma_settings.chroma_persist_dir),
        llm=None,
        user_memory=mem,
        world=world,
    )

    trace = run_pipeline(
        ctx,
        "Should I accept the return offer or wait for campus recruiting — deadline soon?",
        decision_id="chroma-full-1",
        persist_trace=False,
    )

    assert trace.memory.similar_past_decisions, "expected at least one retrieved past decision"
    assert (
        len(trace.evidence.facts) + len(trace.evidence.base_rates) + len(trace.evidence.recent_events)
    ) >= 1


class RoutingLLM:
    """Returns typed objects for each structured_predict by output class name."""

    def __init__(self) -> None:
        self.output_classes: list[str] = []
        self.sim_index = 0
        self.eval_index = 0

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        name = getattr(output_cls, "__name__", "")
        self.output_classes.append(name)

        if name == "UserState":
            return UserState(
                raw_input="synthetic routing input",
                goals=["clarity", "speed"],
                time_pressure=TimePressure.MEDIUM,
                stress_level=4,
                workload=5,
                current_behavior="deliberate",
                decision_type="career",
                reversibility=Reversibility.PARTIAL,
            )
        if name == "RationalityReport":
            return RationalityReport(
                is_rational_state=True,
                detected_biases=[],
                confidence=0.88,
                recommended_slowdowns=[],
            )
        if name == "OptionSet":
            return OptionSet(
                options=[
                    Option(
                        option_id="r_o1",
                        name="Path Alpha",
                        description="First path.",
                        key_assumptions=["A holds"],
                        cost_of_reversal="low",
                    ),
                    Option(
                        option_id="r_o2",
                        name="Path Beta",
                        description="Second path.",
                        key_assumptions=["B holds"],
                        cost_of_reversal="medium",
                    ),
                ]
            )
        if name == "SimulatedFuture":
            oid = "r_o1" if self.sim_index == 0 else "r_o2"
            self.sim_index += 1
            return SimulatedFuture(
                option_id=oid,
                time_horizon="4 months",
                scenarios=[
                    Scenario(label="best", trajectory="up", probability=0.25, key_drivers=["x"]),
                    Scenario(label="base", trajectory="flat", probability=0.5, key_drivers=["y"]),
                    Scenario(label="worst", trajectory="down", probability=0.25, key_drivers=["z"]),
                ],
            )
        if name == "OptionEvaluation":
            oid = "r_o1" if self.eval_index == 0 else "r_o2"
            self.eval_index += 1
            return OptionEvaluation(
                option_id=oid,
                expected_value_score=7.0 if oid == "r_o1" else 5.0,
                risk_score=3.0,
                regret_score=3.0,
                uncertainty_score=4.0,
                goal_alignment_score=8.0 if oid == "r_o1" else 6.0,
                rationale=f"scores for {oid}",
            )
        if name == "Recommendation":
            return Recommendation(
                chosen_option_id="r_o1",
                reasoning="Alpha dominates on alignment.",
                next_actions=[
                    NextAction(action="Draft email", deadline="Mon", artifacts=["draft.md"])
                ],
                reassessment_triggers=["Offer changes"],
            )
        if name == "Reflection":
            return Reflection(
                possible_errors=["e1"],
                uncertainty_sources=["u1"],
                model_limitations=["m1"],
                information_gaps=["g1"],
                self_improvement_signal="sig1",
            )
        raise AssertionError(f"unexpected output_cls {output_cls}")


def test_routing_llm_full_stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every LLM touchpoint receives a valid structured object; recommend follows higher EV."""
    monkeypatch.setenv("TAVILY_API_KEY", "")
    settings = Settings(foresight_data_dir=tmp_path)
    llm = RoutingLLM()
    ctx = PipelineContext(settings=settings, llm=llm)

    trace = run_pipeline(
        ctx,
        "ignored — LLM supplies UserState",
        decision_id="route-1",
        persist_trace=False,
    )

    expected_types = [
        "UserState",
        "RationalityReport",
        "OptionSet",
        "SimulatedFuture",
        "SimulatedFuture",
        "OptionEvaluation",
        "OptionEvaluation",
        "Recommendation",
        "Reflection",
    ]
    assert llm.output_classes == expected_types
    assert trace.recommendation.chosen_option_id == "r_o1"
    assert trace.reflection.self_improvement_signal == "sig1"
    assert {o.option_id for o in trace.options} == {"r_o1", "r_o2"}


def test_workflow_class_matches_routing_pipeline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _freeze_time(monkeypatch)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    settings = Settings(foresight_data_dir=tmp_path)
    llm = RoutingLLM()
    ctx = PipelineContext(settings=settings, llm=llm)

    trace_p = run_pipeline(ctx, "x", decision_id="wcmp-1", persist_trace=False)

    async def _run() -> DecisionTrace:
        wf = ForesightWorkflow(ctx, timeout=120.0)
        return await wf.run(
            start_event=ForesightStartEvent(raw_input="x", decision_id="wcmp-1", persist_trace=False)
        )

    trace_w = asyncio.run(_run())
    assert trace_p.recommendation.chosen_option_id == trace_w.recommendation.chosen_option_id
    assert trace_p.options == trace_w.options


def test_tavily_mock_injects_recent_events_in_trace(
    chroma_settings: Settings,
    embed_model: MockEmbedding,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sparse cache + time-sensitive query calls Tavily mock; trace JSON lists recent_events."""
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
    mock_gw = MagicMock()
    mock_gw.search_as_facts.return_value = [
        Fact(text="External labor market note 2026.", source_url="https://example.test/a", confidence=0.72)
    ]
    world = WorldKnowledge(settings=chroma_settings, embed_model=embed_model, tavily=mock_gw)

    ctx = PipelineContext(
        settings=Settings(
            foresight_data_dir=chroma_settings.foresight_data_dir,
            chroma_persist_dir=chroma_settings.chroma_persist_dir,
        ),
        llm=None,
        world=world,
    )

    trace = run_pipeline(
        ctx,
        "Urgent offer — must decide tomorrow on career move.",
        decision_id="tavily-trace-1",
        persist_trace=True,
    )
    assert mock_gw.search_as_facts.called
    assert any("labor market" in f.text.lower() for f in trace.evidence.recent_events)
    dumped = (chroma_settings.foresight_data_dir / "traces" / "tavily-trace-1.json").read_text(encoding="utf-8")
    assert "labor market" in dumped.lower() or "recent_events" in dumped
