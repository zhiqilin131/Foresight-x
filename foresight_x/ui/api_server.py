"""FastAPI server for the Foresight-X web UI (Vite dev proxy → /api/*)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from foresight_x.config import load_settings
from foresight_x.harness.improvement_loop import apply_outcome_to_memory
from foresight_x.harness.outcome_tracker import save_decision_outcome
from foresight_x.orchestration.pipeline import PipelineContext, run_pipeline
from foresight_x.schemas import DecisionOutcome
from foresight_x.ui.cli import _build_context


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


app = FastAPI(title="Foresight-X API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    raw_input: str = Field(min_length=1)


class RunResponse(BaseModel):
    trace: dict
    notes: list[str]
    trace_path: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/run", response_model=RunResponse)
def run_decision(body: RunRequest) -> RunResponse:
    settings = load_settings()
    ctx, notes = _build_context(settings)
    trace = run_pipeline(ctx, body.raw_input.strip(), persist_trace=True)
    trace_path = settings.traces_dir / f"{trace.decision_id}.json"
    return RunResponse(
        trace=trace.model_dump(mode="json"),
        notes=notes,
        trace_path=str(trace_path),
    )


class RecordOutcomeRequest(BaseModel):
    decision_id: str = Field(min_length=1)
    user_took_recommended_action: bool
    actual_outcome: str = Field(min_length=1)
    user_reported_quality: int = Field(ge=1, le=5)
    reversed_later: bool


class RecordOutcomeResponse(BaseModel):
    ok: bool
    outcome_path: str


@app.post("/api/record-outcome", response_model=RecordOutcomeResponse)
def record_outcome(body: RecordOutcomeRequest) -> RecordOutcomeResponse:
    settings = load_settings()
    trace_path = settings.traces_dir / f"{body.decision_id}.json"
    if not trace_path.exists():
        raise HTTPException(status_code=404, detail=f"Trace not found for decision_id={body.decision_id}")
    outcome = DecisionOutcome(
        decision_id=body.decision_id,
        user_took_recommended_action=body.user_took_recommended_action,
        actual_outcome=body.actual_outcome.strip(),
        user_reported_quality=body.user_reported_quality,
        reversed_later=body.reversed_later,
        timestamp=_utc_now(),
    )
    path = save_decision_outcome(outcome, settings=settings)
    apply_outcome_to_memory(body.decision_id, outcome, settings=settings)
    return RecordOutcomeResponse(ok=True, outcome_path=str(path))
