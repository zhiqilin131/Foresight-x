# Foresight-X — Technical Architecture (for Cursor)

> This document is the build spec. Cursor should read this end-to-end before generating code.
> Every component has a file path, data contract, and implementation note.

**Completion alignment:** Product spec **§9** lists four demo gates (7 sections, Tavily, memory, harness delta). This doc’s **§7 Minimum Viable Demo** and **§11 What "Done" Looks Like** are the implementation-side contract. **v0 Harness minimum:** outcome JSON + memory re-index; anything beyond that is stretch.

---

## 0. Tech Stack (locked)

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| LLM | **OpenAI API** (`llama-index-llms-openai` / `llama-index-embeddings-openai`); optional `OPENAI_API_BASE` for Azure or proxies |
| RAG framework | **LlamaIndex** |
| Web retrieval | **Tavily** |
| Vector store | **Chroma** (persistent, via `llama-index-vector-stores-chroma`) |
| Orchestration | **LlamaIndex Workflows** (or LangGraph if team prefers) |
| State validation | Pydantic v2 |
| Storage | Local JSON/SQLite for decision logs; Chroma persist dir under `data/chroma` |
| UI | FastAPI + minimal HTML, or Streamlit for speed |
| Observability | `structlog` + JSON trace dumps |

---

## 1. Architectural Pattern: RIS + Harness

**RIS pipeline** — the core reasoning cycle:

```
R (Retrieve)  →  I (Infer)  →  S (Simulate)  →  Decide
     ↑                                              │
     └──────────── Harness feedback ←───────────────┘
```

- **R (Retrieve):** Memory (LlamaIndex) + World (LlamaIndex + Tavily)
- **I (Infer):** Structured state, irrationality detection, option generation
- **S (Simulate):** Multi-future scenarios + evaluation

**Harness Engineering** — the scaffolding *around* the RIS pipeline:

- Input validation & state contracts (Pydantic)
- Tool-call orchestration (LlamaIndex Workflows)
- Decision trace capture (every step logged)
- Evaluation harness (metrics on captured traces)
- Outcome collection & memory write-back
- Self-improvement hooks (prompt/weight adjustment — **stretch**; v0 = memory write-back only)

Treat Harness as the **production-grade wrapper** that makes an LLM behave like a reliable agent, not a one-shot prompt.

---

## 2. File Structure

```
foresight_x/
├── README.md
├── pyproject.toml                 # or requirements.txt
├── .env.example                   # ANTHROPIC_API_KEY, TAVILY_API_KEY, ...
│
├── foresight_x/
│   ├── __init__.py
│   │
│   ├── schemas.py                 # ALL Pydantic models (single source of truth)
│   │
│   ├── config.py                  # settings, model IDs, paths
│   │
│   ├── perception/
│   │   ├── __init__.py
│   │   └── layer.py               # raw input → UserState
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── memory.py              # LlamaIndex user-memory index
│   │   ├── world_cache.py         # LlamaIndex world-knowledge cache
│   │   └── tavily_client.py       # Tavily wrapper (live web)
│   │
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── irrationality.py       # bias detector
│   │   └── option_generator.py    # 2–4 options
│   │
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── future_simulator.py    # scenario generation
│   │   └── evaluator.py           # scoring
│   │
│   ├── decision/
│   │   ├── __init__.py
│   │   ├── recommender.py
│   │   └── reflector.py
│   │
│   ├── harness/
│   │   ├── __init__.py
│   │   ├── trace.py               # decision trace capture
│   │   ├── outcome_tracker.py     # user-reported outcomes
│   │   ├── eval_harness.py        # metrics
│   │   └── improvement_loop.py    # memory write-back, prompt tuning hooks
│   │
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── workflow.py            # LlamaIndex Workflow wiring the pipeline
│   │   └── pipeline.py            # synchronous linear fallback (same steps) — ship this if Workflow slips
│   │
│   ├── prompts/
│   │   ├── __init__.py
│   │   ├── perception.py
│   │   ├── irrationality.py
│   │   ├── option_generator.py
│   │   ├── future_simulator.py
│   │   ├── evaluator.py
│   │   ├── recommender.py
│   │   └── reflector.py
│   │
│   └── ui/
│       ├── __init__.py
│       ├── cli.py
│       └── app.py                 # FastAPI or Streamlit
│
├── data/
│   ├── chroma/                    # Chroma persistence root (see CHROMA_PERSIST_DIR)
│   ├── memory/                    # auxiliary files / exports per user
│   ├── world_cache/               # cached external knowledge
│   ├── traces/                    # decision trace JSON dumps
│   └── outcomes/                  # captured outcomes
│
└── tests/
    ├── test_schemas.py
    ├── test_perception.py
    ├── test_retrieval.py
    ├── test_simulation.py
    └── test_workflow_e2e.py
```

