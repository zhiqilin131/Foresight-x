"""Rank fusion for ``recent_events``: memory + trace history + Shadow notes.

Uses **Reciprocal Rank Fusion (RRF)** — score(d) = Σ 1/(k + rank(d)) across ranked
lists — a standard way to merge hybrid retrieval channels (industry default k≈60;
see hybrid-search / Azure AI Search docs). For Shadow lines we apply a
**Maximal Marginal Relevance (MMR)**-style selection (Carbonell & Goldstein, 1998):
relevance to the current decision minus redundancy vs already picked lines, so
the UI is not flooded with near-duplicate reflective notes.
"""

from __future__ import annotations

import re
from foresight_x.config import Settings
from foresight_x.harness.outcome_tracker import load_decision_outcome_optional
from foresight_x.harness.trace import load_decision_trace
from foresight_x.harness.trace_index import list_traces
from foresight_x.retrieval.memory_query import build_memory_retrieval_query
from foresight_x.retrieval.query_text import profile_fact_line_for_recent_events
from foresight_x.schemas import DecisionOutcome, DecisionTrace, Fact, MemoryBundle, UserState

_RRF_K = 60
_MAX_DECISION_FACTS = 8
_MAX_SHADOW_FACTS = 4


def _word_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z]{3,}", (text or "").lower())}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def reciprocal_rank_fusion(rank_lists: list[list[str]], *, k: int = _RRF_K) -> list[tuple[str, float]]:
    """Merge ordered ID lists; higher score = stronger consensus / rank across lists."""
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for rank, doc_id in enumerate(lst, start=1):
            did = str(doc_id).strip()
            if not did:
                continue
            scores[did] = scores.get(did, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _relevance_to_query(query: str, line: str) -> float:
    q = _word_set(query)
    w = _word_set(line)
    if not q:
        return 0.25
    return min(1.0, len(q & w) / max(12.0, len(q) * 0.35))


def mmr_select_shadow_lines(lines: list[str], query: str, *, k: int, lambda_mult: float = 0.72) -> list[str]:
    """Pick up to ``k`` Shadow lines: balance query relevance vs diversity (MMR)."""
    candidates = [(s.strip(), _relevance_to_query(query, s)) for s in lines if (s or "").strip()]
    candidates.sort(key=lambda x: x[1], reverse=True)
    # consider a wider pool then MMR-trim
    pool = candidates[: min(24, len(candidates))]
    selected: list[str] = []
    remaining = list(pool)
    while remaining and len(selected) < k:
        best_i = -1
        best_mmr = -1.0
        for i, (text, rel) in enumerate(remaining):
            tset = _word_set(text)
            div = 0.0
            if selected:
                div = max(_jaccard(tset, _word_set(s)) for s in selected)
            mmr = lambda_mult * rel - (1.0 - lambda_mult) * div
            if mmr > best_mmr:
                best_mmr = mmr
                best_i = i
        if best_i < 0:
            break
        chosen = remaining.pop(best_i)[0]
        selected.append(chosen)
    return selected


def _chosen_option_label(trace: DecisionTrace) -> str:
    rid = trace.recommendation.chosen_option_id
    for o in trace.options:
        if o.option_id == rid:
            return o.name
    return str(rid)


def _list_outcome_ids_recency(settings: Settings) -> list[str]:
    """Newest outcome files first, **only** for decisions whose trace is visible to the current user.

    Global outcome scans would leak other personas' decision_ids into RRF; :func:`~foresight_x.harness.trace_index.list_traces`
    already enforces ``active_user_id`` (see trace JSON). We intersect with that set.
    """
    allowed = {t.decision_id for t in list_traces(settings=settings)}
    if not allowed:
        return []
    root = settings.outcomes_dir
    if not root.is_dir():
        return []
    rows: list[tuple[str, str]] = []
    for path in root.glob("*.json"):
        stem = path.stem
        if stem not in allowed:
            continue
        try:
            o = DecisionOutcome.model_validate_json(path.read_text(encoding="utf-8"))
            rows.append((o.timestamp, stem))
        except (OSError, ValueError):
            continue
    rows.sort(key=lambda x: x[0], reverse=True)
    return [s for _, s in rows]


def _format_decision_fact(
    *,
    decision_id: str,
    memory_rank: int | None,
    decision_type: str,
    timestamp: str,
    situation: str,
    chosen: str | None,
    outcome: DecisionOutcome | None,
) -> tuple[str, float]:
    sit = " ".join((situation or "").split())[:420]
    mem_tag = f"memory_rank={memory_rank}" if memory_rank is not None else "memory_rank=—"
    head = f"Decision history (id={decision_id} · {mem_tag} · {decision_type} · {timestamp})"
    chosen_bit = f" Chosen: {chosen}." if chosen else ""
    if outcome and (outcome.actual_outcome or "").strip():
        body = (
            f"{sit}{chosen_bit} Recorded outcome: {outcome.actual_outcome.strip()} "
            f"(quality {outcome.user_reported_quality}/5)."
        )
        conf = 0.82 if memory_rank is not None else 0.74
    else:
        body = f"{sit}{chosen_bit} Outcome not recorded yet."
        conf = 0.71 if memory_rank is not None else 0.62
    return f"{head}: {body}", conf


def _decision_query_relevance(query_text: str, *, situation: str, chosen: str | None, decision_type: str) -> float:
    """Lexical relevance between current query and one decision episode."""
    q = _word_set(query_text)
    if not q:
        return 0.0
    doc = " ".join([situation or "", chosen or "", decision_type or ""])
    d = _word_set(doc)
    if not d:
        return 0.0
    inter = len(q & d)
    # Favor direct entity overlap (names/keywords) without over-penalizing long docs.
    base = inter / max(6.0, min(24.0, len(q) * 0.65))
    return max(0.0, min(1.0, base))


def _profile_facts(user_state: UserState) -> list[Fact]:
    """Exact :func:`~foresight_x.retrieval.query_text.profile_snippet_for_retrieval` string (see ``profile_fact_line_for_recent_events``)."""
    line = profile_fact_line_for_recent_events(user_state)
    if not line:
        return []
    return [Fact(text=line, source_url=None, confidence=0.68)]


def build_fused_recent_facts(
    settings: Settings,
    user_state: UserState,
    memory_bundle: MemoryBundle | None,
    *,
    exclude_decision_id: str | None = None,
) -> list[Fact]:
    """Facts for ``recent_events``: profile + MMR Shadow + RRF-ranked decision episodes.

    Order is **profile → shadow → decision history** so thin UIs that only show the first few
    rows still surface global user context, not only episodic lines.
    """
    mem = memory_bundle
    memory_ids = [p.decision_id for p in (mem.similar_past_decisions if mem else []) if p.decision_id]
    memory_rank: dict[str, int] = {did: i + 1 for i, did in enumerate(memory_ids)}

    traces = list_traces(settings=settings)
    trace_order = [t.decision_id for t in traces]
    outcome_order = _list_outcome_ids_recency(settings)

    rank_lists = [memory_ids, trace_order, outcome_order]
    fused = reciprocal_rank_fusion(rank_lists)

    query_text = build_memory_retrieval_query(user_state)
    facts: list[Fact] = []
    facts.extend(_profile_facts(user_state))

    # Shadow before decision rows so a 5-item UI cap still shows reflective notes when present.
    from foresight_x.shadow.store import load_shadow_self

    shadow = load_shadow_self(settings=settings)
    obs = [str(x).strip() for x in (shadow.observations or []) if str(x).strip()]
    for line in mmr_select_shadow_lines(obs, query_text, k=_MAX_SHADOW_FACTS):
        facts.append(
            Fact(
                text=f"Shadow (reflective chat) note: {_truncate(line, 480)}",
                source_url=None,
                confidence=0.52,
            )
        )

    seen_ids: set[str] = set()
    decision_rows: list[tuple[float, Fact]] = []

    for did, rrf in fused:
        if not did or did in seen_ids:
            continue
        if exclude_decision_id and did == exclude_decision_id:
            continue
        seen_ids.add(did)

        row = next((t for t in traces if t.decision_id == did), None)
        preview = row.preview if row else ""
        ts = row.timestamp if row else ""
        dt = row.decision_type if row else "unknown"

        trace: DecisionTrace | None = None
        try:
            trace = load_decision_trace(did, settings=settings)
        except Exception:
            pass

        situation = ""
        chosen: str | None = None
        if trace is not None:
            situation = (trace.user_state.raw_input or "")[:600]
            dt = trace.user_state.decision_type or dt
            ts = trace.timestamp or ts
            try:
                chosen = _chosen_option_label(trace)
            except Exception:
                chosen = None
        if not situation.strip():
            situation = preview

        outcome = load_decision_outcome_optional(did, settings=settings)
        text, conf = _format_decision_fact(
            decision_id=did,
            memory_rank=memory_rank.get(did),
            decision_type=str(dt),
            timestamp=str(ts)[:32],
            situation=situation,
            chosen=chosen,
            outcome=outcome,
        )
        rel = _decision_query_relevance(
            query_text,
            situation=situation,
            chosen=chosen,
            decision_type=str(dt),
        )
        memory_boost = 0.13 if memory_rank.get(did) is not None else 0.0
        final_rank = float(rrf) + 0.92 * rel + memory_boost
        decision_rows.append((final_rank, Fact(text=text, source_url=None, confidence=min(0.9, conf + 0.08 * rel))))

    decision_rows.sort(key=lambda x: x[0], reverse=True)
    for _, fact in decision_rows[:_MAX_DECISION_FACTS]:
        facts.append(fact)

    return facts


def _truncate(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"
