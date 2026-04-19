"""Per-user decision memory: Chroma + LlamaIndex -> `MemoryBundle`.

**Indexing:** past decisions are inserted when an outcome is recorded via
:func:`foresight_x.harness.improvement_loop.apply_outcome_to_memory` (not at raw
trace save time).

Retrieval uses a **vector candidate set**, then **re-ranks** by combining:
embedding relevance, **exponential time decay** on ``timestamp``, and a simple
**priority overlap** boost from :func:`profile_snippet_for_retrieval` vs document
text. This pattern aligns with production hybrid systems (e.g. RRF-style rank
fusion, temporal decay, multi-signal ranking); see Reciprocal Rank Fusion and
learning-to-rank over multi-channel retrieval for background.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any

import chromadb
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from foresight_x.config import Settings, load_settings
from foresight_x.retrieval._embeddings import build_openai_embedding
from foresight_x.retrieval.query_text import profile_snippet_for_retrieval
from foresight_x.schemas import (
    DecisionOutcome,
    DecisionTrace,
    MemoryBundle,
    PastDecision,
    UserState,
)


def _sanitize_id(user_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id.strip())[:120]


def _collection_name(user_id: str) -> str:
    return f"fx_mem_{_sanitize_id(user_id)}"


def _chroma_metadata(meta: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """Chroma accepts only scalar metadata; encode structures as JSON strings."""
    out: dict[str, str | int | float | bool] = {}
    for key, val in meta.items():
        if val is None:
            continue
        if isinstance(val, (str, int, float, bool)):
            out[key] = val
        else:
            out[key] = json.dumps(val, ensure_ascii=False)
    return out


def _parse_iso_timestamp(raw: str) -> datetime | None:
    if not raw or not str(raw).strip():
        return None
    t = str(raw).strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _recency_multiplier(ts: str, *, now: datetime | None = None) -> float:
    """Exponential decay by age; missing timestamps get a neutral weight."""
    dt = _parse_iso_timestamp(ts)
    if dt is None:
        return 0.9
    n = now or datetime.now(timezone.utc)
    age_days = max(0.0, (n - dt).total_seconds() / 86400.0)
    # Half-life ~60 days at default decay
    return math.exp(-0.0115 * age_days)


def _priority_word_overlap(profile_snippet: str, doc_text: str) -> float:
    """Cheap alignment signal: shared content words vs profile priorities (0–1)."""
    pw = {w for w in re.findall(r"[a-zA-Z]{4,}", profile_snippet.lower())}
    dw = {w for w in re.findall(r"[a-zA-Z]{4,}", doc_text.lower())}
    if not pw:
        return 0.0
    inter = len(pw & dw)
    return min(1.0, inter / max(6.0, len(pw) * 0.45))


def _is_packaged_seed_meta(md: dict[str, Any]) -> bool:
    """True for demo JSON ingest or legacy ``seed-*`` ids (no re-index required)."""
    v = md.get("packaged_seed")
    if v is True or v == 1 or str(v).lower() in ("true", "1", "yes"):
        return True
    did = str(md.get("decision_id", "") or "")
    return did.startswith("seed-")


def _packaged_seed_memory_multiplier(user_state: UserState, md: dict[str, Any]) -> float:
    """Downrank packaged demo memories when the current decision is off-topic."""
    if not _is_packaged_seed_meta(md):
        return 1.0
    dt = (user_state.decision_type or "general").lower()
    if dt in ("career", "academic"):
        return 0.9
    if dt in ("financial", "health"):
        return 0.52
    return 0.28


def _normalize_retriever_score(score: float | None, rank: int) -> float:
    """Map retriever score to (0,1]; handle cosine-like vs distance-like values."""
    if score is None:
        return 1.0 / (rank + 1)
    s = float(score)
    if 0.0 <= s <= 1.0:
        return max(0.04, s)
    if s > 1.0:
        return max(0.04, 1.0 / (1.0 + s))
    return max(0.04, min(1.0, s))


def _node_document_text(node: Any) -> str:
    n = getattr(node, "node", None)
    if n is not None:
        return str(getattr(n, "text", "") or "")
    return str(getattr(node, "text", "") or "")


def _decode_meta(md: dict[str, Any]) -> dict[str, Any]:
    out = dict(md)
    raw = out.get("behavioral_patterns_json")
    if isinstance(raw, str) and raw:
        try:
            out["behavioral_patterns"] = json.loads(raw)
        except json.JSONDecodeError:
            out["behavioral_patterns"] = []
    return out


class UserMemory:
    """Persisted vector index of past decisions for one user."""

    def __init__(
        self,
        user_id: str,
        *,
        settings: Settings | None = None,
        embed_model: BaseEmbedding | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.user_id = user_id
        self.settings = settings or load_settings()
        self.embed_model = embed_model or build_openai_embedding(self.settings)
        self._collection_key = collection_name or _collection_name(user_id)

        self.settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.settings.chroma_persist_dir))
        self._collection = self._client.get_or_create_collection(name=self._collection_key)
        store = ChromaVectorStore(chroma_collection=self._collection)
        ctx = StorageContext.from_defaults(vector_store=store)
        self._index = VectorStoreIndex.from_vector_store(
            vector_store=store,
            storage_context=ctx,
            embed_model=self.embed_model,
        )

    def remove_by_decision_id(self, decision_id: str) -> None:
        """Delete indexed chunks for a decision (e.g. before re-indexing with an outcome)."""
        if not decision_id.strip():
            return
        self._collection.delete(where={"decision_id": decision_id})

    def add_past_decision(
        self,
        past: PastDecision,
        *,
        behavioral_patterns: list[str] | None = None,
        packaged_seed: bool = False,
    ) -> None:
        lines = [
            past.situation_summary,
            f"Chosen option: {past.chosen_option}",
        ]
        if past.outcome:
            lines.append(f"Outcome: {past.outcome}")
        text = "\n".join(lines)
        meta: dict[str, Any] = {
            "kind": "past_decision",
            "decision_id": past.decision_id,
            "situation_summary": past.situation_summary,
            "chosen_option": past.chosen_option,
            "outcome": past.outcome or "",
            "outcome_quality": past.outcome_quality if past.outcome_quality is not None else -1,
            "timestamp": past.timestamp,
        }
        if behavioral_patterns:
            meta["behavioral_patterns_json"] = json.dumps(behavioral_patterns, ensure_ascii=False)
        if packaged_seed:
            meta["packaged_seed"] = True
        self._index.insert(Document(text=text, metadata=_chroma_metadata(meta)))

    def add_decision(self, trace: DecisionTrace, outcome: DecisionOutcome | None = None) -> None:
        label = next(
            (o.name for o in trace.options if o.option_id == trace.recommendation.chosen_option_id),
            trace.recommendation.chosen_option_id,
        )
        past = PastDecision(
            decision_id=trace.decision_id,
            situation_summary=trace.user_state.raw_input[:2000],
            chosen_option=label,
            outcome=outcome.actual_outcome if outcome else None,
            outcome_quality=outcome.user_reported_quality if outcome else None,
            timestamp=outcome.timestamp if outcome else trace.timestamp,
        )
        patterns = list(trace.memory.behavioral_patterns) if trace.memory else []
        self.add_past_decision(past, behavioral_patterns=patterns or None)

    def list_all_past_decisions(self) -> list[PastDecision]:
        """Return all persisted past decisions for this user, newest first."""
        rows = self._collection.get(include=["metadatas", "documents"])
        metadatas = rows.get("metadatas") or []
        documents = rows.get("documents") or []

        by_decision_id: dict[str, PastDecision] = {}
        for idx, md_raw in enumerate(metadatas):
            md = _decode_meta(dict(md_raw or {}))
            did = str(md.get("decision_id", "") or "").strip()
            if not did:
                continue
            oq = md.get("outcome_quality")
            if isinstance(oq, (int, float)) and int(oq) == -1:
                pq: int | None = None
            elif isinstance(oq, (int, float)):
                pq = int(oq)
            else:
                pq = None

            doc_text = str(documents[idx]) if idx < len(documents) and documents[idx] is not None else ""
            candidate = PastDecision(
                decision_id=did,
                situation_summary=str(md.get("situation_summary", doc_text[:800])),
                chosen_option=str(md.get("chosen_option", "")),
                outcome=str(md.get("outcome")) if md.get("outcome") else None,
                outcome_quality=pq,
                timestamp=str(md.get("timestamp", "")),
            )
            prev = by_decision_id.get(did)
            if prev is None:
                by_decision_id[did] = candidate
                continue
            # Prefer the entry with the newer valid timestamp.
            prev_dt = _parse_iso_timestamp(prev.timestamp) or datetime.min.replace(tzinfo=timezone.utc)
            cand_dt = _parse_iso_timestamp(candidate.timestamp) or datetime.min.replace(tzinfo=timezone.utc)
            if cand_dt >= prev_dt:
                by_decision_id[did] = candidate

        out = list(by_decision_id.values())
        out.sort(
            key=lambda p: _parse_iso_timestamp(p.timestamp) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return out

    def retrieve(self, user_state: UserState, top_k: int = 5) -> MemoryBundle:
        extra = profile_snippet_for_retrieval(user_state)
        query = " ".join(
            [
                user_state.decision_type,
                " ".join(user_state.goals),
                user_state.current_behavior,
                extra,
                user_state.raw_input[:1500],
            ]
        )
        fetch_k = min(48, max(top_k * 6, top_k + 12))
        retriever = self._index.as_retriever(similarity_top_k=fetch_k)
        raw_nodes = retriever.retrieve(query)

        combined: list[tuple[float, Any]] = []
        for rank, node in enumerate(raw_nodes):
            md_raw: dict[str, Any] = {}
            inner = getattr(node, "node", None)
            if inner is not None and getattr(inner, "metadata", None) is not None:
                md_raw = dict(inner.metadata)
            score = getattr(node, "score", None)
            sim = _normalize_retriever_score(score, rank)
            md0 = _decode_meta(md_raw)
            ts = str(md0.get("timestamp", "") or "")
            rec = _recency_multiplier(ts)
            doc_bits = " ".join(
                [
                    _node_document_text(node),
                    str(md0.get("situation_summary", "") or ""),
                    str(md0.get("chosen_option", "") or ""),
                ]
            )
            pov = _priority_word_overlap(extra, doc_bits)
            seed_m = _packaged_seed_memory_multiplier(user_state, md0)
            # Relevance × time decay × (1 + priority alignment) × seed-topic match
            fuse = sim * (0.42 + 0.58 * rec) * (1.0 + 0.38 * pov) * seed_m
            combined.append((fuse, node))

        combined.sort(key=lambda x: x[0], reverse=True)
        nodes = [n for _, n in combined[:top_k]]

        pasts: list[PastDecision] = []
        patterns_acc: list[str] = []
        outcome_snippets: list[str] = []
        seen_pat: set[str] = set()

        for node in nodes:
            md_raw = {}
            inner = getattr(node, "node", None)
            if inner is not None and getattr(inner, "metadata", None) is not None:
                md_raw = dict(inner.metadata)
            md = _decode_meta(md_raw)
            if md.get("kind") != "past_decision" and not md.get("decision_id"):
                continue
            did = md.get("decision_id")
            if not did:
                continue
            oq = md.get("outcome_quality")
            if isinstance(oq, (int, float)) and int(oq) == -1:
                pq: int | None = None
            elif isinstance(oq, (int, float)):
                pq = int(oq)
            else:
                pq = None

            snippet_fallback = _node_document_text(node)[:800]
            pasts.append(
                PastDecision(
                    decision_id=str(did),
                    situation_summary=str(md.get("situation_summary", snippet_fallback)),
                    chosen_option=str(md.get("chosen_option", "")),
                    outcome=str(md["outcome"]) if md.get("outcome") else None,
                    outcome_quality=pq,
                    timestamp=str(md.get("timestamp", "")),
                )
            )
            bplist = md.get("behavioral_patterns")
            if isinstance(bplist, list):
                for p in bplist:
                    s = str(p)
                    if s not in seen_pat:
                        seen_pat.add(s)
                        patterns_acc.append(s)
            outv = md.get("outcome")
            if outv:
                outcome_snippets.append(str(outv))

        summary = (
            " ".join(outcome_snippets[:6])
            if outcome_snippets
            else "No strong outcome signal in top retrieved memories."
        )
        return MemoryBundle(
            similar_past_decisions=pasts,
            behavioral_patterns=patterns_acc,
            prior_outcomes_summary=summary[:2000],
        )
