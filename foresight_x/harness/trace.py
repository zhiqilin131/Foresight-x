"""Persist `DecisionTrace` to disk for demos and Harness."""

from __future__ import annotations

from pathlib import Path

from foresight_x.config import Settings, load_settings
from foresight_x.schemas import DecisionTrace


def save_decision_trace(
    trace: DecisionTrace,
    *,
    settings: Settings | None = None,
    traces_dir: Path | None = None,
) -> Path:
    """Write trace JSON to ``data/traces/{decision_id}.json`` (or ``traces_dir``)."""
    s = settings or load_settings()
    root = traces_dir if traces_dir is not None else s.traces_dir
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{trace.decision_id}.json"
    path.write_text(trace.model_dump_json(indent=2), encoding="utf-8")
    return path
