"""Option generation from user context + memory + evidence."""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel

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
            out = llm.structured_predict(OptionSet, prompt)
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
