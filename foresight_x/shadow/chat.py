"""One turn of shadow chat: therapist-leaning tone, no decisions; updates shadow notes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from foresight_x.config import Settings, load_settings
from foresight_x.orchestration.llm_factory import build_openai_llm
from foresight_x.shadow.store import ShadowSelfState, load_shadow_self, merge_observation, save_shadow_self
from foresight_x.structured_predict import structured_predict


class ShadowChatTurn(BaseModel):
    reply_to_user: str = Field(
        description=(
            "Your next message to the user. Warm, curious, therapist-like researcher and friend. "
            "Do not recommend a specific decision, option, or plan. No numbered action lists for "
            "what they should do. Reflect feelings, ask gentle questions, share brief human warmth."
        )
    )
    suggest_decision_navigation: bool = Field(
        description=(
            "True only if the user is clearly asking for a concrete decision, which option to pick, "
            "or to run the Foresight / decision analysis mode."
        )
    )
    shadow_observation: str = Field(
        default="",
        description=(
            "At most one short bullet (max 220 chars) noting a behavior or emotional pattern "
            "you noticed this turn. Empty string if nothing new or uncertain."
        ),
    )


def _format_transcript(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for m in messages:
        role = str(m.get("role", "")).strip()
        content = str(m.get("content", "")).strip()
        if role == "system" or not content:
            continue
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


SHADOW_INSTRUCTIONS = """You are in "Shadow space" — a private reflective chat. Your stance:
- Like a skilled therapist-researcher who is also a friend: curious, non-judgmental, present.
- Explore meaning, feelings, and patterns. Short paragraphs; avoid clinical jargon.
- Do NOT give decisions, rankings, "you should", or step-by-step advice for life choices.
- If the user asks what to choose between options, or to analyze a decision, you still respond warmly
  but the structured output will flag that they may want the separate Decision mode — you do not
  decide for them here.
- You may notice behavioral or emotional patterns and record ONE concise observation when genuine.

Current accumulated notes about this user (may be empty):
{shadow_block}

Full conversation so far:
{transcript}

Respond according to the schema: your reply, whether to suggest opening Decision mode, and one optional observation bullet."""


def run_shadow_turn(
    messages: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
) -> tuple[str, bool, ShadowSelfState, str | None]:
    """Return (assistant_reply, suggest_decision_navigation, updated_state, recorded_observation_or_none)."""
    s = settings or load_settings()
    if not messages:
        raise ValueError("messages must be non-empty")
    last = messages[-1]
    if str(last.get("role")) != "user":
        raise ValueError("last message must be from user")

    if not (s.openai_api_key or "").strip():
        raise RuntimeError("OPENAI_API_KEY is required for shadow chat")

    llm = build_openai_llm(s, temperature=0.68)

    state = load_shadow_self(settings=s)
    shadow_block = state.narrative.strip() or "(none yet — first turns.)"
    transcript = _format_transcript(messages)

    prompt = SHADOW_INSTRUCTIONS.format(shadow_block=shadow_block, transcript=transcript)
    turn = structured_predict(llm, ShadowChatTurn, prompt)

    reply = turn.reply_to_user.strip()
    flag = bool(turn.suggest_decision_navigation)
    obs = (turn.shadow_observation or "").strip()
    if len(obs) > 220:
        obs = obs[:217] + "…"

    recorded: str | None = None
    if obs:
        state = merge_observation(state, obs)
        recorded = obs
    else:
        state = state.model_copy(update={"turn_count": state.turn_count + 1})
    save_shadow_self(state, settings=s)

    return reply, flag, state, recorded
