# Foresight-X — Product Specification

> **Foresight-X** is a self-improving, evidence-grounded decision agent.
> It is **not** a chatbot. It is a decision system optimized for **decision quality**, not user satisfaction.

**Hackathon completion contract (v0 must ship):** See **§9** and **§10**. If time runs short, **§10** defines what cannot be dropped versus what may be simplified. The technical companion doc (`foresight_x_technical_architecture.md`) lists the same gates under *Minimum Viable Demo*.

---

## 1. Executive Summary

Foresight-X helps users make **high-stakes decisions** by combining:

- **Personal memory** (what this user has done before, and how it turned out)
- **World evidence** (external facts, policies, statistics, recent events)
- **Multi-future simulation** (what happens under each option)
- **Self-improvement** (learns from past decision outcomes via a Harness loop)

The system is built on a **RIS pipeline** (Retrieval → Inference → Simulation) wrapped in a **Harness Engineering** layer that handles evaluation, feedback, and self-improvement.

**One-line pitch:**
> Foresight-X is a decision system that retrieves your past, grounds in world evidence, simulates your futures, and improves from every outcome — so you decide better than you would alone.

---

## 2. Problem Statement

Humans make poor high-stakes decisions because:

1. **Cognitive load** under stress collapses option-generation
2. **Recency bias** and **emotion** override evidence
3. **Single-future thinking** ignores counterfactuals
4. **No feedback loop** — people repeat the same mistakes

Existing AI tools don't solve this:

| Tool | Gap |
|------|-----|
| ChatGPT / generic LLM chat | No memory, no evidence grounding, no simulation |
| Notion AI / writing assistants | Content tools, not decision tools |
| Traditional decision-support | Rule-based, no reasoning, no personalization |
| Agent frameworks (LangChain, etc.) | Scaffolding, not decision quality |

Foresight-X fills this gap by being a **decision-quality–first** system.

---

## 3. Target Users & Use Cases

### Primary persona
College students and early-career professionals facing consequential decisions under time pressure.

### Example decisions

| Domain | Example |
|--------|---------|
| Academic | "Should I drop this class or push through the semester?" |
| Career | "Should I accept this internship offer today or wait?" |
| Health (informational only) | "Should I go to urgent care or wait it out?" — **not medical advice**; v0 must surface disclaimers and avoid definitive clinical recommendations |
| Financial | "Should I sign this lease or keep searching?" |
| Interpersonal | "Should I have this difficult conversation today?" |

### Non-goals
- Casual chat / emotional support (not a therapist)
- Trivia / general Q&A (not a search engine)
- Content generation (not a writing tool)
- Licensed professional advice (medical, legal, financial) — v0 provides **decision structure + drafts**, not authoritative diagnoses or binding guidance

---

## 4. Core Value Proposition

Three differentiators vs. generic LLM chat:

1. **Evidence-grounded (best-effort)** — the pipeline **retrieves** memory + world knowledge first and **requires** the recommender to tie claims to those sources in the output schema. LLMs can still err; v0 optimizes for **traceability** (citations, structured trace), not a mathematical guarantee against hallucination.
2. **Multi-future simulation** — generates 2–4 options and projects consequences *before* recommending. Scenario probabilities are **illustrative** (LLM-generated), not calibrated forecasts until enough outcomes exist (post–v0).
3. **Self-improving (v0 = memory + trace)** — Outcome Tracker writes real outcomes back into memory so later retrievals change. Prompt rewrites and evaluation **weight tuning** are **stretch** for hackathon; see §12.

---

