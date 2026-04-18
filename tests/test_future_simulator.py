"""Tests for future simulation."""

from __future__ import annotations

from typing import Any

from foresight_x.schemas import EvidenceBundle, Fact, Option, Reversibility, TimePressure, UserState
from foresight_x.simulation.future_simulator import simulate_futures


class FakeLLM:
    def __init__(self, responses: list[Any] | None = None, *, raise_error: bool = False) -> None:
        self.responses = responses or []
        self.raise_error = raise_error
        self.calls = 0

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        self.calls += 1
        if self.raise_error:
            raise RuntimeError("LLM unavailable")
        if self.responses:
            return self.responses[self.calls - 1]
        raise RuntimeError("no response")


def _state() -> UserState:
    return UserState(
        raw_input="Career choice under deadline.",
        goals=["growth"],
        time_pressure=TimePressure.MEDIUM,
        stress_level=5,
        workload=5,
        current_behavior="thinking",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
    )


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(
        facts=[Fact(text="Industry demand is steady.", confidence=0.7)],
        base_rates=[],
        recent_events=[],
    )


def _options() -> list[Option]:
    return [
        Option(
            option_id="o1",
            name="Accept",
            description="Take the offer.",
            key_assumptions=["fit"],
            cost_of_reversal="medium",
        ),
        Option(
            option_id="o2",
            name="Negotiate",
            description="Ask for changes.",
            key_assumptions=["room to negotiate"],
            cost_of_reversal="low",
        ),
    ]


def test_simulate_futures_fallback_three_scenarios_sum_to_one() -> None:
    futures = simulate_futures(_options(), _state(), _evidence(), llm=None)
    assert len(futures) == 2
    for fut in futures:
        assert fut.option_id in ("o1", "o2")
        assert len(fut.scenarios) == 3
        total = sum(s.probability for s in fut.scenarios)
        assert abs(total - 1.0) < 1e-6
        labels = {s.label for s in fut.scenarios}
        assert labels == {"best", "base", "worst"}


def test_simulate_futures_llm_normalizes_probabilities() -> None:
    opt = _options()[0]
    bad = {
        "option_id": opt.option_id,
        "time_horizon": "6 months",
        "scenarios": [
            {"label": "best", "trajectory": "up", "probability": 0.1, "key_drivers": ["a"]},
            {"label": "base", "trajectory": "flat", "probability": 0.1, "key_drivers": ["b"]},
            {"label": "worst", "trajectory": "down", "probability": 0.1, "key_drivers": ["c"]},
        ],
    }
    llm = FakeLLM([bad])
    out = simulate_futures([opt], _state(), _evidence(), llm=llm)
    assert len(out) == 1
    assert abs(sum(s.probability for s in out[0].scenarios) - 1.0) < 0.06


def test_simulate_futures_llm_failure_uses_fallback() -> None:
    llm = FakeLLM(raise_error=True)
    out = simulate_futures(_options(), _state(), _evidence(), llm=llm)
    assert len(out) == 2
    assert all(len(f.scenarios) == 3 for f in out)
