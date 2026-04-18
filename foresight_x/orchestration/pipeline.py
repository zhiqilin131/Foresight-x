"""Synchronous RIS pipeline: Perceive → Retrieve → Infer → Simulate → Decide → Reflect."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from foresight_x.config import Settings, load_settings
from foresight_x.decision.recommender import recommend
from foresight_x.decision.reflector import reflect
from foresight_x.harness.trace import save_decision_trace
from foresight_x.inference.irrationality import detect_irrationality
from foresight_x.inference.option_generator import generate_options
from foresight_x.perception.layer import build_user_state
from foresight_x.retrieval.memory import UserMemory
from foresight_x.retrieval.world_cache import WorldKnowledge
from foresight_x.schemas import (
    DecisionTrace,
    EvidenceBundle,
    MemoryBundle,
    Option,
    OptionEvaluation,
    RationalityReport,
    Reflection,
    SimulatedFuture,
    UserState,
)
from foresight_x.simulation.evaluator import evaluate_options
from foresight_x.simulation.future_simulator import simulate_futures


@dataclass
class PipelineContext:
    """Dependencies for one pipeline run."""

    settings: Settings | None = None
    llm: Any | None = None
    user_memory: UserMemory | None = None
    world: WorldKnowledge | None = None


def _empty_memory() -> MemoryBundle:
    return MemoryBundle(
        similar_past_decisions=[],
        behavioral_patterns=[],
        prior_outcomes_summary="",
    )


def _empty_evidence() -> EvidenceBundle:
    return EvidenceBundle(facts=[], base_rates=[], recent_events=[])


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def retrieve_bundles(
    user_state: UserState,
    ctx: PipelineContext,
) -> tuple[MemoryBundle, EvidenceBundle]:
    memory = ctx.user_memory.retrieve(user_state) if ctx.user_memory else _empty_memory()
    evidence = ctx.world.retrieve(user_state) if ctx.world else _empty_evidence()
    return memory, evidence


def step_infer(
    user_state: UserState,
    memory_bundle: MemoryBundle,
    evidence_bundle: EvidenceBundle,
    llm: Any | None,
) -> tuple[RationalityReport, list[Option]]:
    rationality = detect_irrationality(user_state, memory_bundle, llm)
    options = generate_options(user_state, memory_bundle, evidence_bundle, llm)
    return rationality, options


def finalize_trace(
    *,
    decision_id: str,
    timestamp: str,
    user_state: UserState,
    memory_bundle: MemoryBundle,
    evidence_bundle: EvidenceBundle,
    rationality: RationalityReport,
    options: list[Option],
    futures: list[SimulatedFuture],
    evaluations: list[OptionEvaluation],
    llm: Any | None,
    persist_trace: bool,
    settings: Settings,
) -> DecisionTrace:
    recommendation = recommend(
        evaluations,
        options,
        evidence_bundle,
        memory_bundle,
        llm=llm,
    )
    placeholder = Reflection(
        possible_errors=["pending"],
        uncertainty_sources=["pending"],
        model_limitations=["pending"],
        information_gaps=["pending"],
        self_improvement_signal="pending",
    )
    trace = DecisionTrace(
        decision_id=decision_id,
        timestamp=timestamp,
        user_state=user_state,
        memory=memory_bundle,
        evidence=evidence_bundle,
        rationality=rationality,
        options=options,
        futures=futures,
        evaluations=evaluations,
        recommendation=recommendation,
        reflection=placeholder,
    )
    reflection = reflect(trace, llm)
    trace = trace.model_copy(update={"reflection": reflection})
    if persist_trace:
        save_decision_trace(trace, settings=settings)
    return trace


def run_pipeline(
    ctx: PipelineContext,
    raw_input: str,
    *,
    decision_id: str | None = None,
    persist_trace: bool = True,
) -> DecisionTrace:
    """Execute the full RIS stack and return a ``DecisionTrace``; optionally save JSON under ``data/traces/``."""
    settings = ctx.settings or load_settings()
    did = decision_id or str(uuid.uuid4())
    ts = utc_timestamp()

    user_state = build_user_state(raw_input, ctx.llm)
    memory_bundle, evidence_bundle = retrieve_bundles(user_state, ctx)

    rationality, options = step_infer(user_state, memory_bundle, evidence_bundle, ctx.llm)

    futures = simulate_futures(options, user_state, evidence_bundle, ctx.llm)
    evaluations = evaluate_options(futures, user_state, ctx.llm)

    return finalize_trace(
        decision_id=did,
        timestamp=ts,
        user_state=user_state,
        memory_bundle=memory_bundle,
        evidence_bundle=evidence_bundle,
        rationality=rationality,
        options=options,
        futures=futures,
        evaluations=evaluations,
        llm=ctx.llm,
        persist_trace=persist_trace,
        settings=settings,
    )
