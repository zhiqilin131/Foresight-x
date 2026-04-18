"""Tests for foresight_x.config.Settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from foresight_x.config import Settings


class TestSettings:
    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FORESIGHT_DATA_DIR", raising=False)
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        # Override any value from a local .env so defaults are deterministic in CI/dev.
        monkeypatch.setenv("TAVILY_API_KEY", "")
        s = Settings()
        assert s.foresight_user_id == "demo_user"
        assert s.openai_model == "gpt-4o-mini"
        assert s.openai_embedding_model == "text-embedding-3-small"
        assert s.memory_dir == Path("./data") / "memory"
        assert s.chroma_persist_dir == Path("./data/chroma")
        assert s.openai_api_base is None
        assert s.tavily_api_key == ""
        assert s.tavily_search_depth == "advanced"

    def test_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FORESIGHT_USER_ID", "u_test")
        monkeypatch.setenv("FORESIGHT_DATA_DIR", "/tmp/fx_data")
        monkeypatch.setenv("CHROMA_PERSIST_DIR", "/var/chroma")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
        monkeypatch.setenv("OPENAI_API_BASE", "https://example.azure.com")
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-x")
        s = Settings()
        assert s.foresight_user_id == "u_test"
        assert s.traces_dir == Path("/tmp/fx_data") / "traces"
        assert s.chroma_persist_dir == Path("/var/chroma")
        assert s.openai_model == "gpt-4o"
        assert s.openai_api_base == "https://example.azure.com"
        assert s.tavily_api_key == "tvly-x"