## 5. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INPUT                                  │
│         (situation + goals + current state)                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  [1] PERCEPTION LAYER                                            │
│       Converts raw input → structured State object               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  RIS PIPELINE                                                    │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌────────────────┐        │
│  │ R: Retrieve │ → │ I: Inference │ → │ S: Simulation  │        │
│  │             │   │              │   │                │        │
│  │ [2] Memory  │   │ [4] Irration │   │ [6] Future Sim │        │
│  │ [3] World   │   │ [5] Options  │   │ [7] Evaluator  │        │
│  └─────────────┘   └──────────────┘   └────────────────┘        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  [8] RECOMMENDER  → one decision + concrete next actions         │
│  [9] REFLECTOR    → self-critique of reasoning                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  HARNESS ENGINEERING LAYER                                       │
│  [10] Outcome Tracker  [11] Eval Harness  [12] Self-Improvement  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Component Specification

Each component below is described with:
- **Purpose** — what it does in the decision loop
- **Input / Output** — data contract
- **Role** — how it contributes to decision quality

---

### [1] Perception Layer

**Purpose.** Converts unstructured user input into a structured `UserState` object so downstream modules reason over clean signals, not raw text.

**Input.** Free-text situation description + optional explicit signals (mood, deadline).

**Output.** `UserState` — structured fields:
- `goals` (list)
- `time_pressure` (low / medium / high)
- `stress_level` (0–10)
- `workload` (0–10)
- `current_behavior` (e.g., "procrastinating", "impulsive", "overthinking")
- `decision_type` (e.g., "career", "academic", "health")
- `reversibility` (reversible / partially / irreversible)

**Role.** Without structure, every later step re-parses the same ambiguity. Perception forces the system to commit to an interpretation it can defend.

---

### [2] Memory Module — LlamaIndex

**Purpose.** Retrieve **this user's** relevant past decisions and outcomes.

**Implementation.** LlamaIndex `VectorStoreIndex` over a per-user corpus of:
- Past decision records (situation, options considered, chosen option, outcome)
- Behavioral patterns (recurring biases, stress responses)
- Journal-style reflections from the Reflector

**Input.** `UserState` (used to build retrieval query).

**Output.** `MemoryBundle`:
- `similar_past_decisions` (top-k)
- `relevant_behavioral_patterns`
- `prior_outcomes` (what worked / failed)

**Role.** Personalization. Without it, Foresight-X is just a generic advisor.

---

### [3] World Knowledge Module — LlamaIndex + Tavily

**Purpose.** Retrieve external, real-world evidence to ground reasoning and reduce hallucination.

**Implementation.**
- **LlamaIndex** over a cached knowledge base (policies, FAQs, base rates, prior Tavily results)
- **Tavily** for live web retrieval when the cache is insufficient or the query is time-sensitive
- Hybrid strategy: cache-first, Tavily-fallback

**Input.** `UserState` + decision domain.

**Output.** `EvidenceBundle`:
- `retrieved_facts` (with source URLs)
- `relevant_base_rates`
- `recent_events` (from Tavily)
- `confidence_per_fact`

**Role.** Grounds the model in reality. **v0 requirement:** the final recommendation’s reasoning field must **reference** at least one retrieved memory item or evidence fact (by summary or quote), per schema — enforced in prompts and trace review, not by formal proof.

---

### [4] Irrationality Detector

**Purpose.** Detect whether the user is making a potentially irrational decision **before** generating options.

**Heuristics checked:**
- High stress + irreversible decision → flag
- Time pressure + high-stakes → flag
- Sunk-cost framing in user text → flag
- Emotional language dominating factual content → flag
- Contradiction with prior stated goals (from memory) → flag

**Input.** `UserState` + `MemoryBundle`.

**Output.** `RationalityReport`:
- `is_rational_state` (bool)
- `detected_biases` (list)
- `confidence`
- `recommended_slowdowns` (e.g., "sleep on it", "gather X data first")

**Role.** Prevents the system from dutifully optimizing a bad question. A decision agent that helps you execute a mistake faster is worse than no agent.

---

### [5] Option Generator

**Purpose.** Produce **2–4** distinct decision options, including at least one option the user did not explicitly mention.

**Input.** `UserState` + `MemoryBundle` + `EvidenceBundle`.

**Output.** `List[Option]` where each `Option` has:
- `name`
- `description`
- `key_assumptions`
- `cost_of_reversal`

