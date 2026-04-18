"""Phase 4: synchronous orchestration pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from foresight_x.config import Settings
from foresight_x.orchestration.pipeline import PipelineContext, run_pipeline
from foresight_x.schemas import DecisionTrace


@pytest.fixture
def isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("TAVILY_API_KEY", "")
    return Settings(foresight_data_dir=tmp_path)


def test_run_pipeline_valid_trace_and_persist(isolated_settings: Settings) -> None:
    ctx = PipelineContext(settings=isolated_settings, llm=None, user_memory=None, world=None)
    trace = run_pipeline(
        ctx,
        "I need to decide on a job offer by Friday; I feel anxious.",
        decision_id="pipe-test-1",
        persist_trace=True,
    )
    assert isinstance(trace, DecisionTrace)
    assert trace.decision_id == "pipe-test-1"
    assert trace.user_state.raw_input
    assert trace.options
    assert trace.recommendation.chosen_option_id
    path = isolated_settings.traces_dir / "pipe-test-1.json"
    assert path.is_file()
    assert "user_state" in path.read_text(encoding="utf-8")


def test_run_pipeline_skip_persist(isolated_settings: Settings) -> None:
    ctx = PipelineContext(settings=isolated_settings, llm=None)
    trace = run_pipeline(
        ctx,
        "Quick question about priorities.",
        decision_id="no-save",
        persist_trace=False,
    )
    assert trace.decision_id == "no-save"
    assert not (isolated_settings.traces_dir / "no-save.json").exists()
    assert trace.reflection.possible_errors != ["pending"]
