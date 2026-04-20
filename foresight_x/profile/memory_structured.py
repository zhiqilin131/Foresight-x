"""Format, keys, and conflict rules for typed profile memory (no domain-specific regex lists)."""

from __future__ import annotations

import re

from foresight_x.schemas import ProfileMemoryFact

_WS = re.compile(r"\s+")

# Predicates where multiple concurrent objects per subject are normal (edges accumulate).
MULTI_OBJECT_PREDICATES: frozenset[str] = frozenset(
    {
        "friend_of",
        "knows",
        "colleague_of",
        "classmate_of",
        "related_to",
        "interested_in",
        "member_of",
    }
)


def normalize_token(s: str) -> str:
    return _WS.sub(" ", (s or "").strip()).lower()


def normalize_predicate(pred: str) -> str:
    p = (pred or "").strip().lower().replace(" ", "_")
    return p[:200]


def triple_key(fact: ProfileMemoryFact) -> tuple[str, str, str]:
    """Identity for exact duplicate detection (active rows)."""
    if not (fact.predicate or "").strip():
        return ("legacy", normalize_token(fact.text), str(fact.category.value))
    return (
        normalize_token(fact.subject_ref or "user"),
        normalize_predicate(fact.predicate),
        normalize_token(fact.object_value),
    )


def single_slot_predicate(pred: str) -> bool:
    """If True, at most one active object per (subject, predicate) — new fact deprecates old."""
    p = normalize_predicate(pred)
    if not p:
        return False
    return p not in MULTI_OBJECT_PREDICATES


def render_triple_line(subject_ref: str, predicate: str, object_value: str) -> str:
    subj = (subject_ref or "user").strip() or "user"
    pred = (predicate or "").strip()
    obj = (object_value or "").strip()
    if pred and obj:
        return f"{subj} {pred.replace('_', ' ')} {obj}".strip()
    return obj or pred or subj


def format_memory_fact_prompt_line(fact: ProfileMemoryFact) -> str:
    """Single line for LLM prompts (prefer typed triple when present)."""
    if (fact.predicate or "").strip() and (fact.object_value or "").strip():
        return (
            f"{fact.category.value}: "
            f"{(fact.subject_ref or 'user').strip()} | {normalize_predicate(fact.predicate)} | {fact.object_value.strip()}"
        )
    return f"{fact.category.value}: {fact.text}"


def format_stored_fact_bullet(fact: ProfileMemoryFact) -> str:
    """Line for Shadow memory block."""
    if (fact.predicate or "").strip() and (fact.object_value or "").strip():
        return (
            f"- [{fact.category.value}] {(fact.subject_ref or 'user').strip()} — "
            f"{fact.predicate} — {fact.object_value.strip()}"
        )
    return f"- [{fact.category.value}] {fact.text}"


def ensure_memory_fact_text(fact: ProfileMemoryFact) -> ProfileMemoryFact | None:
    """Ensure ``text`` is non-empty; derive from triple if needed. Returns None if unusable."""
    t = (fact.text or "").strip()
    if t:
        return fact.model_copy(update={"text": t[:500]})
    if (fact.predicate or "").strip() and (fact.object_value or "").strip():
        line = render_triple_line(fact.subject_ref, fact.predicate, fact.object_value)
        return fact.model_copy(update={"text": line[:500]})
    return None


def active_memory_facts(facts: list[ProfileMemoryFact]) -> list[ProfileMemoryFact]:
    return [f for f in facts if f.status == "active"]
