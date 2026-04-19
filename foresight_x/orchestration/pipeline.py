"""Synchronous RIS pipeline: Perceive → Retrieve → Infer → Simulate → Decide → Reflect."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

from foresight_x.config import Settings, load_settings
from foresight_x.decision.recommender import recommend
from foresight_x.decision.reflector import reflect
from foresight_x.harness.trace import save_decision_trace
from foresight_x.inference.irrationality import detect_irrationality
from foresight_x.inference.option_generator import generate_options
from foresight_x.perception.clarify_gate import merge_clarification_answers
from foresight_x.perception.layer import build_user_state
from foresight_x.perception.query_enhance import prepare_decision_text
from foresight_x.profile.merge import append_clarification_to_profile, merge_profile_into_user_state
from foresight_x.profile.store import load_user_profile, save_user_profile
from foresight_x.retrieval.memory import UserMemory
from foresight_x.retrieval.user_recent_context import merge_user_context_into_evidence
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
    settings = ctx.settings or load_settings()
    memory = ctx.user_memory.retrieve(user_state) if ctx.user_memory else _empty_memory()
    evidence = ctx.world.retrieve(user_state) if ctx.world else _empty_evidence()
    evidence = merge_user_context_into_evidence(evidence, settings)
    return memory, evidence


def retrieve_bundles_parallel(
    user_state: UserState,
    ctx: PipelineContext,
) -> tuple[MemoryBundle, EvidenceBundle]:
    """Run memory and world retrieval concurrently (embedding + vector search; thread pool)."""

    def mem() -> MemoryBundle:
        if ctx.user_memory:
            return ctx.user_memory.retrieve(user_state)
        return _empty_memory()

    def ev() -> EvidenceBundle:
        if ctx.world:
            return ctx.world.retrieve(user_state)
        return _empty_evidence()

    settings = ctx.settings or load_settings()
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_m = pool.submit(mem)
        fut_e = pool.submit(ev)
        memory_bundle, evidence_bundle = fut_m.result(), fut_e.result()
    evidence_bundle = merge_user_context_into_evidence(evidence_bundle, settings)
    return memory_bundle, evidence_bundle


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
    user_memory: UserMemory | None = None,
    original_user_input: str = "",
    anchor_now_iso: str | None = None,
) -> DecisionTrace:
    anchor = (anchor_now_iso.strip() if anchor_now_iso else None) or utc_timestamp()
    recommendation = recommend(
        evaluations,
        options,
        evidence_bundle,
        memory_bundle,
        user_state=user_state,
        llm=llm,
        anchor_now_iso=anchor,
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
        original_user_input=original_user_input,
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
        # Vector memory is written only when an outcome is recorded (see
        # ``apply_outcome_to_memory``), not here — aligns with "write on outcome" lifecycle.
    return trace


def iter_pipeline_events(
    ctx: PipelineContext,
    raw_input: str,
    *,
    decision_id: str | None = None,
    timestamp: str | None = None,
    persist_trace: bool = True,
    anchor_now_iso: str | None = None,
    clarification_answers: dict[str, str] | None = None,
    save_clarification_to_profile: bool = False,
    preserve_raw_input: bool = False,
) -> Iterator[dict[str, Any]]:
    """Yield meta, partial trace fragments per stage, then ``complete`` (SSE)."""
    settings = ctx.settings or load_settings()
    did = decision_id or str(uuid.uuid4())
    ts = timestamp or utc_timestamp()
    anchor = (anchor_now_iso.strip() if anchor_now_iso else None) or utc_timestamp()

    yield {"event": "meta", "decision_id": did, "timestamp": ts}

    yield {"event": "stage", "stage": "enhance"}
    profile = load_user_profile(settings)
    user_raw = raw_input.strip()
    effective = merge_clarification_answers(user_raw, clarification_answers)
    if preserve_raw_input:
        original, enhanced = user_raw, user_raw
    else:
        original, enhanced = prepare_decision_text(
            effective,
            ctx.llm,
            profile=profile,
            original_override=user_raw,
        )
    yield {
        "event": "partial",
        "stage": "enhance",
        "data": {"original_user_input": original, "enhanced_preview": enhanced},
    }

    yield {"event": "stage", "stage": "perceive"}
    user_state = build_user_state(enhanced, ctx.llm, profile=profile)
    user_state = merge_profile_into_user_state(user_state, profile)
    yield {
        "event": "partial",
        "stage": "perceive",
        "data": {"user_state": user_state.model_dump(mode="json")},
    }

    yield {"event": "stage", "stage": "retrieve"}
    memory_bundle, evidence_bundle = retrieve_bundles_parallel(user_state, ctx)
    yield {
        "event": "partial",
        "stage": "retrieve",
        "data": {
            "memory": memory_bundle.model_dump(mode="json"),
            "evidence": evidence_bundle.model_dump(mode="json"),
        },
    }

    yield {"event": "stage", "stage": "infer"}
    rationality, options = step_infer(user_state, memory_bundle, evidence_bundle, ctx.llm)
    yield {
        "event": "partial",
        "stage": "infer",
        "data": {
            "rationality": rationality.model_dump(mode="json"),
            "options": [o.model_dump(mode="json") for o in options],
        },
    }

    yield {"event": "stage", "stage": "simulate"}
    futures = simulate_futures(options, user_state, evidence_bundle, ctx.llm, memory_bundle)
    yield {
        "event": "partial",
        "stage": "simulate",
        "data": {"futures": [f.model_dump(mode="json") for f in futures]},
    }

    yield {"event": "stage", "stage": "evaluate"}
    evaluations = evaluate_options(futures, user_state, ctx.llm)
    yield {
        "event": "partial",
        "stage": "evaluate",
        "data": {"evaluations": [e.model_dump(mode="json") for e in evaluations]},
    }

    yield {"event": "stage", "stage": "finalize"}
    trace = finalize_trace(
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
        user_memory=ctx.user_memory,
        original_user_input=original,
        anchor_now_iso=anchor,
    )
    if save_clarification_to_profile and clarification_answers:
        p = append_clarification_to_profile(load_user_profile(settings), clarification_answers)
        save_user_profile(p, settings=settings)
    yield {"event": "complete", "trace": trace.model_dump(mode="json")}


def run_pipeline(
    ctx: PipelineContext,
    raw_input: str,
    *,
    decision_id: str | None = None,
    persist_trace: bool = True,
    anchor_now_iso: str | None = None,
    clarification_answers: dict[str, str] | None = None,
    save_clarification_to_profile: bool = False,
    preserve_raw_input: bool = False,
) -> DecisionTrace:
    """Execute the full RIS stack and return a ``DecisionTrace``; optionally save JSON under ``data/traces/``."""
    settings = ctx.settings or load_settings()
    did = decision_id or str(uuid.uuid4())
    ts = utc_timestamp()
    anchor = (anchor_now_iso.strip() if anchor_now_iso else None) or utc_timestamp()

    profile = load_user_profile(settings)
    user_raw = raw_input.strip()
    effective = merge_clarification_answers(user_raw, clarification_answers)
    if preserve_raw_input:
        original, enhanced = user_raw, user_raw
    else:
        original, enhanced = prepare_decision_text(
            effective,
            ctx.llm,
            profile=profile,
            original_override=user_raw,
        )
    user_state = build_user_state(enhanced, ctx.llm, profile=profile)
    user_state = merge_profile_into_user_state(user_state, profile)
    memory_bundle, evidence_bundle = retrieve_bundles_parallel(user_state, ctx)

    rationality, options = step_infer(user_state, memory_bundle, evidence_bundle, ctx.llm)

    futures = simulate_futures(options, user_state, evidence_bundle, ctx.llm, memory_bundle)
    evaluations = evaluate_options(futures, user_state, ctx.llm)

    trace = finalize_trace(
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
        user_memory=ctx.user_memory,
        original_user_input=original,
        anchor_now_iso=anchor,
    )
    if save_clarification_to_profile and clarification_answers:
        p = append_clarification_to_profile(load_user_profile(settings), clarification_answers)
        save_user_profile(p, settings=settings)
    return trace
