"""Tests for personalization merge (no LLM)."""

from foresight_x.personalization.ingest import (
    PersonalizationExtract,
    PersonalizationMemoryFactDraft,
    _merge_profiles,
    preview_extract_summary,
)
from foresight_x.schemas import UserProfile


def test_merge_profiles_dedupes_and_appends_about() -> None:
    base = UserProfile(
        recurring_themes=["likes planning"],
        values=[],
        current_goals=[],
        known_constraints=[],
        inferred_priorities=[],
        about_me="Hello",
        confidence=0.2,
    )
    ext = PersonalizationExtract(
        recurring_themes_add=["likes planning", "defers under pressure"],
        values_add=["autonomy"],
        inferred_priority_lines=["Tends to seek reassurance before committing"],
        about_me_append="Often frames tradeoffs as moral tests.",
        risk_posture="moderate",
    )
    out = _merge_profiles(base, ext, stamp="2026-04-18T12:00:00Z")
    assert "defers under pressure" in out.recurring_themes
    assert out.recurring_themes.count("likes planning") == 1
    assert "autonomy" in out.values
    assert any("reassurance" in x for x in out.inferred_priorities)
    assert "Personalization import" in out.about_me
    assert out.risk_posture == "moderate"
    assert out.confidence > 0.2


def test_merge_profiles_appends_memory_facts() -> None:
    base = UserProfile(user_id="u1", memory_facts=[])
    ext = PersonalizationExtract(
        memory_facts_add=[
            PersonalizationMemoryFactDraft(category="identity", text="Goes by Bella"),
            PersonalizationMemoryFactDraft(category="identity", text="Age 20"),
            PersonalizationMemoryFactDraft(category="constraints", text="Studies at CMU"),
        ],
    )
    out = _merge_profiles(base, ext, stamp="2026-04-20T12:00:00Z")
    assert len(out.memory_facts) == 3
    texts = {f.text for f in out.memory_facts}
    assert "Goes by Bella" in texts
    assert "Age 20" in texts
    assert "Studies at CMU" in texts
    assert all(f.source == "personalize" for f in out.memory_facts)


def test_preview_extract_summary_nonempty() -> None:
    ext = PersonalizationExtract(
        recurring_themes_add=["x"],
        inferred_priority_lines=["y"],
        about_me_append="z" * 400,
    )
    lines = preview_extract_summary(ext)
    assert len(lines) >= 1
