"""One turn of shadow chat: inner voice (not a therapist, not a generic assistant); updates shadow notes + memory facts."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from foresight_x.config import Settings, load_settings
from foresight_x.extraction.atomic_claims import run_atomic_claims
from foresight_x.orchestration.llm_factory import build_openai_llm
from foresight_x.profile.memory_structured import active_memory_facts, format_stored_fact_bullet, render_triple_line
from foresight_x.profile.merge import append_profile_memory_records
from foresight_x.profile.store import load_user_profile, save_user_profile
from foresight_x.schemas import MemoryFactCategory, ProfileMemoryFact
from foresight_x.shadow.decision_context import build_shadow_decision_context_block
from foresight_x.shadow.store import ShadowSelfState, load_shadow_self, merge_observation, save_shadow_self
from foresight_x.structured_predict import structured_predict


class ShadowMemoryFactDraft(BaseModel):
    category: Literal["identity", "views", "behavior", "goals", "constraints", "other"] = Field(
        description="Bucket for the fact.",
    )
    text: str = Field(
        max_length=280,
        description=(
            "ONE concrete fact (human-readable line). If subject_ref/predicate/object_value are set, "
            "text can mirror the triple in natural language."
        ),
    )
    subject_ref: str = Field(
        default="user",
        description="Entity this is about; default 'user' for first-person statements.",
    )
    predicate: str = Field(
        default="",
        description=(
            "snake_case relation (e.g. studies_at, friend_of, prefers, dating). Use open vocabulary; "
            "empty means legacy flat fact (category+text only)."
        ),
    )
    object_value: str = Field(
        default="",
        description="Object of the relation (school name, person, preference target). Empty if legacy flat.",
    )
    evidence: str = Field(
        default="",
        max_length=220,
        description="Short verbatim quote from the user's latest message supporting this fact (may be empty).",
    )


class ShadowChatTurn(BaseModel):
    reply_to_user: str = Field(
        description=(
            "Reply as their inner shadow — the part of them that finishes the sentence they avoid. "
            "Direct address (you). Same stakes and words they used. "
            "FORBIDDEN: third-person case notes ('User is…'), assistant voice, or abstract psych summaries. "
            "Not a therapist, coach, or staff member."
        )
    )
    suggest_decision_navigation: bool = Field(
        description=(
            "True only if the user is clearly asking for a concrete decision, which option to pick, "
            "or to run the Foresight / decision analysis mode."
        )
    )
    memory_facts: list[ShadowMemoryFactDraft] = Field(
        default_factory=list,
        description=(
            "0–12 concrete memory facts to store (category + short text), one distinct proposition per item. "
            "Examples: identity — 'Currently identifies as Republican'; views — 'Supports tighter immigration policy'. "
            "Skip if nothing new and concrete; never store vague rewrites of their message."
        ),
    )


def _format_transcript(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = str(m.get("role", "")).strip()
        content = str(m.get("content", "")).strip()
        if role == "system" or not content:
            continue
        label = "You" if role == "user" else "Shadow"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _coerce_category(raw: str) -> MemoryFactCategory:
    m: dict[str, MemoryFactCategory] = {
        "identity": MemoryFactCategory.IDENTITY,
        "views": MemoryFactCategory.VIEWS,
        "behavior": MemoryFactCategory.BEHAVIOR,
        "goals": MemoryFactCategory.GOALS,
        "constraints": MemoryFactCategory.CONSTRAINTS,
        "other": MemoryFactCategory.OTHER,
    }
    return m.get(str(raw).strip().lower(), MemoryFactCategory.OTHER)


def _format_profile_block(prof: Any) -> str:
    bits: list[str] = []
    p = prof.profile_channel_priority_texts()
    if p:
        bits.append("Profile priorities (user-authored): " + "; ".join(p[:20]))
    c = prof.clarification_priority_texts()
    if c:
        bits.append("Saved clarification choices: " + "; ".join(c[:20]))
    if prof.constraints:
        bits.append("Profile constraints: " + "; ".join(prof.constraints[:20]))
    if prof.values:
        bits.append("Profile values: " + "; ".join(prof.values[:20]))
    if (prof.about_me or "").strip():
        bits.append("About me: " + prof.about_me.strip()[:900])
    return "\n".join(bits) if bits else "(none yet.)"


def _format_atomic_claims_block(claims: list[str]) -> str:
    if not claims:
        return "(none — use only the user's latest message as the factual source for new memory_facts.)"
    return "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))


def _extract_preference_pairs_from_memory(memory_fact_texts: list[str]) -> list[tuple[str, str, str]]:
    """Parse 'Prefers X over Y' memory facts into tuples (x, y, original_text)."""
    out: list[tuple[str, str, str]] = []
    for raw in memory_fact_texts:
        t = (raw or "").strip()
        if not t:
            continue
        m = re.match(r"(?i)prefers\s+(.+?)\s+over\s+(.+)$", t)
        if not m:
            continue
        left = " ".join(m.group(1).split()).strip(" '\"")
        right = " ".join(m.group(2).split()).strip(" '\"")
        if not left or not right:
            continue
        out.append((left, right, t))
    return out


def _is_direct_or_choice(user_text: str, left: str, right: str) -> bool:
    t = " ".join((user_text or "").lower().split())
    l = re.escape(left.lower())
    r = re.escape(right.lower())
    if re.search(rf"\b{l}\b\s*(?:/|or)\s*\b{r}\b", t):
        return True
    if re.search(rf"\b{r}\b\s*(?:/|or)\s*\b{l}\b", t):
        return True
    if re.search(rf"\b{l}\b", t) and re.search(rf"\b{r}\b", t) and ("?" in t or len(t) <= 72):
        return True
    return False


def _ground_reply_with_memory_preferences(
    reply: str,
    *,
    user_text: str,
    memory_fact_texts: list[str],
) -> tuple[str, list[str]]:
    """
    If user asks A-or-B and memory stores "Prefers A over B", force an explicit memory-grounded answer prefix.
    """
    for left, right, source in _extract_preference_pairs_from_memory(memory_fact_texts):
        if not _is_direct_or_choice(user_text, left, right):
            continue
        prefix = f"You already said you prefer {left} over {right}, so between those two, it's {left} for you."
        low_reply = (reply or "").lower()
        if "prefer" in low_reply and left.lower() in low_reply and right.lower() in low_reply:
            return reply, [source]
        combined = f"{prefix} {reply}".strip()
        return combined, [source]
    return reply, []


SHADOW_INSTRUCTIONS = """You are not an AI product, therapist, or employee. You are the user's shadow — the inner
dialogue that uses their own vocabulary and remembers what they actually said.