---

## 3. Core Data Contracts (`schemas.py`)

Single source of truth. Every module imports from here.

```python
# foresight_x/schemas.py
from __future__ import annotations
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field

# ---------- Perception ----------

class TimePressure(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Reversibility(str, Enum):
    REVERSIBLE = "reversible"
    PARTIAL = "partial"
    IRREVERSIBLE = "irreversible"

class UserState(BaseModel):
    raw_input: str
    goals: list[str]
    time_pressure: TimePressure
    stress_level: int = Field(ge=0, le=10)
    workload: int = Field(ge=0, le=10)
    current_behavior: str                 # e.g. "procrastinating"
    decision_type: str                    # e.g. "career", "academic"
    reversibility: Reversibility
    deadline_hint: str | None = None

# ---------- Retrieval ----------

class PastDecision(BaseModel):
    decision_id: str
    situation_summary: str
    chosen_option: str
    outcome: str | None = None
    outcome_quality: int | None = Field(default=None, ge=1, le=5)
    timestamp: str

class MemoryBundle(BaseModel):
    similar_past_decisions: list[PastDecision]
    behavioral_patterns: list[str]
    prior_outcomes_summary: str

class Fact(BaseModel):
    text: str
    source_url: str | None = None
    confidence: float = Field(ge=0, le=1)

class EvidenceBundle(BaseModel):
    facts: list[Fact]
    base_rates: list[Fact]
    recent_events: list[Fact]

# ---------- Inference ----------

class RationalityReport(BaseModel):
    is_rational_state: bool
    detected_biases: list[str]
    confidence: float = Field(ge=0, le=1)
    recommended_slowdowns: list[str]

class Option(BaseModel):
    option_id: str
    name: str
    description: str
    key_assumptions: list[str]
    cost_of_reversal: Literal["low", "medium", "high"]

# ---------- Simulation ----------

class Scenario(BaseModel):
    label: Literal["best", "base", "worst"]
    trajectory: str                       # narrative
    probability: float = Field(ge=0, le=1)
    key_drivers: list[str]

class SimulatedFuture(BaseModel):
    option_id: str
    time_horizon: str                     # e.g. "3 months"
    scenarios: list[Scenario]

class OptionEvaluation(BaseModel):
    option_id: str
    expected_value_score: float = Field(ge=0, le=10)
    risk_score: float = Field(ge=0, le=10)          # higher = riskier
    regret_score: float = Field(ge=0, le=10)        # higher = more regret if wrong
    uncertainty_score: float = Field(ge=0, le=10)   # higher = less confident
    goal_alignment_score: float = Field(ge=0, le=10)
    rationale: str

# ---------- Decision ----------

class NextAction(BaseModel):
    action: str
    deadline: str | None = None
    artifacts: list[str] = []             # e.g. draft message, checklist

class Recommendation(BaseModel):
    chosen_option_id: str
    reasoning: str                        # cites memory + evidence + simulation
    next_actions: list[NextAction]
    reassessment_triggers: list[str]

class Reflection(BaseModel):
    possible_errors: list[str]
    uncertainty_sources: list[str]
    model_limitations: list[str]
    information_gaps: list[str]
    self_improvement_signal: str          # consumed by Harness

# ---------- Harness ----------

class DecisionTrace(BaseModel):
    decision_id: str
    timestamp: str
    user_state: UserState
    memory: MemoryBundle
    evidence: EvidenceBundle
    rationality: RationalityReport
    options: list[Option]
    futures: list[SimulatedFuture]
    evaluations: list[OptionEvaluation]
    recommendation: Recommendation
    reflection: Reflection

class DecisionOutcome(BaseModel):
    decision_id: str
    user_took_recommended_action: bool
    actual_outcome: str
    user_reported_quality: int = Field(ge=1, le=5)
    reversed_later: bool
    timestamp: str
```

