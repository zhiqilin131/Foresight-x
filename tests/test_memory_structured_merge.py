"""Structured memory: triple dedup and single-slot deprecation."""

from foresight_x.profile.merge import append_profile_memory_records
from foresight_x.schemas import MemoryFactCategory, ProfileMemoryFact, UserProfile


def test_single_slot_deprecates_prior_object() -> None:
    old = ProfileMemoryFact(
        id="f-old",
        category=MemoryFactCategory.IDENTITY,
        text="user studies_at CMU",
        source="shadow",
        created_at="2025-01-01T00:00:00Z",
        subject_ref="user",
        predicate="studies_at",
        object_value="CMU",
    )
    base = UserProfile(memory_facts=[old])
    new = ProfileMemoryFact(
        id="",
        category=MemoryFactCategory.IDENTITY,
        text="user studies_at Stanford",
        source="shadow",
        created_at="",
        subject_ref="user",
        predicate="studies_at",
        object_value="Stanford",
    )
    out = append_profile_memory_records(base, [new])
    assert len(out.memory_facts) == 2
    dep = next(x for x in out.memory_facts if x.id == "f-old")
    assert dep.status == "deprecated"
    assert dep.replaced_by_id
    active = [x for x in out.memory_facts if x.status == "active"]
    assert len(active) == 1
    assert active[0].object_value == "Stanford"
    assert active[0].supersedes_id == "f-old"


def test_multi_object_predicate_keeps_both() -> None:
    a = ProfileMemoryFact(
        id="a1",
        category=MemoryFactCategory.IDENTITY,
        text="friend_of Bob",
        source="shadow",
        created_at="2025-01-01T00:00:00Z",
        subject_ref="user",
        predicate="friend_of",
        object_value="Bob",
    )
    base = UserProfile(memory_facts=[a])
    b = ProfileMemoryFact(
        id="",
        category=MemoryFactCategory.IDENTITY,
        text="friend_of Ann",
        source="shadow",
        created_at="",
        subject_ref="user",
        predicate="friend_of",
        object_value="Ann",
    )
    out = append_profile_memory_records(base, [b])
    assert len([x for x in out.memory_facts if x.status == "active"]) == 2
