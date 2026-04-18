"""WorldKnowledge cache + Tavily (mocked) behavior."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from llama_index.core.embeddings import MockEmbedding

from foresight_x.config import Settings
from foresight_x.retrieval.seed import ingest_world_markdown
from foresight_x.retrieval.world_cache import WorldKnowledge
from foresight_x.schemas import Fact, Reversibility, TimePressure, UserState


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
    monkeypatch.delenv("FORESIGHT_DATA_DIR", raising=False)
    monkeypatch.setenv("TAVILY_API_KEY", "")
    return Settings(
        chroma_persist_dir=tmp_path / "chroma",
        foresight_data_dir=tmp_path / "data",
        openai_api_key="test",
        tavily_api_key="test",
    )


@pytest.fixture
def embed_model() -> MockEmbedding:
    return MockEmbedding(embed_dim=1536)


def test_cache_only_no_tavily(settings: Settings, embed_model: MockEmbedding) -> None:
    wk = WorldKnowledge(settings=settings, embed_model=embed_model, tavily=None)
    ingest_world_markdown(wk)
    state = UserState(
        raw_input="Should I negotiate internship deadline?",
        goals=["better information"],
        time_pressure=TimePressure.MEDIUM,
        stress_level=4,
        workload=5,
        current_behavior="deliberate",
        decision_type="career",
        reversibility=Reversibility.PARTIAL,
    )
    ev = wk.retrieve(state, min_cache_hits=10, top_k=4)
    assert len(ev.facts) + len(ev.base_rates) >= 1


def test_tavily_supplements_when_sparse(settings: Settings, embed_model: MockEmbedding) -> None:
    mock_gw = MagicMock()
    mock_gw.search_as_facts.return_value = [
        Fact(text="Live web snippet about recruiting.", source_url="https://x.test", confidence=0.7)
    ]
    wk = WorldKnowledge(settings=settings, embed_model=embed_model, tavily=mock_gw)
    state = UserState(
        raw_input="urgent offer comparison",
        goals=["maximize EV"],
        time_pressure=TimePressure.HIGH,
        stress_level=9,
        workload=8,
        current_behavior="rushed",
        decision_type="career",
        reversibility=Reversibility.IRREVERSIBLE,
        deadline_hint="tomorrow",
    )
    ev = wk.retrieve(state, min_cache_hits=5, top_k=3)
    assert mock_gw.search_as_facts.called
    assert len(ev.recent_events) >= 1