---

## 4. Component Implementation Notes

For each component: inputs, outputs, and what Cursor should generate.

### 4.1 Perception Layer — `perception/layer.py`

Extract `UserState` from raw text using an LLM with **structured output** (Pydantic schema).

```python
def build_user_state(raw_input: str, llm) -> UserState:
    # 1. Prompt LLM with raw_input + system prompt from prompts/perception.py
    # 2. Use llm.structured_predict(UserState, prompt) or equivalent
    # 3. Return validated UserState
```

**Implementation tips:**
- Use LlamaIndex's `llm.structured_predict(UserState, prompt_template)` — it enforces the schema.
- If stress_level / workload are unknown, LLM should estimate from linguistic cues (hedging, urgency words, exclamation density).

---

### 4.2 Memory Module — `retrieval/memory.py`

Per-user LlamaIndex `VectorStoreIndex`.

```python
class UserMemory:
    def __init__(self, user_id: str, persist_dir: str = "data/memory"):
        # Load or create VectorStoreIndex at f"{persist_dir}/{user_id}"
        ...

    def retrieve(self, user_state: UserState, top_k: int = 5) -> MemoryBundle:
        # Build query from decision_type + goals + current_behavior
        # Retrieve top_k documents
        # Parse into PastDecision objects + behavioral_patterns
        ...

    def add_decision(self, trace: DecisionTrace, outcome: DecisionOutcome | None = None):
        # Serialize to a Document, add to index, persist
        ...
```

**What gets indexed:** Each past `DecisionTrace` becomes a `Document` with a natural-language summary as text and the full JSON as metadata. When an outcome arrives, update the document.

---

### 4.3 World Knowledge — `retrieval/world_cache.py` + `tavily_client.py`

Hybrid cache-first + Tavily-fallback.

```python
class WorldKnowledge:
    def __init__(self, cache_dir: str = "data/world_cache"):
        self.cache = VectorStoreIndex(...)     # LlamaIndex over cached facts
        self.tavily = TavilyClient(api_key=...)

    def retrieve(self, user_state: UserState, min_cache_hits: int = 3) -> EvidenceBundle:
        # 1. Build queries from decision_type + goals
        # 2. Hit LlamaIndex cache first
        # 3. If < min_cache_hits or decision is time-sensitive, call Tavily
        # 4. Persist new Tavily results into cache (so next time we skip the call)
        # 5. Return EvidenceBundle
```

**Time-sensitivity rule:** if `user_state.decision_type` involves external state that changes (job market, prices, policies, current events), always call Tavily in addition to cache.

---

### 4.4 Irrationality Detector — `inference/irrationality.py`

Combination of **rule-based heuristics** + **LLM check**.

```python
def detect_irrationality(
    user_state: UserState,
    memory: MemoryBundle,
    llm,
) -> RationalityReport:
    # Rule-based pass (fast, deterministic):
    flags = []
    if user_state.stress_level >= 8 and user_state.reversibility == Reversibility.IRREVERSIBLE:
        flags.append("high_stress_irreversible")
    if user_state.time_pressure == TimePressure.HIGH and user_state.reversibility != Reversibility.REVERSIBLE:
        flags.append("rushed_high_stakes")
    # ... more rules

    # LLM pass (nuanced: sunk cost, emotional framing, goal contradiction)
    llm_flags = llm.structured_predict(
        RationalityReport,
        prompt_template_with(user_state, memory, flags),
    )

    # Merge
    return merge(flags, llm_flags)
```

---

### 4.5 Option Generator — `inference/option_generator.py`

```python
def generate_options(
    user_state: UserState,
    memory: MemoryBundle,
    evidence: EvidenceBundle,
    llm,
) -> list[Option]:
    # LLM structured_predict → list[Option]
    # Constraints in prompt:
    #   - produce 2 to 4 options
    #   - at least one must NOT be explicitly in the raw input
    #   - options must be mutually distinct (not rephrasings)
```

---

### 4.6 Future Simulator — `simulation/future_simulator.py`

For each option, generate `SimulatedFuture` with best/base/worst scenarios.

```python
def simulate_futures(
    options: list[Option],
    user_state: UserState,
    evidence: EvidenceBundle,
    llm,
) -> list[SimulatedFuture]:
    futures = []
    for opt in options:
        fut = llm.structured_predict(
            SimulatedFuture,
            prompt=futures_prompt(opt, user_state, evidence),
        )
        # Validate: probabilities sum to 1.0 (±0.05)
        futures.append(fut)
    return futures
```

