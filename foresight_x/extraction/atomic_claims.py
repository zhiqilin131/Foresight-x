"""Decompose user text into atomic factual claims via structured LLM output (no regex heuristics)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from foresight_x.structured_predict import structured_predict

# Whitespace / punctuation normalization only — no domain-specific phrase lists.
_WS_RE = re.compile(r"\s+")


class AtomicClaimsExtraction(BaseModel):
    """One proposition per element; wording grounded in the source text."""

    claims: list[str] = Field(
        default_factory=list,
        description=(
            "Each string is exactly one factual proposition explicitly supported by the input "
            "(identity, affiliation, preference, constraint, relationship status, etc.). "
            "Never merge independent facts into one string."
        ),
    )

    @field_validator("claims", mode="before")
    @classmethod
    def _strip_claims(cls, v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        out: list[str] = []
        for x in v:
            t = _WS_RE.sub(" ", str(x or "").strip())
            if t:
                out.append(t)
        return out


ATOMIC_CLAIMS_PROMPT = """You decompose the following user-authored text into atomic factual claims for long-term user modeling.

Hard rules:
- Each list item must express EXACTLY ONE proposition the text explicitly states (who/what/where/when/preference/constraint/relationship or life-status/affiliation/education level when stated).
- If one sentence states several independent facts, split them into separate list items. Do not merge multiple facts into one string.
- Preserve proper nouns and numbers as given; keep the same language as the source when possible.
- Do not infer causes, psychology, or unstated biography. Do not generalize beyond the text.
- Omit content-free hedges alone ("maybe", "not sure") unless they are attached to a factual assertion worth keeping with that assertion.
- If there are no extractable factual claims, return an empty list.
- At most {max_claims} items. Each item at most 220 characters.

TEXT:
---
{text}
---

Return JSON matching the schema AtomicClaimsExtraction (field "claims" only).
"""


def run_atomic_claims(text: str, llm: Any, *, max_claims: int = 16) -> list[str]:
    """Return deduplicated atomic claims (case-insensitive), capped at ``max_claims``."""
    raw = (text or "").strip()
    if not raw:
        return []
    mc = max(4, min(max_claims, 32))
    prompt = ATOMIC_CLAIMS_PROMPT.format(text=raw, max_claims=mc)
    ext = structured_predict(llm, AtomicClaimsExtraction, prompt)
    seen: set[str] = set()
    out: list[str] = []
    for c in ext.claims:
        t = _WS_RE.sub(" ", (c or "").strip())
        if not t:
            continue
        if len(t) > 220:
            t = t[:217] + "…"
        k = t.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
        if len(out) >= mc:
            break
    return out
