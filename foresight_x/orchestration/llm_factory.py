"""LLM factory helpers for pipeline structured prediction."""

from __future__ import annotations

from typing import Any

from llama_index.llms.openai import OpenAI

from foresight_x.config import Settings, load_settings


def build_openai_llm(settings: Settings | None = None, *, temperature: float | None = None) -> Any:
    """Build a LlamaIndex OpenAI-compatible LLM for structured_predict calls.

    Using a smaller/faster model via OPENAI_MODEL reduces cost/latency but can hurt
    structured-output fidelity and calibration — only appropriate for non-critical steps.
    """
    s = settings or load_settings()
    kwargs: dict[str, Any] = {
        "model": s.openai_model,
        "api_key": s.openai_api_key or None,
        # Default: concise deterministic structured outputs; override for chat-like turns.
        "temperature": 0.2 if temperature is None else temperature,
    }
    if s.openai_api_base:
        kwargs["api_base"] = s.openai_api_base
    return OpenAI(**kwargs)
