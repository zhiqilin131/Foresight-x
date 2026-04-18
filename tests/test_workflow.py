"""Phase 4: LlamaIndex Workflow orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from foresight_x.config import Settings
from foresight_x.orchestration.pipeline import PipelineContext
from foresight_x.orchestration.workflow import ForesightStartEvent, ForesightWorkflow, run_pipeline_workflow
from foresight_x.schemas import DecisionTrace


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("TAVILY_API_KEY", "")
    return Settings(foresight_data_dir=tmp_path)


def test_run_pipeline_workflow_returns_trace(isolated_settings: Settings) -> None:
    ctx = PipelineContext(settings=isolated_settings, llm=None)

    async def _run() -> DecisionTrace:
        return await run_pipeline_workflow(
            ctx,
            "Career pivot under time pressure.",
            decision_id="wf-1",
            persist_trace=True,
            workflow_timeout=120.0,
        )

    trace = asyncio.run(_run())
    assert isinstance(trace, DecisionTrace)
    assert trace.decision_id == "wf-1"
    assert (isolated_settings.traces_dir / "wf-1.json").is_file()


def test_foresight_workflow_class_steps(isolated_settings: Settings) -> None:
    ctx = PipelineContext(settings=isolated_settings, llm=None)

    async def _run() -> DecisionTrace:
        wf = ForesightWorkflow(ctx, timeout=120.0)
        handler = wf.run(
            start_event=ForesightStartEvent(
                raw_input="Smaller async workflow check.",
                decision_id="wf-2",
                persist_trace=False,
            )
        )
        return await handler

    trace = asyncio.run(_run())
    assert isinstance(trace, DecisionTrace)
    assert trace.decision_id == "wf-2"
