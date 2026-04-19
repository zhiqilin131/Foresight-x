"""Post-hoc reflection on a full DecisionTrace."""

from __future__ import annotations

from typing import Any, Protocol

from foresight_x.structured_predict import structured_predict
from foresight_x.prompts.reflector import reflector_prompt
from foresight_x.schemas import DecisionTrace, Reflection


class StructuredPredictLLM(Protocol):
    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


def _fallback_reflection() -> Reflection:
    return Reflection(
        possible_errors=[
            "Underestimated tail risk in worst-case branch",
            "Overweighted recent stress vs. stable preferences",
        ],
        uncertainty_sources=[
            "Scenario probability estimates",
            "Sparse or stale evidence",
        ],
        model_limitations=[
            "Cannot verify employer claims or market moves in real time",
        ],
        information_gaps=[
            "Exact negotiation leeway",
            "Hidden constraints from other stakeholders",
        ],
        self_improvement_signal="When evidence is thin, add targeted retrieval before commitment.",
    )


def reflect(trace: DecisionTrace, llm: StructuredPredictLLM | None = None) -> Reflection:
    """Structured critique of the trace for Harness / improvement loop."""
    if llm is None:
        return _fallback_reflection()
    prompt = reflector_prompt(trace)
    try:
        raw = structured_predict(llm, Reflection, prompt)
        return raw if isinstance(raw, Reflection) else Reflection.model_validate(raw)
    except Exception:
        return _fallback_reflection()