**Key prompt engineering:** Explicitly ask the LLM to ground each scenario in at least one `Fact` from `evidence` by citing it.

---

### 4.7 Evaluator — `simulation/evaluator.py`

```python
def evaluate_options(
    futures: list[SimulatedFuture],
    user_state: UserState,
    llm,
) -> list[OptionEvaluation]:
    # For each SimulatedFuture:
    #   expected_value_score = weighted sum over scenarios
    #   risk_score = variance / tail risk
    #   regret_score = max loss if this option is wrong
    #   uncertainty_score = derived from LLM confidence + evidence coverage
    #   goal_alignment_score = match against user_state.goals
    #
    # LLM fills rationale per dimension (structured_predict).
```

Keep a **weights config** (`config.py`) per decision_type so the Harness loop can tune them later.

---

### 4.8 Recommender — `decision/recommender.py`

```python
def recommend(
    evaluations: list[OptionEvaluation],
    options: list[Option],
    evidence: EvidenceBundle,
    memory: MemoryBundle,
    weights: dict,
    llm,
) -> Recommendation:
    # 1. Compute composite score per option using weights
    # 2. Pick argmax
    # 3. LLM generates reasoning (must cite evidence + memory + simulation)
    # 4. LLM generates next_actions (concrete: drafts, schedules, checklists)
    # 5. LLM generates reassessment_triggers
```

---

### 4.9 Reflector — `decision/reflector.py`

Takes the full trace, returns a `Reflection`. This is the bridge to the Harness.

```python
def reflect(trace: DecisionTrace, llm) -> Reflection:
    # LLM structured_predict over the full trace
    # Specifically ask: where is this most likely wrong?
```

---

### 4.10 Harness — `harness/*.py`

**`trace.py`** — capture every module output into a `DecisionTrace` and dump to `data/traces/{decision_id}.json`.

**`outcome_tracker.py`** — a CLI / UI flow: `ask_outcome(decision_id)` prompts the user, writes `DecisionOutcome`, calls `memory.update_outcome(...)`.

**`eval_harness.py`** — **v0:** optional; stub returning a small JSON or empty report is acceptable. **Post–v0:** batch metrics over traces + outcomes (calibration, regret, action completion, reversal rate, quality distribution).

**`improvement_loop.py`** — **v0 (ship this):** after `outcome_tracker` writes a `DecisionOutcome`, append/update the corresponding document in `UserMemory` and persist. That satisfies product “self-improvement” for hackathon.

**Stretch (only if core is green):** consume `HarnessReport` to re-weight `OptionEvaluation` dimensions, flag prompts, promote `Reflection.possible_errors` into Irrationality rules, re-embed on drift.

---

### 4.11 Orchestration — `orchestration/workflow.py`

Use **LlamaIndex Workflows** (event-driven) to wire the pipeline.

```python
from llama_index.core.workflow import Workflow, step, Event, StartEvent, StopEvent

class PerceivedEvent(Event):    state: UserState
class RetrievedEvent(Event):    memory: MemoryBundle; evidence: EvidenceBundle
class OptionsEvent(Event):      options: list[Option]; rationality: RationalityReport
class SimulatedEvent(Event):    futures: list[SimulatedFuture]
class EvaluatedEvent(Event):    evaluations: list[OptionEvaluation]

class ForesightWorkflow(Workflow):

    @step
    async def perceive(self, ev: StartEvent) -> PerceivedEvent:
        state = build_user_state(ev.raw_input, self.llm)
        return PerceivedEvent(state=state)

    @step
    async def retrieve(self, ev: PerceivedEvent) -> RetrievedEvent:
        mem = self.memory.retrieve(ev.state)
        evi = self.world.retrieve(ev.state)
        return RetrievedEvent(memory=mem, evidence=evi)

    @step
    async def infer(self, ev: RetrievedEvent) -> OptionsEvent:
        rationality = detect_irrationality(ev.state, ev.memory, self.llm)
        options = generate_options(ev.state, ev.memory, ev.evidence, self.llm)
        return OptionsEvent(options=options, rationality=rationality)

    @step
    async def simulate(self, ev: OptionsEvent) -> SimulatedEvent:
        futures = simulate_futures(ev.options, self.state, self.evidence, self.llm)
        return SimulatedEvent(futures=futures)

    @step
    async def evaluate(self, ev: SimulatedEvent) -> EvaluatedEvent:
        evaluations = evaluate_options(ev.futures, self.state, self.llm)
        return EvaluatedEvent(evaluations=evaluations)

    @step
    async def decide(self, ev: EvaluatedEvent) -> StopEvent:
        rec = recommend(ev.evaluations, self.options, self.evidence, self.memory, self.weights, self.llm)
        refl = reflect(self.current_trace, self.llm)
        self.trace.save(rec, refl)                    # Harness capture
        return StopEvent(result={"recommendation": rec, "reflection": refl})
```

