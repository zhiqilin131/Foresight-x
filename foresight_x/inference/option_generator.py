"""Option generation from user context + memory + evidence."""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel

from foresight_x.structured_predict import structured_predict
from foresight_x.prompts.option_generator import option_generator_prompt
from foresight_x.schemas import EvidenceBundle, MemoryBundle, Option, UserState


class StructuredPredictLLM(Protocol):
    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


class OptionSet(BaseModel):
    options: list[Option]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _dedupe_options(options: list[Option]) -> list[Option]:
    out: list[Option] = []
    seen: set[str] = set()
    for opt in options:
        key = f"{_norm(opt.name)}|{_norm(opt.description)}"
        if key in seen:
            continue
        seen.add(key)
        out.append(opt)
    return out


def _fallback_options(user_state: UserState) -> list[Option]:
    text = user_state.raw_input.lower()
    if any(k in text for k in ("cancer", "tumor", "diagnosis", "medical", "hospital")):
        return [
            Option(
                option_id="opt_urgent_clinical_team",
                name="Contact your clinical care team immediately",
                description=(
                    "Reach out to an oncologist/doctor now to confirm diagnosis details and urgent next steps."
                ),
                key_assumptions=["Clinical guidance is the primary source for medical decisions"],
                cost_of_reversal="low",
            ),
            Option(
                option_id="opt_second_opinion",
                name="Get a rapid second opinion",
                description=(
                    "Request pathology review and a second specialist opinion before committing to treatment."
                ),
                key_assumptions=["A second opinion can materially change treatment choices"],
                cost_of_reversal="low",
            ),
            Option(
                option_id="opt_support_plan",
                name="Build a support and logistics plan",
                description=(
                    "Organize insurance, family support, and treatment logistics in parallel with clinical planning."
                ),
                key_assumptions=["Execution support improves adherence and outcomes"],
                cost_of_reversal="low",
            ),
        ]
    if any(k in text for k in ("job", "offer", "career", "salary", "interview")):
        return [
            Option(
                option_id="opt_negotiate_offer",
                name="Negotiate key terms before deciding",
                description="Clarify compensation, role scope, and growth path to reduce ambiguity.",
                key_assumptions=["Employer is open to negotiation"],
                cost_of_reversal="low",
            ),
            Option(
                option_id="opt_accept_best_fit",
                name="Accept the best-fit offer now",
                description="Choose the offer with strongest long-term fit across your criteria.",
                key_assumptions=["You already have enough evidence on fit and risks"],
                cost_of_reversal="medium",
            ),
            Option(
                option_id="opt_compare_with_scorecard",
                name="Run a weighted comparison scorecard",
                description="Score each offer against criteria and make a fixed-time decision.",
                key_assumptions=["A structured rubric improves decision quality"],
                cost_of_reversal="low",
            ),
        ]
    return [
        Option(
            option_id="opt_ask_extension",
            name="Ask for more time",
            description="Request a short extension to reduce rushed decisions.",
            key_assumptions=["Counterparty can extend the deadline"],
            cost_of_reversal="low",
        ),
        Option(
            option_id="opt_commit_now",
            name="Commit now",
            description="Choose the strongest currently available path and execute immediately.",
            key_assumptions=["Current information is sufficient"],
            cost_of_reversal="medium",
        ),
        Option(
            option_id="opt_information_sprint",
            name="Run a 48-hour information sprint",
            description=(
                "Collect missing evidence tied to top goals, then decide with a fixed cutoff."
            ),
            key_assumptions=["A short delay meaningfully improves certainty"],
            cost_of_reversal="low",
        ),
    ]


def _ensure_novel_option(options: list[Option], raw_input: str) -> list[Option]:
    text = raw_input.lower()
    if any(_norm(f"{o.name} {o.description}") not in text for o in options):
        return options
    options.append(
        Option(
            option_id="opt_pause_reframe",
            name="Pause and reframe criteria",
            description="Define explicit decision criteria before selecting any option.",
            key_assumptions=["Current framing may be incomplete"],
            cost_of_reversal="low",
        )
    )
    return options


def generate_options(
    user_state: UserState,
    memory: MemoryBundle,
    evidence: EvidenceBundle,
    llm: StructuredPredictLLM | None = None,
    *,
    min_options: int = 2,
    max_options: int = 4,
) -> list[Option]:
    """Generate distinct options, with robust fallbacks and guardrails."""
    candidates: list[Option]
    if llm is None:
        candidates = _fallback_options(user_state)
    else:
        prompt = option_generator_prompt(user_state, memory, evidence)
        try:
            out = structured_predict(llm, OptionSet, prompt)
            if isinstance(out, OptionSet):
                candidates = out.options
            elif isinstance(out, list):
                candidates = [o if isinstance(o, Option) else Option.model_validate(o) for o in out]
            else:
                candidates = OptionSet.model_validate(out).options
        except Exception:
            candidates = _fallback_options(user_state)

    options = _dedupe_options(candidates)
    options = _ensure_novel_option(options, user_state.raw_input)
    if len(options) < min_options:
        options.extend(_fallback_options(user_state))
        options = _dedupe_options(options)
    return options[:max_options]
