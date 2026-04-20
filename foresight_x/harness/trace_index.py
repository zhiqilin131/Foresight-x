"""List and delete persisted traces; keep outcomes directory consistent."""

from __future__ import annotations

import json
import re
from pathlib import Path

from foresight_x.config import Settings, load_settings
from foresight_x.harness.decision_commit import delete_commit
from foresight_x.schemas import TraceListItem

_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


def _validate_decision_id(decision_id: str) -> None:
    if not _SAFE_ID.match(decision_id or ""):
        raise ValueError("invalid decision_id")


def list_traces(*, settings: Settings | None = None) -> list[TraceListItem]:
    s = settings or load_settings()
    root = s.traces_dir
    current_user = (s.foresight_user_id or "").strip()
    if not root.is_dir():
        return []
    out: list[TraceListItem] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        did = data.get("decision_id")
        ts = data.get("timestamp")
        us = data.get("user_state") or {}
        if not isinstance(did, str) or not isinstance(ts, str):
            continue
        if isinstance(us, dict):
            trace_user = str(us.get("active_user_id", "") or "").strip()
            if current_user:
                if trace_user:
                    if trace_user != current_user:
                        continue
                else:
                    # Legacy traces without active_user_id were previously visible to every persona.
                    # Only the shared demo sandbox keeps that behavior; named personas must not see
                    # other users' unscoped history.
                    if current_user != "demo_user":
                        continue
        raw = us.get("raw_input") if isinstance(us, dict) else ""
        preview = (raw or "")[:160].replace("\n", " ")
        dt = us.get("decision_type", "") if isinstance(us, dict) else ""
        out.append(
            TraceListItem(
                decision_id=did,
                timestamp=ts,
                decision_type=str(dt) if dt else "unknown",
                preview=preview,
                has_outcome=(s.outcomes_dir / f"{did}.json").is_file(),
                has_commit=(s.commits_dir / f"{did}.json").is_file(),
            )
        )
    return out


def delete_trace(decision_id: str, *, settings: Settings | None = None) -> tuple[bool, bool, bool]:
    """Remove trace, outcome, and commit files if present. Returns (trace_deleted, outcome_deleted, commit_deleted)."""
    _validate_decision_id(decision_id)
    s = settings or load_settings()
    trace_path = s.traces_dir / f"{decision_id}.json"
    outcome_path = s.outcomes_dir / f"{decision_id}.json"
    td = False
    od = False
    if trace_path.is_file():
        trace_path.unlink()
        td = True
    if outcome_path.is_file():
        outcome_path.unlink()
        od = True
    cd = delete_commit(decision_id, settings=s)
    return td, od, cd
