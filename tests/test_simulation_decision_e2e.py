"""Phase 3 integration: simulation + decision produce a valid DecisionTrace."""

from __future__ import annotations

from foresight_x.decision.recommender import recommend
from foresight_x.decision.reflector import reflect
from foresight_x.schemas import (
    DecisionTrace,
    EvidenceBundle,
    Fact,
    MemoryBundle,
    Option,
    RationalityReport,
    Reversibility,
    Reflection,
    TimePressure,
    UserState,
)
from foresight_x.simulation.evaluator import evaluate_options
from foresight_x.simulation.future_simulator import simulate_futures


def test_pipeline_yields_valid_decision_trace() -> None:
    state = UserState(
        raw_input="Should I take the remote role?",
        goals=["career growth", "work-life balance"],
        time_pressure=TimePressure.HIGH,
        stress_level=7,
        workload=6,
        current_behavior="ruminating",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
        deadline_hint="Friday",
    )
    memory = MemoryBundle(
        similar_past_decisions=[],
        behavioral_patterns=["avoids conflict"],
        prior_outcomes_summary="Past pivots worked when planned.",
    )
    evidence = EvidenceBundle(
        facts=[Fact(text="Remote roles often widen talent pools.", confidence=0.75)],
        base_rates=[],
        recent_events=[],
    )
    rationality = RationalityReport(
        is_rational_state=False,
        detected_biases=["availability"],
        confidence=0.7,
        recommended_slowdowns=["sleep on it"],
    )
    options = [
        Option(
            option_id="opt_accept",
            name="Accept remote offer",
            description="Start in two weeks.",
            key_assumptions=["manager support"],
            cost_of_reversal="medium",
        ),
        Option(
            option_id="opt_counter",
            name="Counter on hybrid",
            description="Negotiate hybrid schedule.",
            key_assumptions=["flexibility exists"],
            cost_of_reversal="low",
        ),
    ]

    futures = simulate_futures(options, state, evidence, llm=None)
    evaluations = evaluate_options(futures, state, llm=None)
    recommendation = recommend(evaluations, options, evidence, memory, llm=None)

    placeholder = Reflection(
        possible_errors=["pending"],
        uncertainty_sources=["pending"],
        model_limitations=["pending"],
        information_gaps=["pending"],
        self_improvement_signal="pending",
    )
    trace = DecisionTrace(
        decision_id="e2e-phase3",
        timestamp="2026-04-18T12:00:00Z",
        user_state=state,
        memory=memory,
        evidence=evidence,
        rationality=rationality,
        options=options,
        futures=futures,
        evaluations=evaluations,
        recommendation=recommendation,
        reflection=placeholder,
    )
    final_refl = reflect(trace, llm=None)
    trace_final = trace.model_copy(update={"reflection": final_refl})

    round_trip = DecisionTrace.model_validate(trace_final.model_dump())
    assert round_trip.decision_id == "e2e-phase3"
    assert round_trip.recommendation.chosen_option_id in {o.option_id for o in options}
    assert not round_trip.reflection.possible_errors[0].startswith("pending")
