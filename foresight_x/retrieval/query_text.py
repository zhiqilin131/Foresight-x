"""Extra query text from user profile fields for vector retrieval.

**Single source of truth** for profile-shaped text embedded in:
``UserMemory`` / ``WorldKnowledge`` queries (via :mod:`foresight_x.retrieval.memory_query`),
rerank overlap in :mod:`foresight_x.retrieval.memory`, ``EvidenceBundle.recent_events`` profile
lines, and any UI that wants to show the *exact* string fed to embeddings.

Do not duplicate these labels or field joins elsewhere — import
:func:`profile_snippet_for_retrieval` or :func:`profile_fact_line_for_recent_events`.
"""

from __future__ import annotations

from foresight_x.profile.memory_structured import format_memory_fact_prompt_line
from foresight_x.schemas import UserState

# Truncation windows for embedding-facing text (single source; ``memory_query`` imports these).
ABOUT_ME_SNIPPET_MAX_CHARS = 2000
SITUATION_QUERY_MAX_CHARS = 2000


def profile_snippet_for_retrieval(user_state: UserState) -> str:
    """Whitespace-joined, labeled profile fields — identical substring inside memory/world vector queries."""
    parts: list[str] = []
    if user_state.profile_user_priorities:
        parts.append("user_stated_priorities " + " ".join(user_state.profile_user_priorities))
    if user_state.profile_clarification_priorities:
        parts.append("clarification_priorities " + " ".join(user_state.profile_clarification_priorities))
    if user_state.profile_memory_facts:
        parts.append(
            "memory_facts "
            + " ".join(format_memory_fact_prompt_line(f) for f in user_state.profile_memory_facts)
        )
    if user_state.profile_inferred_priorities:
        parts.append("system_inferred_priorities " + " ".join(user_state.profile_inferred_priorities))
    if user_state.profile_about_me.strip():
        parts.append("about_me " + user_state.profile_about_me.strip()[: ABOUT_ME_SNIPPET_MAX_CHARS])
    if user_state.profile_constraints:
        parts.append("constraints " + " ".join(user_state.profile_constraints))
    if user_state.profile_values:
        parts.append("values " + " ".join(user_state.profile_values))
    return " ".join(parts)


def profile_fact_line_for_recent_events(user_state: UserState) -> str | None:
    """One evidence line: **exact** :func:`profile_snippet_for_retrieval` output with a fixed prefix (no extra truncation)."""
    snip = profile_snippet_for_retrieval(user_state).strip()
    if not snip:
        return None
    return f"Profile (retrieval snippet): {snip}"
