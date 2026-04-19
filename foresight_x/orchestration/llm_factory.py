"""LLM factory helpers for pipeline structured prediction."""

from __future__ import annotations

from typing import Any

from llama_index.llms.openai import OpenAI

from foresight_x.config import Settings, load_settings


def build_openai_llm(settings: Settings | None = None) -> Any:
    """Build a LlamaIndex OpenAI-compatible LLM for structured_predict calls."""
    s = settings or load_settings()
    kwargs: dict[str, Any] = {
        "model": s.openai_model,
        "api_key": s.openai_api_key or None,
        # Keep outputs concise and deterministic for schema-constrained generation.
        "temperature": 0.2,
    }
    if s.openai_api_base:
        kwargs["api_base"] = s.openai_api_base
    return OpenAI(**kwargs)
