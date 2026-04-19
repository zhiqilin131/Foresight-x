"""Perception module: raw user text -> UserState."""

from __future__ import annotations

from typing import Any, Protocol

from foresight_x.structured_predict import structured_predict
from foresight_x.prompts.perception import perception_prompt
from foresight_x.schemas import Reversibility, TimePressure, UserState


class StructuredPredictLLM(Protocol):
    """Protocol for LLMs that support Pydantic structured prediction."""

    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


def _heuristic_user_state(raw_input: str) -> UserState:
    text = raw_input.lower()
    high_pressure_markers = ("urgent", "asap", "deadline", "friday", "tomorrow", "today")
    stress_markers = ("anxious", "stressed", "panic", "overwhelmed", "worried")

    time_pressure = (
        TimePressure.HIGH
        if any(tok in text for tok in high_pressure_markers)
        else TimePressure.MEDIUM
    )
    stress_level = 8 if any(tok in text for tok in stress_markers) else 5

    reversibility = Reversibility.PARTIAL
    if "irreversible" in text:
        reversibility = Reversibility.IRREVERSIBLE
    if "reversible" in text:
        reversibility = Reversibility.REVERSIBLE

    return UserState(
        raw_input=raw_input,
        goals=["make a high-quality decision"],
        time_pressure=time_pressure,
        stress_level=stress_level,
        workload=5,
        current_behavior="seeking guidance",
        decision_type="general",
        reversibility=reversibility,
        deadline_hint="unknown" if time_pressure == TimePressure.HIGH else None,
    )


def build_user_state(raw_input: str, llm: StructuredPredictLLM | None = None) -> UserState:
    """Return `UserState` using structured prediction with a robust fallback.

    If ``llm`` is ``None``, uses fast heuristics only (orchestration / tests without API keys).
    """
    if llm is None:
        return _heuristic_user_state(raw_input)
    prompt = perception_prompt(raw_input)
    try:
        out = structured_predict(llm, UserState, prompt)
        if isinstance(out, UserState):
            return out
        return UserState.model_validate(out)
    except Exception:
        return _heuristic_user_state(raw_input)
