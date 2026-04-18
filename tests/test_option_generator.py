"""Tests for option generation."""

from __future__ import annotations

from typing import Any

from foresight_x.inference.option_generator import generate_options
from foresight_x.schemas import EvidenceBundle, Fact, MemoryBundle, Option, Reversibility, TimePressure, UserState


class FakeLLM:
    def __init__(self, response: Any, *, raise_error: bool = False) -> None:
        self.response = response
        self.raise_error = raise_error

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        if self.raise_error:
            raise RuntimeError("no model")
        return self.response


def _state(raw_input: str) -> UserState:
    return UserState(
        raw_input=raw_input,
        goals=["maximize upside", "minimize regret"],
        time_pressure=TimePressure.HIGH,
        stress_level=7,
        workload=6,
        current_behavior="uncertain",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
        deadline_hint="Friday",
    )


def _memory() -> MemoryBundle:
    return MemoryBundle(similar_past_decisions=[], behavioral_patterns=[], prior_outcomes_summary="")


def _evidence() -> EvidenceBundle:
    return EvidenceBundle(
        facts=[Fact(text="Company X has strong mentorship program.", confidence=0.8)],
        base_rates=[],
        recent_events=[],
    )


def test_generate_options_from_llm_and_dedupe() -> None:
    llm_options = [
        Option(
            option_id="a",
            name="Ask for extension",
            description="Request one-week extension.",
            key_assumptions=["they allow extension"],
            cost_of_reversal="low",
        ),
        Option(
            option_id="b",
            name="Ask for extension",
            description="Request one-week extension.",
            key_assumptions=["duplicate"],
            cost_of_reversal="low",
        ),
        Option(
            option_id="c",
            name="Accept now",
            description="Accept current offer now.",
            key_assumptions=["offer is strongest"],
            cost_of_reversal="medium",
        ),
    ]
    out = generate_options(
        _state("I can accept now or ask for extension."),
        _memory(),
        _evidence(),
        llm=FakeLLM(llm_options),
    )
    assert 2 <= len(out) <= 4
    names = [o.name for o in out]
    assert names.count("Ask for extension") == 1


def test_generate_options_adds_novel_option_if_needed() -> None:
    raw = "Accept now. Accept now."
    llm_options = [
        Option(
            option_id="x",
            name="Accept now",
            description="Accept now.",
            key_assumptions=["already decided"],
            cost_of_reversal="high",
        )
    ]
    out = generate_options(_state(raw), _memory(), _evidence(), llm=FakeLLM(llm_options))
    assert len(out) >= 2
    assert any("reframe" in o.name.lower() or "time" in o.name.lower() for o in out)


def test_generate_options_fallback_when_llm_fails() -> None:
    out = generate_options(
        _state("I need help deciding quickly."),
        _memory(),
        _evidence(),
        llm=FakeLLM([], raise_error=True),
    )
    assert 2 <= len(out) <= 4