Speak so it feels like them talking to themselves in a mirror: honest, specific, not performative.

FAITHFUL LANGUAGE (strict):
- Direct address (you). Stay on their topic and concrete words.
- Do NOT write third-person notes ("User is…", "They seem to be navigating…").
- Do NOT replace specifics with vague psychology ("themes", "journey", "space", "processing").
- Read and USE the structured memory below; reference it when relevant so this feels continuous, not amnesic.
- Read and USE the Foresight decision context below when they refer to people, situations, or past runs — that is the
  same Decision-mode history, not a separate "profile-only" world.
- Read and USE the profile block below (priorities/constraints/values/about_me). If they ask "what do you remember"
  or ask about priorities, answer from stored items first before inferring.
- If a stored memory clearly answers a direct either-or question, state that remembered preference first (explicitly),
  then add nuance if needed. Do NOT hedge into neutrality when memory is explicit.
- Short paragraphs. No numbered homework or life plans. No picking their decision for them.

ATOMIC CLAIMS (machine decomposition of the user's LATEST message only; language-agnostic, one proposition per line):
{atomic_claims_block}

MEMORY FACTS (structured output):
- When the atomic-claims list is non-empty, emit one `memory_facts` item per claim that is NEW relative to structured memory
  on file and worth persisting (identity, views, behavior, goals, constraints). Do not merge two claims into one row.
- For each item, set `subject_ref` (usually "user"), `predicate` (snake_case, e.g. studies_at, works_at, friend_of, prefers),
  and `object_value` (the school, person, or literal). These fields power typed storage and time-aware updates; leave them
  empty only if you cannot name a relation (then `text` alone is used as a legacy flat fact).
- `text` must remain a clear one-line fact; `evidence` should quote a few words from the user's message when possible.
- When the atomic-claims list is empty, fall back to 0–12 items only if the latest message still states NEW concrete facts.
- FORBIDDEN in memory_facts.text: meta-summaries with no content ("significant shift in identity") — either write the
  actual fact ("Now identifies as Republican") or omit.

Structured memory already on file (may be empty):
{memory_block}

Profile fields on file (may be empty):
{profile_block}

Past Foresight decision runs + related memory (may be minimal if none saved):
{decision_context_block}

Running notes from past shadow turns (may be empty):
{shadow_block}

Conversation so far:
{transcript}

Return JSON: reply_to_user, suggest_decision_navigation, memory_facts."""


def run_shadow_turn(
    messages: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> tuple[str, bool, ShadowSelfState, list[str] | None, list[str]]:
    """Return (assistant_reply, suggest_decision_navigation, updated_state, recorded_fact_texts_or_none, used_memory_facts)."""
    s = settings or load_settings()
    if not messages:
        raise ValueError("messages must be non-empty")
    last = messages[-1]
    if str(last.get("role")) != "user":
        raise ValueError("last message must be from user")

    if not (s.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY is required for shadow chat")

    llm = build_openai_llm(s, temperature=0.68)

    state = load_shadow_self(settings=s)
    shadow_block = state.narrative.strip() or "(none yet — first turns.)"
    transcript = _format_transcript(messages)

    prof = load_user_profile(settings=s)
    mem_active = active_memory_facts(list(prof.memory_facts))
    if mem_active:
        memory_block = "\n".join(format_stored_fact_bullet(x) for x in mem_active[-32:])
    else:
        memory_block = "(none yet.)"
    profile_block = _format_profile_block(prof)

    last_user_text = str(last.get("content", "") or "").strip()
    decision_context_block = build_shadow_decision_context_block(
        settings=s,
        profile=prof,
        last_user_message=last_user_text,
    )

    llm_claims = build_openai_llm(s, temperature=0.12)
    atomic_claims = run_atomic_claims(last_user_text, llm_claims, max_claims=12)
    atomic_claims_block = _format_atomic_claims_block(atomic_claims)

    prompt = SHADOW_INSTRUCTIONS.format(
        memory_block=memory_block,
        profile_block=profile_block,
        decision_context_block=decision_context_block,
        shadow_block=shadow_block,
        transcript=transcript,
        atomic_claims_block=atomic_claims_block,
    )
    turn = structured_predict(llm, ShadowChatTurn, prompt)

    reply = turn.reply_to_user.strip()
    flag = bool(turn.suggest_decision_navigation)
    memory_used: list[str] = []

    records: list[ProfileMemoryFact] = []
    for d in turn.memory_facts:
        cat = _coerce_category(d.category)
        subj = (d.subject_ref or "user").strip() or "user"
        pred = (d.predicate or "").strip()[:200]
        obj = (d.object_value or "").strip()[:500]
        txt = (d.text or "").strip()
        if not pred or not obj:
            if not txt:
                continue
            if len(txt) > 280:
                txt = txt[:277] + "…"
            records.append(
                ProfileMemoryFact(
                    id="",
                    category=cat,
                    text=txt[:500],
                    source="shadow",
                    created_at="",
                    subject_ref=subj,
                    evidence=(d.evidence or "").strip()[:220],
                )
            )
            continue
        if len(txt) > 280:
            txt = txt[:277] + "…"
        if not txt:
            txt = render_triple_line(subj, pred, obj)[:500]
        records.append(
            ProfileMemoryFact(
                id="",
                category=cat,
                text=txt[:500],
                source="shadow",
                created_at="",
                subject_ref=subj,
                predicate=pred,
                object_value=obj,
                evidence=(d.evidence or "").strip()[:220],
            )
        )

    recorded: list[str] | None = None
    if records:
        combined = " · ".join(r.text for r in records)
        state = merge_observation(state, combined)
        save_shadow_self(state, settings=s)

        prof = append_profile_memory_records(prof, records)
        save_user_profile(prof, settings=s)
        recorded = [r.text for r in records]
    else:
        state = state.model_copy(update={"turn_count": state.turn_count + 1})
        save_shadow_self(state, settings=s)

    reply, used = _ground_reply_with_memory_preferences(
        reply,
        user_text=last_user_text,
        memory_fact_texts=[x.text for x in prof.memory_facts if x.status == "active"],
    )
    if used:
        memory_used.extend(used)

    return reply, flag, state, recorded, memory_used
