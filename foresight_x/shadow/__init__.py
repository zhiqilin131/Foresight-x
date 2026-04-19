"""Shadow chat: dialogue with the user's shadow self for behavioral understanding (not decision advice).

``run_shadow_turn`` lives in ``foresight_x.shadow.chat`` — not re-exported here to avoid import cycles
(``shadow.chat`` → ``orchestration`` → ``pipeline`` → ``user_recent_context`` → ``shadow.store``).
"""

from foresight_x.shadow.store import ShadowSelfState, load_shadow_self, merge_observation, save_shadow_self

__all__ = [
    "ShadowSelfState",
    "load_shadow_self",
    "merge_observation",
    "save_shadow_self",
]
