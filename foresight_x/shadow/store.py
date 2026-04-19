"""Persist a growing \"shadow\" model of the user's patterns (chat-only space)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from foresight_x.config import Settings, load_settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ShadowSelfState(BaseModel):
    user_id: str
    narrative: str = ""
    observations: list[str] = Field(default_factory=list)
    updated_at: str = ""
    turn_count: int = 0


def _shadow_path(user_id: str, settings: Settings) -> Path:
    root = settings.foresight_data_dir / "shadow_self"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{user_id}.json"


def load_shadow_self(*, settings: Settings | None = None, user_id: str | None = None) -> ShadowSelfState:
    s = settings or load_settings()
    uid = user_id or s.foresight_user_id
    path = _shadow_path(uid, s)
    if not path.exists():
        return ShadowSelfState(user_id=uid, updated_at=_utc_now())
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ShadowSelfState.model_validate(raw)


def save_shadow_self(state: ShadowSelfState, *, settings: Settings | None = None) -> Path:
    s = settings or load_settings()
    state = state.model_copy(update={"updated_at": _utc_now()})
    path = _shadow_path(state.user_id, s)
    path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return path


def merge_observation(state: ShadowSelfState, observation: str, *, max_observations: int = 48) -> ShadowSelfState:
    """Append a single new observation line; trim oldest when over cap."""
    obs = observation.strip()
    if not obs:
        return state
    merged = list(state.observations)
    merged.append(obs)
    if len(merged) > max_observations:
        merged = merged[-max_observations:]
    narrative = "\n".join(f"• {o}" for o in merged[-24:])
    return state.model_copy(
        update={
            "observations": merged,
            "narrative": narrative,
            "turn_count": state.turn_count + 1,
        }
    )
