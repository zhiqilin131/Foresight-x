"""Shadow chat: reflective dialogue and behavioral understanding (not decision advice)."""

from foresight_x.shadow.chat import run_shadow_turn
from foresight_x.shadow.store import ShadowSelfState, load_shadow_self, merge_observation, save_shadow_self

__all__ = [
    "ShadowSelfState",
    "load_shadow_self",
    "merge_observation",
    "run_shadow_turn",
    "save_shadow_self",
]
