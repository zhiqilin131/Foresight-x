"""Pydantic contracts: single source of truth for all modules."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# Provenance for each priority row (API + UI + writers).
ProfileLineChannel = Literal["profile", "clarification", "shadow", "personalize", "legacy"]


class ProfileLine(BaseModel):
    """One user-stated or system-recorded priority line, with source channel."""

    id: str = Field(default="", description="UUID when created in-app; empty for legacy imports.")
    text: str = Field(min_length=1)
    origin: Literal["user", "system"] = "system"
    channel: ProfileLineChannel = "legacy"
    created_at: str = Field(default="", description="ISO-8601 UTC when known.")

    @field_validator("text", mode="before")
    @classmethod
    def _strip_text(cls, v: Any) -> str:
        return str(v or "").strip()


class MemoryFactCategory(str, Enum):
    """Bucket for durable profile facts (concrete, not therapist paraphrases)."""

    IDENTITY = "identity"
    VIEWS = "views"
    BEHAVIOR = "behavior"
    GOALS = "goals"
    CONSTRAINTS = "constraints"
    OTHER = "other"


MemoryFactSource = Literal["shadow", "personalize", "clarification", "user", "import", "legacy"]

MemoryFactStatus = Literal["active", "deprecated"]


class ProfileMemoryFact(BaseModel):
    """Structured memory: legacy flat ``text`` and/or typed triple + time/version semantics."""

    id: str = Field(default="", description="UUID; assigned on load if missing.")
    category: MemoryFactCategory = MemoryFactCategory.OTHER
    text: str = Field(min_length=1, description="Human-readable line for UI and prompts (always set).")
    source: MemoryFactSource = "shadow"
    created_at: str = Field(default="", description="ISO-8601 UTC when known.")
    # Typed layer (optional; empty predicate => legacy category+text only)
    subject_ref: str = Field(
        default="user",
        description="Entity the fact is about; default 'user' for first-person memories.",
    )
    predicate: str = Field(
        default="",
        description="snake_case relation label, e.g. studies_at, friend_of, prefers.",
    )
    object_value: str = Field(
        default="",
        description="Object of the relation (entity label or literal).",
    )
    qualifiers: dict[str, Any] = Field(default_factory=dict, description="Optional key-value qualifiers.")
    valid_from: str = Field(default="", description="ISO-8601 UTC start of validity; empty = unknown.")
    valid_to: str = Field(default="", description="ISO-8601 UTC end of validity; empty = still valid if active.")
    status: MemoryFactStatus = "active"
    replaced_by_id: str = Field(default="", description="Newer fact that supersedes this row when deprecated.")
    supersedes_id: str = Field(default="", description="Prior fact this one replaces.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str = Field(
        default="",
        description="Verbatim or near-verbatim snippet from the user for audit.",
    )

    @field_validator("text", mode="before")
    @classmethod
    def _strip_fact_text(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("subject_ref", "predicate", "object_value", "evidence", mode="before")
    @classmethod
    def _strip_optional_strings(cls, v: Any) -> str:
        return str(v or "").strip()


class TimePressure(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    PARTIAL = "partial"
    IRREVERSIBLE = "irreversible"


class UserProfile(BaseModel):
    """Tier 3 semantic profile (with legacy fields kept for compatibility)."""

    # ---------- Semantic User Profile (Tier 3 Memory) ----------
    user_id: str = ""
    values: list[str] = Field(
        default_factory=list,
        description=(
            "Stable values the user has revealed through past decisions. "
            "E.g. 'long-term stability over short-term gain', 'autonomy', "
            "'relationships over career advancement'."
        ),
    )
    risk_posture: Literal["risk-averse", "moderate", "risk-seeking", "unknown"] = "unknown"
    recurring_themes: list[str] = Field(
        default_factory=list,
        description=(
            "Behavioral patterns observed across past decisions. "
            "E.g. 'tends to overcommit when excited', 'delays irreversible choices'."
        ),
    )
    current_goals: list[str] = Field(
        default_factory=list,
        description="Active goals the user is working toward, distilled from recent decisions.",
    )
    known_constraints: list[str] = Field(
        default_factory=list,
        description="Stable constraints: time, money, obligations, health, location.",
    )
    n_decisions_summarized: int = 0
    last_updated: str = ""
    confidence: float = Field(ge=0, le=1, default=0.0)

    # ---------- data/profile (form + shadow) ----------
    priority_lines: list[ProfileLine] = Field(
        default_factory=list,
        description="Canonical rows with provenance; flat user_priorities/inferred_priorities stay in sync.",
    )
    user_priorities: list[str] = Field(
        default_factory=list,
        description="Mirror of priority_lines with origin=user (Profile UI, clarification).",
    )
    inferred_priorities: list[str] = Field(
        default_factory=list,
        description="Mirror of priority_lines with origin=system (shadow, personalize, …).",
    )
    # Legacy mirror of user_priorities for older JSON files; kept in sync on save.
    priorities: list[str] = Field(default_factory=list)
    about_me: str = ""
    constraints: list[str] = Field(default_factory=list)
    memory_facts: list[ProfileMemoryFact] = Field(
        default_factory=list,
        description="Categorized concrete facts (identity, views, behavior, …) — preferred over vague one-line summaries.",
    )

    @model_validator(mode="before")
    @classmethod
    def _sync_priority_lines_and_flat_lists(cls, data: Any) -> Any:
        """Migrate legacy flat lists into priority_lines, or sync mirrors from priority_lines (before init)."""
        if not isinstance(data, dict):
            return data
        d = dict(data)
        if not d.get("user_priorities") and d.get("priorities"):
            d["user_priorities"] = list(d["priorities"])
        pl_raw = d.get("priority_lines")
        if pl_raw is not None and len(pl_raw) > 0:
            users: list[str] = []
            inferred: list[str] = []
            for row in pl_raw:
                if not isinstance(row, dict):
                    continue
                o = row.get("origin")
                t = str(row.get("text") or "").strip()
                if not t:
                    continue
                if o == "user":
                    users.append(t)
                elif o == "system":
                    inferred.append(t)
            d["user_priorities"] = users
            d["priorities"] = list(users)
            d["inferred_priorities"] = inferred
            return d
        u_raw = list(d.get("user_priorities") or [])
        if not u_raw and d.get("priorities"):
            u_raw = list(d["priorities"])
        i_raw = list(d.get("inferred_priorities") or [])
        if not u_raw and not i_raw:
            return d
        new_lines: list[dict[str, Any]] = []
        for t in u_raw:
            tt = str(t).strip()
            if tt:
                new_lines.append({"text": tt, "origin": "user", "channel": "profile", "id": "", "created_at": ""})
        for t in i_raw:
            tt = str(t).strip()
            if tt:
                new_lines.append({"text": tt, "origin": "system", "channel": "legacy", "id": "", "created_at": ""})
        d["priority_lines"] = new_lines
        d["user_priorities"] = [x["text"] for x in new_lines if x["origin"] == "user"]
        d["priorities"] = list(d["user_priorities"])
        d["inferred_priorities"] = [x["text"] for x in new_lines if x["origin"] == "system"]
        return d

    def stated_priority_lines(self) -> list[str]:
        """User-owned priority lines (excludes inferred)."""
        if self.priority_lines:
            return [x.text for x in self.priority_lines if x.origin == "user"]
        if self.user_priorities:
            return list(self.user_priorities)
        return list(self.priorities)

    def profile_channel_priority_texts(self) -> list[str]:
        """Lines authored in Profile only (excludes clarification modal rows)."""
        if self.priority_lines:
            return [x.text for x in self.priority_lines if x.origin == "user" and x.channel == "profile"]
        return [t for t in self.stated_priority_lines() if t]

    def clarification_priority_texts(self) -> list[str]:
        """Multiple-choice clarification answers saved as user rows."""
        if self.priority_lines:
            return [x.text for x in self.priority_lines if x.origin == "user" and x.channel == "clarification"]
        return []


def rebuild_priority_lines_from_flat(
    profile: UserProfile,
    *,
    system_channel: ProfileLineChannel = "legacy",
) -> UserProfile:
    """Rebuild priority_lines from flat lists (e.g. after bulk LLM merge). All system rows share ``system_channel``."""
    import uuid
    from datetime import datetime, timezone

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    u_src = list(profile.user_priorities) if profile.user_priorities else list(profile.priorities)
    inf = list(profile.inferred_priorities)
    lines: list[ProfileLine] = []
    for t in u_src:
        tt = str(t).strip()
        if tt:
            lines.append(ProfileLine(id=str(uuid.uuid4()), text=tt, origin="user", channel="profile", created_at=ts))
    for t in inf:
        tt = str(t).strip()
        if tt:
            lines.append(
                ProfileLine(id=str(uuid.uuid4()), text=tt, origin="system", channel=system_channel, created_at=ts)
            )
    u = [x.text for x in lines if x.origin == "user"]
    i = [x.text for x in lines if x.origin == "system"]
    return profile.model_copy(
        update={
            "priority_lines": lines,
            "user_priorities": u,
            "priorities": u,
            "inferred_priorities": i,
        }
    )


class UserState(BaseModel):
    raw_input: str
    active_user_id: str = Field(
        default="",
        description="Runtime persona/user id used to scope traces, memory and profile in UI/API.",
    )
    goals: list[str]
    time_pressure: TimePressure
    stress_level: int = Field(ge=0, le=10)
    workload: int = Field(ge=0, le=10)
    current_behavior: str
    decision_type: str
    reversibility: Reversibility
    deadline_hint: str | None = None
    # Filled from persisted UserProfile for retrieval + LLM prompts (defaults keep older traces valid).
    profile_priorities: list[str] = Field(
        default_factory=list,
        description="Combined user-stated + inferred priorities for backward-compatible consumers.",
    )
    profile_user_priorities: list[str] = Field(default_factory=list)
    profile_clarification_priorities: list[str] = Field(
        default_factory=list,
        description="Structured clarification answers (user-chosen), distinct from free-form priorities.",
    )
    profile_inferred_priorities: list[str] = Field(default_factory=list)
    profile_memory_facts: list[ProfileMemoryFact] = Field(default_factory=list)
    profile_about_me: str = ""
    profile_constraints: list[str] = Field(default_factory=list)
    profile_values: list[str] = Field(default_factory=list)


class PastDecision(BaseModel):
    decision_id: str
    situation_summary: str
    chosen_option: str
    outcome: str | None = None
    outcome_quality: int | None = Field(default=None, ge=1, le=5)
    timestamp: str


class MemoryBundle(BaseModel):
    similar_past_decisions: list[PastDecision]
    behavioral_patterns: list[str]
    prior_outcomes_summary: str


class Fact(BaseModel):
    text: str
    source_url: str | None = None
    confidence: float = Field(ge=0, le=1)


class EvidenceBundle(BaseModel):
    facts: list[Fact]
    base_rates: list[Fact]
    recent_events: list[Fact]


class RationalityReport(BaseModel):
    is_rational_state: bool
    detected_biases: list[str]
    confidence: float = Field(ge=0, le=1)
    recommended_slowdowns: list[str]


class Option(BaseModel):
    option_id: str
    name: str
    description: str
    key_assumptions: list[str]
    cost_of_reversal: Literal["low", "medium", "high"]


class Scenario(BaseModel):
    label: Literal["best", "base", "worst"]
    trajectory: str
    probability: float = Field(ge=0, le=1)
    key_drivers: list[str]


class SimulatedFuture(BaseModel):
    option_id: str
    time_horizon: str
    scenarios: list[Scenario]

    @field_validator("scenarios")
    @classmethod
    def probabilities_sum_to_one(cls, scenarios: list[Scenario]) -> list[Scenario]:
        if not scenarios:
            return scenarios
        total = sum(s.probability for s in scenarios)
        if abs(total - 1.0) > 0.05:
            raise ValueError(
                f"scenario probabilities must sum to 1.0 (+/- 0.05), got {total:.4f}"
            )
        return scenarios


class OptionEvaluation(BaseModel):
    option_id: str
    expected_value_score: float = Field(ge=0, le=10)
    risk_score: float = Field(ge=0, le=10)
    regret_score: float = Field(ge=0, le=10)
    uncertainty_score: float = Field(ge=0, le=10)
    goal_alignment_score: float = Field(ge=0, le=10)
    rationale: str


class NextAction(BaseModel):
    action: str
    deadline: str | None = None
    artifacts: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    chosen_option_id: str
    reasoning: str
    next_actions: list[NextAction]
    reassessment_triggers: list[str]


class Reflection(BaseModel):
    possible_errors: list[str]
    uncertainty_sources: list[str]
    model_limitations: list[str]
    information_gaps: list[str]
    self_improvement_signal: str


class DecisionTrace(BaseModel):
    decision_id: str
    timestamp: str
    original_user_input: str = Field(
        default="",
        description="Exact user text before optional LLM clarification (empty on legacy traces).",
    )
    user_state: UserState
    memory: MemoryBundle
    evidence: EvidenceBundle
    rationality: RationalityReport
    options: list[Option]
    futures: list[SimulatedFuture]
    evaluations: list[OptionEvaluation]
    recommendation: Recommendation
    reflection: Reflection


class DecisionOutcome(BaseModel):
    decision_id: str
    user_took_recommended_action: bool
    actual_outcome: str
    user_reported_quality: int = Field(ge=1, le=5)
    reversed_later: bool
    timestamp: str


class HarnessReport(BaseModel):
    """Aggregated metrics for eval_harness (v0 may return an empty or partial report)."""

    trace_count: int = 0
    outcome_count: int = 0
    notes: str = ""


class TraceListItem(BaseModel):
    """Metadata for a saved decision trace (GET /api/traces)."""

    decision_id: str
    timestamp: str
    decision_type: str
    preview: str
    has_outcome: bool = False
    has_commit: bool = False


class DecisionCommit(BaseModel):
    """User explicitly chose an option (adopt) before optional outcome recording."""

    decision_id: str
    chosen_option_id: str
    matches_recommendation: bool = True
    committed_at: str
