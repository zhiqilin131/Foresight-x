"""Tests for option evaluation."""

from __future__ import annotations

from typing import Any

from foresight_x.schemas import (
    OptionEvaluation,
    Reversibility,
    Scenario,
    SimulatedFuture,
    TimePressure,
    UserState,
)
from foresight_x.simulation.evaluator import evaluate_options


class FakeLLM:
    def __init__(self, response: Any, *, raise_error: bool = False) -> None:
        self.response = response
        self.raise_error = raise_error

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        if self.raise_error:
            raise RuntimeError("LLM unavailable")
        return self.response


def _state() -> UserState:
    return UserState(
        raw_input="x",
        goals=["a", "b"],
        time_pressure=TimePressure.LOW,
        stress_level=3,
        workload=4,
        current_behavior="calm",
        decision_type="career",
        reversibility=Reversibility.REVERSIBLE,
    )


def _future(oid: str) -> SimulatedFuture:
    return SimulatedFuture(
        option_id=oid,
        time_horizon="3 months",
        scenarios=[
            Scenario(label="best", trajectory="good", probability=0.25, key_drivers=["x"]),
            Scenario(label="base", trajectory="ok", probability=0.5, key_drivers=["y"]),
            Scenario(label="worst", trajectory="bad", probability=0.25, key_drivers=["z"]),
        ],
    )


def test_evaluate_options_heuristic() -> None:
    futures = [_future("a"), _future("b")]
    evs = evaluate_options(futures, _state(), llm=None)
    assert len(evs) == 2
    for e in evs:
        assert e.option_id in ("a", "b")
        assert 0 <= e.expected_value_score <= 10
        assert e.rationale


def test_evaluate_options_llm_path() -> None:
    fut = _future("only")
    llm_ev = OptionEvaluation(
        option_id="only",
        expected_value_score=7.0,
        risk_score=4.0,
        regret_score=3.0,
        uncertainty_score=5.0,
        goal_alignment_score=8.0,
        rationale="LLM rationale",
    )
    evs = evaluate_options([fut], _state(), llm=FakeLLM(llm_ev))
    assert len(evs) == 1
    assert evs[0].rationale == "LLM rationale"
    assert evs[0].expected_value_score == 7.0


def test_evaluate_options_llm_fixes_option_id() -> None:
    fut = _future("correct_id")
    wrong = OptionEvaluation(
        option_id="wrong",
        expected_value_score=6.0,
        risk_score=5.0,
        regret_score=5.0,
        uncertainty_score=5.0,
        goal_alignment_score=6.0,
        rationale="x",
    )
    evs = evaluate_options([fut], _state(), llm=FakeLLM(wrong))
    assert evs[0].option_id == "correct_id"


def test_evaluate_options_llm_fallback() -> None:
    fut = _future("z")
    evs = evaluate_options([fut], _state(), llm=FakeLLM(None, raise_error=True))
    assert evs[0].option_id == "z"
