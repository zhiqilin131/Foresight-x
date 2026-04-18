"""Score options from simulated futures."""

from __future__ import annotations

from typing import Any, Protocol

from foresight_x.prompts.evaluator import evaluator_prompt
from foresight_x.schemas import OptionEvaluation, SimulatedFuture, UserState


class StructuredPredictLLM(Protocol):
    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


def _scenario_scores(future: SimulatedFuture) -> dict[str, float]:
    if not future.scenarios:
        return {"ev": 5.0, "risk": 5.0, "regret": 5.0, "unc": 5.0}
    by_label = {s.label: s for s in future.scenarios}
    best_p = by_label.get("best", future.scenarios[0]).probability
    base_p = by_label.get("base", future.scenarios[0]).probability
    worst_p = by_label.get("worst", future.scenarios[-1]).probability
    ev = best_p * 10.0 + base_p * 5.0 + worst_p * 0.0
    risk = min(10.0, worst_p * 10.0 + abs(best_p - worst_p) * 5.0)
    regret = min(10.0, worst_p * 10.0)
    unc = min(10.0, (1.0 - max(best_p, base_p, worst_p)) * 10.0)
    return {"ev": ev, "risk": risk, "regret": regret, "unc": unc}


def _heuristic_evaluation(future: SimulatedFuture, user_state: UserState) -> OptionEvaluation:
    m = _scenario_scores(future)
    ga = min(10.0, 4.0 + 6.0 * (1.0 - user_state.stress_level / 10.0))
    rationale = (
        f"Heuristic from {future.time_horizon} scenarios (best/base/worst): "
        f"EV≈{m['ev']:.1f}, tail emphasis on worst-case weight {m['regret']:.1f}."
    )
    return OptionEvaluation(
        option_id=future.option_id,
        expected_value_score=m["ev"],
        risk_score=m["risk"],
        regret_score=m["regret"],
        uncertainty_score=m["unc"],
        goal_alignment_score=ga,
        rationale=rationale,
    )


def evaluate_options(
    futures: list[SimulatedFuture],
    user_state: UserState,
    llm: StructuredPredictLLM | None = None,
) -> list[OptionEvaluation]:
    """One OptionEvaluation per SimulatedFuture; LLM overrides with structured scores."""
    evaluations: list[OptionEvaluation] = []
    for fut in futures:
        if llm is None:
            evaluations.append(_heuristic_evaluation(fut, user_state))
            continue
        prompt = evaluator_prompt(fut, user_state)
        try:
            raw = llm.structured_predict(OptionEvaluation, prompt)
            ev = raw if isinstance(raw, OptionEvaluation) else OptionEvaluation.model_validate(raw)
            if ev.option_id != fut.option_id:
                ev = ev.model_copy(update={"option_id": fut.option_id})
            evaluations.append(ev)
        except Exception:
            evaluations.append(_heuristic_evaluation(fut, user_state))
    return evaluations
