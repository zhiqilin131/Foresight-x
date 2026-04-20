"""Optional pre-run clarification: multiple-choice questions when input is too vague."""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from foresight_x.schemas import UserProfile
from foresight_x.structured_predict import structured_predict


class StructuredPredictLLM(Protocol):
    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


class ClarifyOption(BaseModel):
    value: str = Field(description="Stable id for the answer, e.g. budget_tight")
    label: str = Field(description="Short human-readable choice")


class ClarifyQuestion(BaseModel):
    id: str = Field(description="snake_case id, e.g. budget_sensitivity")
    prompt: str = Field(description="One sentence question")
    options: list[ClarifyOption] = Field(min_length=2, max_length=6)


SkipReason = Literal["none", "no_input", "no_llm", "not_needed", "no_questions", "error"]


class ClarifyGateResult(BaseModel):
    need_clarification: bool = Field(
        description="True only if the message is too vague to analyze without guessing priorities."
    )
    questions: list[ClarifyQuestion] = Field(default_factory=list)
    note: str = Field(default="", description="Optional hint for the UI")
    skip_reason: SkipReason = Field(
        default="none",
        description=(
            "When need_clarification is false: why the multiple-choice modal was not shown. "
            "'not_needed' means the model judged the message specific enough."
        ),
    )


def merge_clarification_answers(raw: str, answers: dict[str, str] | None) -> str:
    """Append structured answers to the raw prompt for downstream perception."""
    base = raw.strip()
    if not answers:
        return base
    lines = [base, "", "User clarification (structured):"]
    for qid, val in answers.items():
        lines.append(f"- {qid}: {val}")
    return "\n".join(lines)


def run_clarify_gate(
    raw: str,
    llm: StructuredPredictLLM | None,
    *,
    profile: UserProfile | None = None,
) -> ClarifyGateResult:
    """Ask the LLM whether we need 1–2 multiple-choice questions before the main pipeline."""
    text = raw.strip()
    if not text:
        return ClarifyGateResult(need_clarification=False, skip_reason="no_input")
    if llm is None:
        return ClarifyGateResult(need_clarification=False, skip_reason="no_llm")

    prof_bits = ""
    if profile:
        pp = profile.profile_channel_priority_texts()
        if pp:
            prof_bits += f"User-authored priorities (authoritative): {pp}\n"
        clar = profile.clarification_priority_texts()
        if clar:
            prof_bits += f"Saved clarification choices: {clar}\n"
        if profile.memory_facts:
            from foresight_x.profile.memory_structured import active_memory_facts, format_memory_fact_prompt_line

            prof_bits += "Structured memory facts: " + " | ".join(
                format_memory_fact_prompt_line(f) for f in active_memory_facts(list(profile.memory_facts))[:16]
            ) + "\n"
        if profile.inferred_priorities:
            prof_bits += (
                f"Legacy system-inferred lines (lower weight): {profile.inferred_priorities}\n"
            )
        if profile.constraints:
            prof_bits += f"Known constraints: {profile.constraints}\n"

    prompt = (
        "You help a decision agent decide if the user's message needs extra multiple-choice input.\n"
        "Set need_clarification=true ONLY when:\n"
        "- the decision is critically underspecified (e.g. trade-offs depend on budget, timeline, or risk tolerance not mentioned), AND\n"
        "- those dimensions cannot be inferred from the text or from the profile snippet below.\n"
        "If the message is short but clear enough (e.g. pick A vs B), need_clarification=false.\n"
        "When need_clarification=true, add at most 2 questions with 2–4 options each. "
        "Questions must not repeat facts already in the profile. "
        "Do NOT ask about things already stated in the user message.\n\n"
        f"{prof_bits}\nUSER MESSAGE:\n---\n{text}\n---\n"
    )
    try:
        out = structured_predict(llm, ClarifyGateResult, prompt)
        res = out if isinstance(out, ClarifyGateResult) else ClarifyGateResult.model_validate(out)
        if not res.need_clarification:
            return ClarifyGateResult(need_clarification=False, skip_reason="not_needed")
        if not res.questions:
            return ClarifyGateResult(need_clarification=False, skip_reason="no_questions")
        return ClarifyGateResult(
            need_clarification=True,
            questions=res.questions[:2],
            note=res.note[:500] if res.note else "",
            skip_reason="none",
        )
    except Exception:
        return ClarifyGateResult(need_clarification=False, skip_reason="error")
