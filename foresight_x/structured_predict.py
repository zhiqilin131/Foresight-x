"""Compatibility wrapper for LlamaIndex structured prediction."""

from __future__ import annotations

from typing import Any

from llama_index.core import PromptTemplate


def structured_predict(llm: Any, output_cls: Any, prompt: str, **kwargs: Any) -> Any:
    """Run structured prediction across llama-index API variants.

    Older call sites and test doubles use raw string prompts; newer llama-index
    releases require a BasePromptTemplate instance.
    """
    try:
        return llm.structured_predict(output_cls, prompt, **kwargs)
    except Exception:
        return llm.structured_predict(output_cls, PromptTemplate(prompt), **kwargs)
