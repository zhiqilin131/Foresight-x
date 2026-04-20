"""Rewrite vague decision prompts into clearer questions (optional LLM)."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from foresight_x.schemas import UserProfile
from foresight_x.structured_predict import structured_predict


class StructuredPredictLLM(Protocol):
    def structured_predict(self, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
        ...


class EnhancedDecisionText(BaseModel):
    """Structured output for query clarification."""

    enhanced_question: str = Field(
        description=(
            "Exactly ONE decision question string for downstream analysis. "
            "Preserve the user's information content: entities, quantities, constraints, and trade-offs they relied on "
            "to pose the decision. Do not replace a detailed message with a short generic question. "
            "Do not refuse, sanitize topics, or substitute a bland paraphrase for their framing."
        )
    )


# If the model returns safety refusals or an over-short rewrite, we keep the user's text.
_REFUSAL_HINTS: tuple[str, ...] = (
    "i can't assist",
    "i cannot assist",
    "can't help with",
    "cannot help with",
    "i'm not able to",
    "i am not able to",
    "unable to comply",
    "as an ai language model",
    "as a language model",
    "i don't have the ability",
    "cannot provide guidance",
    "i cannot provide",
    "refuse to",
    "inappropriate content",
    "harmful content",
)


def _looks_like_refusal(text: str) -> bool:
    t = text.lower()
    return any(h in t for h in _REFUSAL_HINTS)


def _likely_stripped_too_much(body: str, enhanced: str) -> bool:
    """Heuristic: long detailed message vs very short rewrite — probably over-sanitized."""
    if len(body) < 160:
        return False
    e = enhanced.strip()
    if len(e) >= len(body) * 0.45:
        return False
    return len(e) < 100 and len(body) > 280


def _enhancement_drops_too_much_substance(body: str, enhanced: str) -> bool:
    """Reject rewrites that are much shorter than the user text — models often drop decision-relevant specifics."""
    b = body.strip()
    e = (enhanced or "").strip()
    if not e:
        return True
    lb, le = len(b), len(e)
    if lb < 150:
        return False
    # For medium+ prompts, require roughly half the length (after strip) so key specifics survive.
    min_acceptable = max(140, int(lb * 0.50))
    if le < min_acceptable:
        return True
    # Very long narratives: also reject if the model collapsed to a single short paragraph.
    if lb >= 650 and le < int(lb * 0.45):
        return True
    return False


def _pick_enhanced_or_raw(body: str, enhanced: str) -> str:
    e = (enhanced or "").strip()
    if not e:
        return body
    if _looks_like_refusal(e):
        return body
    if _likely_stripped_too_much(body, e):
        return body
    if _enhancement_drops_too_much_substance(body, e):
        return body
    return e


def prepare_decision_text(
    raw: str,
    llm: StructuredPredictLLM | None,
    *,
    profile: UserProfile | None = None,
    original_override: str | None = None,
) -> tuple[str, str]:
    """Return (original_text_for_trace, text_used_for_pipeline).

    ``original_override`` is the user's verbatim message when ``raw`` includes appended clarification.
    """
    original = (original_override if original_override is not None else raw).strip()
    if not raw.strip() or llm is None:
        return original, raw.strip() or original
    prof = ""
    if profile:
        bits: list[str] = []
        pp = profile.profile_channel_priority_texts()
        if pp:
            bits.append("User-authored priorities (Profile only, authoritative): " + "; ".join(pp[:12]))
        clar = profile.clarification_priority_texts()
        if clar:
            bits.append("Saved clarification choices: " + "; ".join(clar[:12]))
        if profile.memory_facts:
            from foresight_x.profile.memory_structured import active_memory_facts, format_memory_fact_prompt_line

            fact_lines = [
                format_memory_fact_prompt_line(f) for f in active_memory_facts(list(profile.memory_facts))[:20]
            ]
            bits.append("Structured memory facts: " + " | ".join(fact_lines))
        if profile.inferred_priorities:
            bits.append(
                "Legacy system-inferred lines (may be revised): "
                + "; ".join(profile.inferred_priorities[:12])
            )
        if profile.constraints:
            bits.append("Known constraints (from profile): " + "; ".join(profile.constraints[:12]))
        if bits:
            prof = "\n".join(bits) + "\n\n"
    body = raw.strip()
    prompt = (
        "You are a technical editor for a private decision-support tool (Foresight-X).\n"
        "Output ONE decision question string that downstream analysis will use as its sole description of the problem.\n"
        "Fidelity beats brevity: if you remove details the user treated as part of the decision, the analysis will be "
        "wrong.\n\n"
        "General principles (any domain):\n"
        "- **Information preservation**: Keep the same level of specificity the user supplied—identifiers they used, "
        "numbers, time bounds, options, and constraints. Do not summarize rich input into a thin generic question.\n"
        "- **Proportional length**: High-detail messages should yield high-detail questions (after removing stutter, "
        "typos, and exact duplicate lines). Do not merge distinct points into one vague phrase.\n"
        "- **When to edit lightly**: If the text is already a clear question with sufficient context, change at most "
        "grammar, spelling, and punctuation.\n"
        "- **When to reshape more**: If the text is rambling or unclear, you may reorder and clarify, but every "
        "substantive claim the user made about the situation must remain available to the reader—nothing important "
        "dropped for tone or concision.\n"
        "- **No invention**: Do not add budgets, deadlines, preferences, or facts not in the message or profile below.\n"
        "- **No refusal or softening**: Do not refuse, moralize, sanitize away the user's topic, or add disclaimers. "
        "Sensitive or socially loaded content is still a valid decision context if the user raised it.\n"
        "- **Output format**: Single question string only—no preamble, no bullets, no labels.\n\n"
        f"{prof}"
        "USER MESSAGE:\n---\n"
        f"{body}\n"
        "---\n\n"
        "Return JSON matching the schema: one field `enhanced_question` with ONLY the final question text."
    )
    try:
        out = structured_predict(llm, EnhancedDecisionText, prompt)
        if isinstance(out, EnhancedDecisionText):
            text = out.enhanced_question.strip()
        else:
            text = EnhancedDecisionText.model_validate(out).enhanced_question.strip()
        final_text = _pick_enhanced_or_raw(body, text)
        return original, final_text
    except Exception:
        return original, body
