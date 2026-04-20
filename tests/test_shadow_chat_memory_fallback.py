from foresight_x.shadow.chat import _ground_reply_with_memory_preferences


def test_ground_reply_prefers_explicit_memory_for_or_question() -> None:
    reply, used = _ground_reply_with_memory_preferences(
        "You're weighing two legends for different reasons.",
        user_text="Lebron or Kobe?",
        memory_fact_texts=["Prefers LeBron over Kobe"],
    )
    assert "prefer LeBron over Kobe" in reply
    assert "it's LeBron for you" in reply
    assert used == ["Prefers LeBron over Kobe"]


def test_ground_reply_no_override_when_no_direct_choice() -> None:
    reply, used = _ground_reply_with_memory_preferences(
        "You seem reflective today.",
        user_text="How's my week looking?",
        memory_fact_texts=["Prefers LeBron over Kobe"],
    )
    assert reply == "You seem reflective today."
    assert used == []