**Role.** Fights single-option tunnel vision — a major failure mode in high-stress decisions.

---

### [6] Future Simulator

**Purpose.** For each option, project plausible outcomes along a time horizon.

**Approach.** LLM-driven scenario generation, conditioned on memory + evidence. For each option, generate:
- **Best-case trajectory** (probability p_best — must sum with others ≈ 1; interpret as model-rough, not empirical)
- **Base-case trajectory** (probability p_base)
- **Worst-case trajectory** (probability p_worst)

**Input.** `List[Option]` + `UserState` + `EvidenceBundle`.

**Output.** `List[SimulatedFuture]` per option:
- `scenarios` (list of {trajectory, probability, key_drivers})
- `time_horizon`

**Role.** Forces the system to think in distributions, not point predictions. This is where Foresight-X earns its name.

---

### [7] Evaluator

**Purpose.** Score each option across multiple dimensions to enable principled comparison.

**Scoring dimensions.**
- **Expected value** (weighted over scenarios)
- **Risk** (variance / tail risk)
- **Regret** (counterfactual: how bad if this option is wrong?)
- **Uncertainty** (how confident is the simulation itself?)
- **Alignment with stated goals**

**Input.** `List[SimulatedFuture]` + `UserState.goals`.

**Output.** `List[OptionEvaluation]` with per-dimension scores + rationale.

**Role.** Makes trade-offs legible. The user can see *why* one option wins.

---

### [8] Recommender

**Purpose.** Select the single best option and generate concrete next actions.

**Input.** `List[OptionEvaluation]`.

**Output.** `Recommendation`:
- `chosen_option`
- `reasoning` (cites specific evidence + memory + simulation results)
- `next_actions` (concrete: schedule, message drafts, checklists)
- `trigger_conditions_for_reassessment` (when to re-run Foresight-X)

**Role.** The point of the whole pipeline. One decision, defensible, actionable.

---

### [9] Reflector

**Purpose.** Meta-analysis of the system's own reasoning.

**Input.** Entire decision trace (all module outputs).

**Output.** `Reflection`:
- `possible_errors` (where could the system be wrong?)
- `uncertainty_sources`
- `model_limitations_that_applied`
- `information_gaps` (what would have improved the decision?)
- `self_improvement_signal` (feeds into Harness)

**Role.** Honesty about limits. Also the primary input to the Harness self-improvement loop.

---

### [10] Outcome Tracker (Harness)

**Purpose.** Capture what actually happened after the decision, so the system can learn.

**Mechanism.** After a configurable delay (or on-demand user check-in), prompt the user for outcome data: "Did you take the action? What happened? How do you feel about it now?"

**Output.** `DecisionOutcome` written back into Memory Module, indexed to the original decision.

**Role.** Without this, "self-improving" is a lie. This is the ground truth.

---

### [11] Evaluation Harness

**Purpose.** Systematically measure decision quality over time.

**Metrics (full vision).**
- **Calibration** — did predicted probabilities match observed frequencies?
- **Regret** — retrospective: would a different option have been better?
- **Action completion** — did the user actually execute next_actions?
- **Reversal rate** — how often did the user later reverse the decision?
- **User-reported outcome quality** (1–5)

**v0 scope:** Store outcomes in the trace/outcome store so metrics *can* be computed later; a full dashboard is **not** required for hackathon completion.

**Role.** Turns subjective "good advice" into objective, trackable signal (incrementally after v0).

---

### [12] Self-Improvement Loop

**Purpose.** Use outcomes + harness metrics to improve future decisions.

**Mechanisms (prioritized for hackathon v0).**
- **Memory update (required for “done”)** — new decisions + outcomes re-indexed so retrieval changes on the next run
- **Prompt tuning (stretch)** — worst-performing prompts flagged for human revision; optional stub log only
- **Weight adjustment (stretch)** — evaluation dimension weights re-balanced per domain; optional small tweak in `config.py`
- **Pattern extraction (post–v0)** — recurring failure modes promoted to Irrationality heuristics

