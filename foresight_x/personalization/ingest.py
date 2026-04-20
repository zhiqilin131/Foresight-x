"""Analyze pasted chat or email exports and merge behavioral insights into ``UserProfile``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from foresight_x.config import Settings, load_settings
from foresight_x.extraction.atomic_claims import run_atomic_claims
from foresight_x.memory.profile_store import empty_profile, load_profile as load_tier3_profile, save_profile as save_tier3_profile
from foresight_x.orchestration.llm_factory import build_openai_llm
from foresight_x.profile.memory_structured import render_triple_line
from foresight_x.profile.merge import append_profile_memory_records
from foresight_x.profile.store import load_user_profile, save_user_profile
from foresight_x.schemas import MemoryFactCategory, ProfileMemoryFact, UserProfile, rebuild_priority_lines_from_flat
from foresight_x.structured_predict import structured_predict

MAX_INGEST_CHARS = 80_000


class PersonalizationMemoryFactDraft(BaseModel):
    category: Literal["identity", "views", "behavior", "goals", "constraints", "other"] = Field(
        default="other",
        description="Bucket for one atomic fact from the excerpt.",
    )
    text: str = Field(
        max_length=280,
        description="One standalone proposition supported by the excerpt; do not merge unrelated statements.",
    )
    subject_ref: str = Field(default="user", description="Entity this row is about; default user.")
    predicate: str = Field(
        default="",
        description="snake_case relation when possible (studies_at, friend_of, …); empty = legacy flat line.",
    )
    object_value: str = Field(default="", description="Object of the relation when predicate is set.")
    evidence: str = Field(default="", max_length=280, description="Short quote from the excerpt supporting this row.")


def _coerce_memory_category(raw: str) -> MemoryFactCategory:
    m: dict[str, MemoryFactCategory] = {
        "identity": MemoryFactCategory.IDENTITY,
        "views": MemoryFactCategory.VIEWS,
        "behavior": MemoryFactCategory.BEHAVIOR,
        "goals": MemoryFactCategory.GOALS,
        "constraints": MemoryFactCategory.CONSTRAINTS,
        "other": MemoryFactCategory.OTHER,
    }
    return m.get(str(raw).strip().lower(), MemoryFactCategory.OTHER)


class PersonalizationExtract(BaseModel):
    """Structured deltas inferred from the user's own text only (no invention)."""

    recurring_themes_add: list[str] = Field(
        default_factory=list,
        description="Short lines: behavioral patterns (how they delay, argue, seek reassurance, etc.).",
    )
    values_add: list[str] = Field(
        default_factory=list,
        description="Stable values implied by what they say or do in the excerpt.",
    )
    current_goals_add: list[str] = Field(
        default_factory=list,
        description="Goals or wants visible in the text.",
    )
    known_constraints_add: list[str] = Field(
        default_factory=list,
        description="Constraints (time, money, people) mentioned or clearly implied.",
    )
    inferred_priority_lines: list[str] = Field(
        default_factory=list,
        description="One-line machine insights to append to inferred_priorities (behavioral, not therapy).",
    )
    about_me_append: str = Field(
        default="",
        description="2–4 sentences: how the model should perceive this person from this excerpt.",
    )
    risk_posture: Literal["risk-averse", "moderate", "risk-seeking", "unknown"] = Field(
        default="unknown",
        description="Only set if clearly supported; otherwise unknown.",
    )
    memory_facts_add: list[PersonalizationMemoryFactDraft] = Field(
        default_factory=list,
        description=(
            "0–24 atomic durable facts (category + text) grounded in the excerpt. "
            "When the prior decomposition lists numbered claims, emit one memory_facts_add row per numbered line "
            "that should be stored (same proposition; category may be refined). Never merge two numbered claims into one row."
        ),
    )


