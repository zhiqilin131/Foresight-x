"""User-local facts merged into evidence.recent_events."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foresight_x.config import Settings
from foresight_x.retrieval.user_recent_context import (
    facts_from_user_local_context,
    merge_user_context_into_evidence,
)
from foresight_x.schemas import EvidenceBundle, Fact


@pytest.fixture
def iso(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("FORESIGHT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FORESIGHT_USER_ID", "u1")
    return Settings()


def test_facts_from_shadow_and_traces(iso: Settings, tmp_path: Path) -> None:
    shadow_dir = tmp_path / "shadow_self"
    shadow_dir.mkdir(parents=True)
    shadow_dir.joinpath("u1.json").write_text(
        json.dumps(
            {
                "user_id": "u1",
                "narrative": "• a",
                "observations": ["notices pressure when deadlines stack"],
                "updated_at": "x",
                "turn_count": 1,
            }
        ),
        encoding="utf-8",
    )
    traces_dir = tmp_path / "traces"
    traces_dir.mkdir(parents=True)
    trace_body = {
        "decision_id": "past-1",
        "timestamp": "2026-02-01T12:00:00Z",
        "user_state": {
            "raw_input": "Should I switch teams at work?",
            "goals": ["g"],
            "time_pressure": "low",
            "stress_level": 3,
            "workload": 4,
            "current_behavior": "c",
            "decision_type": "career",
            "reversibility": "partial",
            "active_user_id": "u1",
        },
    }
    traces_dir.joinpath("past-1.json").write_text(json.dumps(trace_body), encoding="utf-8")

    facts = facts_from_user_local_context(settings=iso)
    texts = " ".join(f.text for f in facts).lower()
    assert "shadow" in texts
    assert "pressure when deadlines" in texts
    assert "past decision" in texts
    assert "switch teams" in texts


def test_merge_appends_to_recent_events(iso: Settings, tmp_path: Path) -> None:
    shadow_dir = tmp_path / "shadow_self"
    shadow_dir.mkdir(parents=True)
    shadow_dir.joinpath("u1.json").write_text(
        json.dumps(
            {
                "user_id": "u1",
                "observations": ["pattern A"],
                "updated_at": "x",
                "turn_count": 1,
            }
        ),
        encoding="utf-8",
    )
    base = EvidenceBundle(
        facts=[],
        base_rates=[Fact(text="Live reference (aligned): web", source_url="https://a.test", confidence=0.7)],
        recent_events=[],
    )
    out = merge_user_context_into_evidence(base, settings=iso)
    assert len(out.recent_events) >= 1
    assert any("Shadow" in f.text for f in out.recent_events)
    assert len(out.base_rates) == 1
