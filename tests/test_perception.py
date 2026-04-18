"""Tests for Perception layer."""

from __future__ import annotations

from typing import Any

from foresight_x.perception.layer import build_user_state
from foresight_x.schemas import Reversibility, TimePressure, UserState


class FakeLLM:
    def __init__(self, response: Any, *, raise_error: bool = False) -> None:
        self.response = response
        self.raise_error = raise_error
        self.prompts: list[str] = []

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        self.prompts.append(prompt)
        if self.raise_error:
            raise RuntimeError("LLM unavailable")
        return self.response


def test_build_user_state_llm_path() -> None:
    expected = UserState(
        raw_input="Offer deadline is Friday and I feel anxious.",
        goals=["maximize growth", "reduce regret"],
        time_pressure=TimePressure.HIGH,
        stress_level=8,
        workload=7,
        current_behavior="rushed",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
        deadline_hint="Friday",
    )
    llm = FakeLLM(expected)

    out = build_user_state(expected.raw_input, llm)
    assert out == expected
    assert llm.prompts and "Perception module" in llm.prompts[0]


def test_build_user_state_fallback_when_llm_fails() -> None:
    raw = "This is urgent, deadline tomorrow, I am stressed and overwhelmed."
    llm = FakeLLM({}, raise_error=True)

    out = build_user_state(raw, llm)
    assert out.raw_input == raw
    assert out.time_pressure == TimePressure.HIGH
    assert out.stress_level >= 8
