"""Shared fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_user_state_dict() -> dict:
    return {
        "raw_input": "Offer from Company X, deadline Friday.",
        "goals": ["maximize career growth", "minimize regret"],
        "time_pressure": "high",
        "stress_level": 7,
        "workload": 6,
        "current_behavior": "rushed",
        "decision_type": "career",
        "reversibility": "partial",
        "deadline_hint": "Friday 5pm",
    }
