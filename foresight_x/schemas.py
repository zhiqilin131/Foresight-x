"""Pydantic contracts: single source of truth for all modules."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TimePressure(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    PARTIAL = "partial"
    IRREVERSIBLE = "irreversible"


class UserState(BaseModel):
    raw_input: str
    goals: list[str]
    time_pressure: TimePressure
    stress_level: int = Field(ge=0, le=10)
    workload: int = Field(ge=0, le=10)
    current_behavior: str
    decision_type: str
    reversibility: Reversibility
    deadline_hint: str | None = None


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