INGEST_PROMPT = """You analyze a raw text export (email thread, chat log, or mixed). The user pasted it to improve
how the app models their behavior—not for therapy or moral judgment.

Prior pass: atomic factual claims already extracted from the SAME excerpt (one independent proposition per line; trust this for granularity):
---
{claims_block}
---

Rules:
- Use ONLY what appears in the excerpt. Do not invent biographical facts or events.
- Prefer concrete behavioral patterns over vague labels.
- You may write output in English or Chinese to match the source text.
- If the text is too short or uninformative, return mostly empty lists and a short honest about_me_append.
- Populate memory_facts_add with one entry per durable fact: when the prior block lists numbered claims, align rows to those lines
  (one memory_facts_add item per relevant numbered claim; do not fuse multiple lines). If the prior block is empty, still split any
  explicit self-reported facts in the TEXT into separate memory_facts_add rows using the same one-proposition-per-row rule.
- When possible, set subject_ref (usually "user"), predicate (snake_case), object_value, and evidence for typed storage; otherwise
  use text-only legacy rows.

TEXT (may be truncated):
---
{text}
---

Return JSON matching the schema (PersonalizationExtract)."""


def _dedupe_extend(existing: list[str], additions: list[str], *, max_items: int, max_len: int = 480) -> list[str]:
    seen = {x.strip().lower() for x in existing if x.strip()}
    out = list(existing)
    for raw in additions:
        t = (raw or "").strip()
        if not t:
            continue
        if len(t) > max_len:
            t = t[: max_len - 1] + "…"
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    if len(out) > max_items:
        out = out[-max_items:]
    return out


def _merge_profiles(base: UserProfile, ext: PersonalizationExtract, *, stamp: str) -> UserProfile:
    themes = _dedupe_extend(list(base.recurring_themes), ext.recurring_themes_add, max_items=36)
    values = _dedupe_extend(list(base.values), ext.values_add, max_items=24)
    goals = _dedupe_extend(list(base.current_goals), ext.current_goals_add, max_items=24)
    constraints = _dedupe_extend(list(base.known_constraints), ext.known_constraints_add, max_items=24)

    inf = list(base.inferred_priorities)
    inf_seen = {x.strip().lower() for x in inf if x.strip()}
    for line in ext.inferred_priority_lines:
        t = (line or "").strip()
        if not t or len(t) > 480:
            continue
        k = t.lower()
        if k in inf_seen:
            continue
        inf_seen.add(k)
        inf.append(t)
    if len(inf) > 56:
        inf = inf[-56:]

    about = (base.about_me or "").strip()
    append = (ext.about_me_append or "").strip()
    if append:
        block = f"---\nPersonalization import ({stamp}): {append}"
        about = f"{about}\n\n{block}".strip() if about else block

    risk = base.risk_posture
    if ext.risk_posture != "unknown":
        if base.risk_posture == "unknown":
            risk = ext.risk_posture
        # If we already had a posture, only overwrite when new signal is non-unknown.
        elif ext.risk_posture != base.risk_posture:
            risk = ext.risk_posture

    conf = min(1.0, float(base.confidence or 0.0) + 0.07)

    prof = base.model_copy(
        update={
            "recurring_themes": themes,
            "values": values,
            "current_goals": goals,
            "known_constraints": constraints,
            "inferred_priorities": inf,
            "about_me": about,
            "risk_posture": risk,
            "confidence": conf,
            "last_updated": stamp,
        }
    )
    recs: list[ProfileMemoryFact] = []
    for d in ext.memory_facts_add:
        cat = _coerce_memory_category(d.category)
        subj = (d.subject_ref or "user").strip() or "user"
        pred = (d.predicate or "").strip()
        obj = (d.object_value or "").strip()
        txt = (d.text or "").strip()
        ev = (d.evidence or "").strip()
        if pred and obj:
            line = txt or render_triple_line(subj, pred, obj)
            recs.append(
                ProfileMemoryFact(
                    id="",
                    category=cat,
                    text=line[:500],
                    source="personalize",
                    created_at="",
                    subject_ref=subj,
                    predicate=pred[:200],
                    object_value=obj[:500],
                    evidence=ev[:280],
                )
            )
        elif txt:
            recs.append(
                ProfileMemoryFact(
                    id="",
                    category=cat,
                    text=txt[:500],
                    source="personalize",
                    created_at="",
                    subject_ref=subj,
                    evidence=ev[:280],
                )
            )
    if recs:
        prof = append_profile_memory_records(prof, recs)
    return prof