**Role.** v0 proves the **closed loop** (decide → outcome → memory). Deeper automation is incremental.

---

## 7. User Journey

1. **Trigger.** User types: "I got an offer from Company X, they want an answer by Friday. I also have an interview with Company Y next week. What should I do?"
2. **Perception.** System extracts: {decision_type: career, time_pressure: high, reversibility: partial, goals: [...retrieved from memory]}.
3. **Retrieval.** Memory surfaces the user's prior job-decision patterns; World Knowledge pulls Tavily results on Company X/Y.
4. **Irrationality check.** System notes high time pressure + irreversible-ish decision → flags for extra scrutiny.
5. **Options generated.** (a) Accept X now, (b) Ask X for 1-week extension, (c) Decline X, wait for Y, (d) Negotiate with X leveraging Y.
6. **Simulation.** Each option → best/base/worst futures with probabilities.
7. **Evaluation.** Option (b) scores highest on expected value, moderate on risk, low on regret.
8. **Recommendation.** "Ask X for a 1-week extension. Draft message below. If X refuses, fall back to accepting — the evidence suggests X > waiting for unseen Y."
9. **Reflection.** "Uncertainty is high around Y's outcome; this dominates the recommendation. If you learn more about Y in 48 hours, re-run."
10. **Outcome loop.** One week later: "What happened?" → captured → indexed → improves future decisions.

---

## 8. Demo Scenarios (Hackathon)

For judging, prepare **2 scripted demos**:

**Demo A — Career decision (shows memory + Tavily).**
Shows retrieval-grounded reasoning, multi-option simulation, actionable output.

**Demo B — Re-run with updated outcome (shows Harness self-improvement).**
Run a decision, record a fake outcome, re-run a similar decision, point out how the system's output changes.

**Demo C (stretch) — Irrationality catch.**
Feed the system a clearly emotional / high-stress input. Show it refuses to optimize, slows the user down, and asks for more information before proceeding.

---

## 9. Success Metrics

**For the hackathon demo — must all be true to count “complete”:**

| # | Gate | How to verify |
|---|------|----------------|
| 1 | **7 sections** | Situation, Insights, Options, Trade-offs, Recommendation, Actions, Reflection — emitted from one end-to-end run (console or UI) |
| 2 | **Tavily** | At least one live Tavily call appears in the saved trace (or logged step); cache may supplement but does not replace this for judging |
| 3 | **Memory** | At least one memory retrieval step in the trace (seeded demo corpus is OK) |
| 4 | **Harness delta** | After recording an outcome for a decision, a **second** similar run produces **observably different** retrieval or recommendation vs the first run — OR pre-seeded two memory states are demoed side-by-side if live loop fails (fallback per technical doc) |

**Stretch (nice-to-have, not required for completion):** Demo C (Irrationality catch); calibration metrics in UI; automated weight tuning.

**For real-world use (post-hackathon — goals, not v0 commitments):**
- Calibration error < 0.15 after 20 decisions (requires outcome volume)
- User-reported outcome quality ≥ 4/5 average
- Action-completion rate ≥ 60%

---

## 10. Out of Scope (v0)

- Multi-user / team decisions
- Real tool execution (sending emails, booking calendars) — only *drafts* in v0
- Fine-tuned models — v0 uses prompted frontier LLMs
- Mobile UI — CLI / simple web UI only for hackathon
- Guaranteed calibration / “always correct” decisions
- Full Evaluation Harness analytics dashboard — minimal metrics or JSON report is enough

**If time collapses:** Ship RIS end-to-end + trace JSON + Tavily + memory first. Narrow Harness to **outcome capture + memory write-back**; show self-improvement via before/after retrieval or slides + pre-seeded memory (see technical architecture *Minimum Viable Demo*).

---

## 11. Key Principle

> Foresight-X does not help you decide faster.
> It helps you decide **better than you would alone**.