(Naming / state-passing will need cleanup — the above is skeletal; Cursor should promote state to a `ctx` object per LlamaIndex Workflows conventions.)

---

## 5. Prompt Design Principles

All prompts live in `prompts/` — separate files per module so the Harness improvement loop can tune them independently.

Every prompt follows this structure:

1. **Role.** "You are the [Module] of Foresight-X, a decision agent."
2. **Objective.** One sentence.
3. **Inputs.** JSON-serialized Pydantic inputs.
4. **Output schema.** Explicit Pydantic schema (enforced by `structured_predict`).
5. **Constraints.**
   - Must cite evidence / memory by ID where relevant.
   - Must not invent facts outside `EvidenceBundle`.
   - Must express uncertainty numerically where the schema demands it.
6. **Anti-patterns.** "Do NOT…" list to prevent known failure modes.

**Critical:** Never concatenate prompts at call sites. Always route through `prompts/*.py` so the Harness can version them.

---

## 6. Build Plan — Hackathon Timeline

Assumes ~48h build window, 2–4 devs, demo due Sunday 11:59am.

### Phase 0 — Setup (2h)

- [ ] Repo init, `pyproject.toml`, `.env.example`
- [ ] Install: `llama-index`, `llama-index-vector-stores-chroma`, `llama-index-llms-openai`, `llama-index-embeddings-openai`, `chromadb`, `tavily-python`, `pydantic`, `fastapi` or `streamlit`
- [ ] Write `schemas.py` **in full** (it's the contract)
- [ ] Smoke test: one LLM call, one Tavily call, one LlamaIndex index build

### Phase 1 — Retrieval spine (4h)

- [ ] `memory.py` — UserMemory class, add/retrieve
- [ ] `world_cache.py` — LlamaIndex cache
- [ ] `tavily_client.py` — thin wrapper
- [ ] Seed memory with 3–5 synthetic past decisions for the demo user
- [ ] Seed world_cache with domain docs relevant to demo scenarios

### Phase 2 — Perception + Inference (4h)

- [ ] `perception/layer.py`
- [ ] `inference/irrationality.py` (rules first, LLM second)
- [ ] `inference/option_generator.py`
- [ ] Unit tests against fixture inputs

### Phase 3 — Simulation + Decision (5h)

- [ ] `simulation/future_simulator.py`
- [ ] `simulation/evaluator.py`
- [ ] `decision/recommender.py`
- [ ] `decision/reflector.py`
- [ ] End-to-end call works on one example, outputs full DecisionTrace

### Phase 4 — Orchestration (3h)

- [ ] `orchestration/workflow.py` (LlamaIndex Workflow) **or** `orchestration/pipeline.py` (sync `asyncio.run` of the same steps) — **at least one must work day-one**
- [ ] Wire all steps, confirm async flow
- [ ] Trace capture into `data/traces/`

### Phase 5 — Harness (4h)

- [ ] `harness/trace.py` (already partially done in workflow)
- [ ] `harness/outcome_tracker.py` — CLI prompt + write-back to memory (**cannot drop for completion**)
- [ ] `harness/eval_harness.py` — **minimal:** optional JSON summary or stub; full calibration is post–v0
- [ ] `harness/improvement_loop.py` — **minimum:** re-index memory after outcome; anything else is stretch

### Phase 6 — UI + Demo polish (4h)

- [ ] `ui/cli.py` (works first)
- [ ] `ui/app.py` — Streamlit preferred for speed; shows the 7-section output + trace JSON expandable
- [ ] Script 2 demos (Demo A: career; Demo B: re-run with outcome)
- [ ] Record backup video in case live demo fails

### Phase 7 — Slide deck (3h)

Slides required:
1. Title + one-line pitch
2. Problem
3. Why existing tools fail
4. RIS pipeline diagram
5. Harness engineering diagram
6. Component tour (1 slide)
7. Demo A (live or video)
8. Demo B — self-improvement visible
9. Tech stack (LlamaIndex, Tavily, Chroma, OpenAI)
10. Ask / next steps

---

## 7. Minimum Viable Demo (if time collapses)

**Priority order (build in this sequence):**  
`schemas.py` → retrieval (memory + Tavily) → perception + inference + simulation + decision → **trace JSON** → CLI → Harness write-back → polish UI.

If Phase 5 (Harness) slips, fall back to this cut:

1. Perception → Retrieval (memory + Tavily) → Options → Simulation → Recommendation → Reflection — **end to end working** (use `pipeline.py` if Workflow breaks)
2. Harness shown as **a trace JSON** saved to disk, with a printed `HarnessReport` or stub on a **pre-seeded fake-outcome file**
3. Self-improvement explained in slides if live delta is weak — **but** still show two memory states (pre-seeded v1 vs v2) so Demo B has a visible story

**Never drop for “complete” (matches product §9):** **Tavily live call** in trace, **memory retrieval** in trace, **7 UI sections**, and a **credible harness story** (live write-back **or** side-by-side pre-seeded memory).

---

## 8. Environment Variables (`.env.example`)

See repository `.env.example`. Summary:

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL` — LLM + embeddings for LlamaIndex
- Optional `OPENAI_API_BASE` — Azure OpenAI or custom gateway
- `TAVILY_API_KEY` — live web retrieval (demo gate)
- `CHROMA_PERSIST_DIR` — Chroma database directory (default `./data/chroma`)

---

## 9. Testing Strategy (minimal)

- `tests/test_schemas.py` — Pydantic round-trips
- `tests/test_retrieval.py` — memory add/retrieve, Tavily mock
- `tests/test_workflow_e2e.py` — one full run on a fixture input, assert a valid `DecisionTrace` is produced

Don't over-invest in tests during the hackathon. The `DecisionTrace` being valid Pydantic at the end is the main integration test.

---

## 10. Known Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Tavily rate limits during demo | Cache aggressively; have pre-fetched results as fallback |
| LLM structured output fails on complex schemas | Break complex schemas into smaller nested calls |
| LlamaIndex Workflow bugs under time pressure | Have a synchronous fallback `pipeline.py` that just calls each step in order |
| Demo goes live and network flakes | Pre-record video of demo as backup |
| Self-improvement loop doesn't show visible change | Pre-seed two decision histories (v1 memory vs v2 memory) to guarantee a visible delta |

---

## 11. What "Done" Looks Like

A single command runs end-to-end:

```bash
python -m foresight_x.ui.cli "I got an offer from Company X, they want an answer by Friday..."
```

Outputs (completion checklist):
- The **7** strict sections in console (or Streamlit)
- `data/traces/{decision_id}.json` on disk with **Tavily** and **memory** steps visible inside
- `python -m foresight_x.ui.cli --record-outcome {decision_id}` (or equivalent) persists outcome and **re-indexes memory** so a follow-up run is not identical — if automation is flaky, ship **pre-seeded** `data/memory/demo_user` variants for Demo B and document the fallback in README

**Not required for done:** full calibration metrics, automated prompt tuning, LangGraph migration.

---

## 12. Notes for Cursor

- **Start with `schemas.py`.** Every other file imports from it. Don't drift.
- **Use `structured_predict`** on the LlamaIndex LLM wrapper for every LLM call that produces a typed output. Don't hand-roll JSON parsing.
- **Never inline prompts.** Route through `prompts/*.py`.
- **Log every module output** to the in-memory `DecisionTrace` — don't wait until the end to assemble it.
- **Prefer async** throughout the workflow; use `asyncio.gather` for parallelizable steps (memory retrieval + world retrieval).
- **Stub Tavily behind an interface** so tests can mock it cleanly.
- **Keep `improvement_loop.py` tiny but real** — at minimum, after an outcome is recorded, the memory index updates so retrieval changes. Indexing a new `DecisionTrace` without an outcome also counts for “one more document,” but **prefer** outcome write-back to match the product story.