def ingest_personalization_text(raw: str, *, settings: Settings | None = None) -> tuple[UserProfile, PersonalizationExtract, str]:
    """Run LLM extraction, merge into disk profile + Tier-3 mirror, return merged profile and extract."""
    s = settings or load_settings()
    text = (raw or "").strip()
    if not text:
        raise ValueError("text is empty")
    if len(text) > MAX_INGEST_CHARS:
        text = text[: MAX_INGEST_CHARS - 20] + "\n…[truncated]"

    if not (s.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY is required for personalization ingest")

    llm_claims = build_openai_llm(s, temperature=0.12)
    claims = run_atomic_claims(text, llm_claims, max_claims=24)
    claims_block = (
        "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
        if claims
        else "(empty — derive memory_facts_add from TEXT using one proposition per memory row.)"
    )

    llm = build_openai_llm(s, temperature=0.35)
    prompt = INGEST_PROMPT.format(text=text, claims_block=claims_block)
    ext = structured_predict(llm, PersonalizationExtract, prompt)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    base = load_user_profile(settings=s)
    merged = _merge_profiles(base, ext, stamp=stamp)
    merged = rebuild_priority_lines_from_flat(merged, system_channel="personalize")

    uid = (s.foresight_user_id or "demo_user").strip() or "demo_user"
    merged = merged.model_copy(update={"user_id": merged.user_id or uid})

    path = save_user_profile(merged, settings=s)

    # Keep recommender Tier-3 file aligned with data/profile semantic fields.
    tier_prior = load_tier3_profile(uid) or empty_profile(uid)
    n_sum = max(tier_prior.n_decisions_summarized, merged.n_decisions_summarized)
    tier_merged = tier_prior.model_copy(
        update={
            "recurring_themes": merged.recurring_themes,
            "values": merged.values,
            "current_goals": merged.current_goals,
            "known_constraints": merged.known_constraints,
            "inferred_priorities": merged.inferred_priorities,
            "about_me": merged.about_me,
            "risk_posture": merged.risk_posture,
            "confidence": merged.confidence,
            "last_updated": merged.last_updated,
            "user_priorities": merged.user_priorities,
            "priorities": merged.priorities,
            "priority_lines": merged.priority_lines,
            "constraints": merged.constraints,
            "memory_facts": merged.memory_facts,
            "n_decisions_summarized": n_sum,
        }
    )
    save_tier3_profile(tier_merged)

    return merged, ext, str(path)


def preview_extract_summary(ext: PersonalizationExtract) -> list[str]:
    """Short bullet lines for API/UI."""
    lines: list[str] = []
    for t in ext.recurring_themes_add[:5]:
        if t.strip():
            lines.append(f"Pattern: {t.strip()}")
    for t in ext.inferred_priority_lines[:5]:
        if t.strip():
            lines.append(f"Inferred: {t.strip()}")
    if ext.about_me_append.strip():
        lines.append(f"About (model view): {ext.about_me_append.strip()[:280]}{'…' if len(ext.about_me_append.strip()) > 280 else ''}")
    for f in ext.memory_facts_add[:6]:
        t = (f.text or "").strip()
        if t:
            lines.append(f"Fact [{f.category}]: {t[:200]}{'…' if len(t) > 200 else ''}")
    if not lines:
        lines.append("No strong new signals — profile updated lightly.")
    return lines[:12]
