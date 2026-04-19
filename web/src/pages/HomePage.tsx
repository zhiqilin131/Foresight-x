import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { ClarifyDialog, type ClarifyQuestion } from '../app/components/ClarifyDialog';
import { InputPanel } from '../app/components/InputPanel';
import { MainNavButtons } from '../app/components/MainNavButtons';
import { DecisionQuestionStrip } from '../app/components/DecisionQuestionStrip';
import { ReportPanel } from '../app/components/ReportPanel';
import { OutcomeHarness } from '../app/components/OutcomeHarness';
import { mapTraceToReport } from '../utils/mapTrace';
import { mergeStreamingPartial } from '../utils/mergeStreamingTrace';
import { apiUrl } from '../utils/apiOrigin';
import { parseSseBlocks } from '../utils/parseSse';
import type { AppState, DecisionReport } from '../app/model';

const PIPELINE_STAGES = ['enhance', 'perceive', 'retrieve', 'infer', 'simulate', 'evaluate', 'finalize'] as const;

const STAGE_LABEL: Record<string, string> = {
  enhance: 'Clarifying your question',
  perceive: 'Understanding your situation',
  retrieve: 'Retrieving memory & world evidence',
  infer: 'Bias check & option generation',
  simulate: 'Simulating futures per option',
  evaluate: 'Scoring trade-offs',
  finalize: 'Recommendation & reflection',
};

function stageToProgress(stage: string): number {
  const i = PIPELINE_STAGES.indexOf(stage as (typeof PIPELINE_STAGES)[number]);
  if (i < 0) return 5;
  return Math.round(((i + 1) / PIPELINE_STAGES.length) * 100);
}

type StreamOpts = {
  clarification_answers?: Record<string, string>;
  save_clarification_to_profile?: boolean;
  preserve_raw_input?: boolean;
};

type Tier3ProfileView = {
  profile: {
    user_id?: string;
    values?: string[];
    risk_posture?: string;
    recurring_themes?: string[];
    current_goals?: string[];
    known_constraints?: string[];
    n_decisions_summarized?: number;
    last_updated?: string;
    confidence?: number;
  };
  used_in_recommender: boolean;
  use_threshold: number;
  source: string;
};

export default function HomePage() {
  const navigate = useNavigate();
  const routeTraceId = useParams().decisionId;

  const [state, setState] = useState<AppState>(() => (routeTraceId ? 'loading' : 'empty'));
  const [decisionInput, setDecisionInput] = useState('');
  const [fullTrace, setFullTrace] = useState<Record<string, unknown> | null>(null);
  const [liveTrace, setLiveTrace] = useState<Record<string, unknown> | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [tracePath, setTracePath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [showOutcome, setShowOutcome] = useState(false);
  const [loadingStage, setLoadingStage] = useState<string | null>(null);
  const [runProgress, setRunProgress] = useState(0);
  const [runStageLabel, setRunStageLabel] = useState('Starting…');
  const [tier3Profile, setTier3Profile] = useState<Tier3ProfileView | null>(null);
  const [clarifyOpen, setClarifyOpen] = useState(false);
  const [clarifyChecking, setClarifyChecking] = useState(false);
  const [clarifyPayload, setClarifyPayload] = useState<{ questions: ClarifyQuestion[]; note: string } | null>(null);
  /** Shown only when clarify fails or LLM is missing — not when the model simply says no extra questions. */
  const [clarifyGateHint, setClarifyGateHint] = useState<string | null>(null);
  const prevTraceIdRef = useRef<string | undefined>(undefined);

  useEffect(() => {
    const prev = prevTraceIdRef.current;
    prevTraceIdRef.current = routeTraceId;
    if (prev !== undefined && routeTraceId === undefined) {
      setFullTrace(null);
      setLiveTrace(null);
      setNotes([]);
      setTracePath(null);
      setDecisionInput('');
      setState('empty');
      setError(null);
    }
  }, [routeTraceId]);

  useEffect(() => {
    if (!routeTraceId) return;
    if (
      fullTrace &&
      typeof fullTrace.decision_id === 'string' &&
      fullTrace.decision_id === routeTraceId
    ) {
      return;
    }
    let cancelled = false;
    setError(null);
    setState('loading');
    setRunStageLabel('Loading saved decision…');
    setLiveTrace(null);
    void (async () => {
      try {
        const res = await fetch(apiUrl(`/api/traces/${encodeURIComponent(routeTraceId)}`));
        if (!res.ok) throw new Error(await res.text());
        const trace = (await res.json()) as Record<string, unknown>;
        if (cancelled) return;
        setFullTrace(trace);
        if (typeof trace.original_user_input === 'string') {
          setDecisionInput(trace.original_user_input);
        }
        setNotes([]);
        setTracePath(null);
        setState('result');
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load saved decision');
          setState('empty');
        }
      } finally {
        if (!cancelled) setRunStageLabel('Starting…');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [routeTraceId, fullTrace]);

  const displayReport = useMemo((): DecisionReport | null => {
    if (state === 'result' && fullTrace) return mapTraceToReport(fullTrace);
    if (liveTrace) return mapTraceToReport(liveTrace);
    return null;
  }, [state, fullTrace, liveTrace]);

  const traceForPanel = state === 'result' ? fullTrace : liveTrace;

  const loadTier3Profile = useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/api/profile/tier3'));
      if (!res.ok) return;
      const data = (await res.json()) as Tier3ProfileView;
      if (data && typeof data === 'object') setTier3Profile(data);
    } catch {
      // non-blocking diagnostics panel
    }
  }, []);

  useEffect(() => {
    void loadTier3Profile();
  }, [loadTier3Profile]);

  const runPipelineStream = useCallback(
    async (opts?: StreamOpts) => {
      setError(null);
      setState('loading');
      setLoadingStage('enhance');
      setRunProgress(4);
      setRunStageLabel('Connecting to pipeline…');
      setLiveTrace(null);
      setFullTrace(null);

      const controller = new AbortController();
      const RUN_TIMEOUT_MS = 300_000;
      const timeoutId = window.setTimeout(() => controller.abort(), RUN_TIMEOUT_MS);

      try {
        const body: Record<string, unknown> = {
          raw_input: decisionInput,
          client_now_iso: new Date().toISOString(),
        };
        if (opts?.clarification_answers && Object.keys(opts.clarification_answers).length > 0) {
          body.clarification_answers = opts.clarification_answers;
          body.save_clarification_to_profile = Boolean(opts.save_clarification_to_profile);
        }
        if (opts?.preserve_raw_input) {
          body.preserve_raw_input = true;
        }

        const res = await fetch(apiUrl('/api/run/stream'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || res.statusText);
        }
        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buf = '';
        let gotNotes: string[] = [];
        let trace: Record<string, unknown> | null = null;
        let path: string | null = null;

        const consume = (data: Record<string, unknown>) => {
          if (data.event === 'notes' && Array.isArray(data.notes)) {
            gotNotes = data.notes as string[];
          }
          if (data.event === 'meta') {
            if (typeof data.decision_id === 'string') {
              setLiveTrace((prev) => ({
                ...(prev ?? {}),
                decision_id: data.decision_id,
                ...(typeof data.timestamp === 'string' ? { timestamp: data.timestamp } : {}),
              }));
            }
          }
          if (data.event === 'partial' && data.data && typeof data.data === 'object') {
            setLiveTrace((prev) => mergeStreamingPartial(prev, data.data as Record<string, unknown>));
          }
          if (data.event === 'stage' && typeof data.stage === 'string') {
            const st = data.stage;
            setLoadingStage(st);
            setRunProgress(stageToProgress(st));
            setRunStageLabel(STAGE_LABEL[st] ?? st);
          }
          if (data.event === 'complete' && data.trace && typeof data.trace === 'object') {
            trace = data.trace as Record<string, unknown>;
            if (typeof data.trace_path === 'string') path = data.trace_path;
            setRunProgress(100);
            setRunStageLabel('Done');
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          buf = parseSseBlocks(buf, consume);
        }
        if (buf.trim()) {
          parseSseBlocks(`${buf}\n\n`, consume);
        }
        if (!trace) throw new Error('Incomplete response (no trace)');

        setLiveTrace(null);
        setFullTrace(trace);
        setNotes(gotNotes);
        setTracePath(path);
        setClarifyGateHint(null);
        setState('result');
        void loadTier3Profile();
        const tid = trace.decision_id;
        if (typeof tid === 'string' && tid) {
          navigate(`/trace/${tid}`, { replace: true });
        }
      } catch (e) {
        let msg = e instanceof Error ? e.message : 'Run failed';
        if (e instanceof Error && e.name === 'AbortError') {
          msg =
            'Run timed out (5 min). Ensure uvicorn is on 8765, OPENAI_API_KEY is set, and `.env.development` has VITE_API_ORIGIN=http://127.0.0.1:8765 for streaming.';
        }
        setError(msg);
        setClarifyGateHint(null);
        setState('empty');
        setLiveTrace(null);
      } finally {
        window.clearTimeout(timeoutId);
        setLoadingStage(null);
        setRunProgress(0);
      }
    },
    [decisionInput, loadTier3Profile, navigate],
  );

  const handleRunDecision = async () => {
    if (state === 'loading' || clarifyChecking || clarifyOpen) return;
    setError(null);
    setClarifyGateHint(null);
    setClarifyChecking(true);
    try {
      const cr = await fetch(apiUrl('/api/clarify'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_input: decisionInput }),
      });
      if (cr.ok) {
        const gate = (await cr.json()) as {
          need_clarification?: boolean;
          questions?: ClarifyQuestion[];
          note?: string;
          skip_reason?: string;
        };
        if (gate.need_clarification && Array.isArray(gate.questions) && gate.questions.length > 0) {
          setClarifyPayload({ questions: gate.questions, note: String(gate.note ?? '') });
          // Ensure we do not show pipeline loading until user clicks "Continue analysis".
          setState('empty');
          setLoadingStage(null);
          setRunProgress(0);
          setRunStageLabel('Starting…');
          setClarifyOpen(true);
          setClarifyChecking(false);
          return;
        }
        // No modal: either input was specific enough (not_needed) or gate unavailable — see clarifyGateHint.
        if (gate.skip_reason === 'error') {
          setClarifyGateHint(
            'Clarification check failed (model/network). Continuing with your raw text (no enhancement rewrite).',
          );
          setClarifyChecking(false);
          await runPipelineStream({ preserve_raw_input: true });
          return;
        } else if (gate.skip_reason === 'no_llm') {
          setClarifyGateHint('Optional clarification is off: API has no LLM configured. Running analysis anyway.');
        }
      }
    } catch {
      /* optional gate — same as skip_reason error: proceed to pipeline */
      setClarifyGateHint('Could not reach clarification endpoint; continuing with your raw text.');
      setClarifyChecking(false);
      await runPipelineStream({ preserve_raw_input: true });
      return;
    }
    setClarifyChecking(false);
    await runPipelineStream();
  };

  const handleReset = () => {
    setState('empty');
    setDecisionInput('');
    setFullTrace(null);
    setLiveTrace(null);
    setNotes([]);
    setTracePath(null);
    setShowJson(false);
    setShowOutcome(false);
    setError(null);
    setClarifyGateHint(null);
    setLoadingStage(null);
    if (routeTraceId) navigate('/', { replace: true });
  };

  const decisionId =
    fullTrace && typeof fullTrace.decision_id === 'string' ? fullTrace.decision_id : null;

  const nav = <MainNavButtons />;

  const workspace = (
    <div className="max-w-[1600px] mx-auto px-6 lg:px-10 py-8 pb-16">
      {nav}

      <header className="mb-6">
        <h1 className="text-3xl md:text-4xl text-gray-900 tracking-tight" style={{ fontWeight: 700, letterSpacing: '-0.03em' }}>
          Foresight-X
        </h1>
        <p className="text-sm md:text-base text-gray-500 mt-1" style={{ fontWeight: 400 }}>
          Evidence-grounded decision agent
        </p>
      </header>

      <DecisionQuestionStrip decisionInput={decisionInput} report={displayReport} />

      {clarifyGateHint && state === 'loading' && (
        <div className="mb-4 text-xs text-amber-950 bg-amber-50/95 border border-amber-200/80 rounded-xl px-4 py-2.5 leading-relaxed">
          {clarifyGateHint}
        </div>
      )}

      {notes.length > 0 && state === 'result' && (
        <div className="mb-4 space-y-2">
          {notes.map((n) => (
            <div
              key={n}
              className="text-sm text-blue-900 bg-blue-50/90 border border-blue-200/60 rounded-xl px-4 py-2"
            >
              {n}
            </div>
          ))}
        </div>
      )}
      {tracePath && state === 'result' && (
        <p className="mb-6 text-sm text-emerald-800 bg-emerald-50/90 border border-emerald-200/60 rounded-xl px-4 py-2">
          Trace saved to {tracePath}
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
        <aside className="lg:col-span-4">
          <InputPanel
            decisionInput={decisionInput}
            onInputChange={setDecisionInput}
            onRun={handleRunDecision}
            onReset={handleReset}
            state={state}
            isClarifyChecking={clarifyChecking}
            clarifyOpen={clarifyOpen}
            loadingStage={loadingStage}
            stageLabel={STAGE_LABEL}
            onVoiceTranscript={(t) =>
              setDecisionInput((s) => {
                const x = s.trim();
                return x ? `${x} ${t}` : t;
              })
            }
          />
        </aside>

        <section className="lg:col-span-8 min-h-[200px]">
          <ReportPanel
            state={state}
            report={displayReport}
            fullTrace={traceForPanel}
            tier3Profile={tier3Profile}
            showJson={showJson}
            onToggleJson={() => setShowJson(!showJson)}
            onShowOutcome={() => setShowOutcome(true)}
            canRecordOutcome={Boolean(decisionId)}
            runProgress={runProgress}
            runStageLabel={runStageLabel}
          />
        </section>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fff5fb] via-[#f5f3ff] to-[#f0f9ff] relative overflow-hidden">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 left-10 w-[500px] h-[500px] bg-gradient-to-br from-purple-300/30 to-pink-300/30 rounded-full blur-3xl"></div>
        <div className="absolute bottom-20 right-10 w-[500px] h-[500px] bg-gradient-to-br from-blue-300/30 to-purple-300/30 rounded-full blur-3xl"></div>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-gradient-to-br from-purple-200/20 to-blue-200/20 rounded-full blur-3xl"></div>
      </div>

      <div className="relative z-10">
        {state === 'empty' ? (
          <div className="flex items-center justify-center min-h-screen px-8">
            <div className="w-full max-w-3xl">
              {nav}
              <div className="text-center mb-16">
                <h1 className="text-7xl mb-5 text-gray-900 tracking-tight" style={{ fontWeight: 700, letterSpacing: '-0.04em' }}>
                  Foresight-X
                </h1>
                <p className="text-xl text-gray-500" style={{ fontWeight: 400 }}>
                  Evidence-grounded decision agent
                </p>
              </div>

              {error && (
                <div className="mb-6 p-4 rounded-2xl bg-red-50 border border-red-200 text-red-800 text-sm">{error}</div>
              )}

              <InputPanel
                decisionInput={decisionInput}
                onInputChange={setDecisionInput}
                onRun={handleRunDecision}
                onReset={handleReset}
                state={state}
                isClarifyChecking={clarifyChecking}
                clarifyOpen={clarifyOpen}
                loadingStage={loadingStage}
                stageLabel={STAGE_LABEL}
                onVoiceTranscript={(t) =>
                  setDecisionInput((s) => {
                    const x = s.trim();
                    return x ? `${x} ${t}` : t;
                  })
                }
              />

              <div className="mt-12 text-center max-w-lg mx-auto">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Personalization</p>
                <Link
                  to="/personalize"
                  className="inline-flex items-center justify-center w-full sm:w-auto px-6 py-3.5 rounded-2xl border border-violet-200/90 bg-white/80 text-violet-900 text-sm font-medium hover:bg-violet-50/90 hover:border-violet-300 transition-colors shadow-sm"
                >
                  Import chats or email (paste / .txt) → teach the model your patterns
                </Link>
                <p className="text-xs text-gray-500 mt-3 leading-relaxed">
                  Optional: stubbed Gmail &amp; Messenger connectors on the next screen — use manual paste for now.
                </p>
              </div>
            </div>
          </div>
        ) : (
          workspace
        )}
      </div>

      <ClarifyDialog
        open={clarifyOpen}
        onOpenChange={(open) => {
          setClarifyOpen(open);
          if (!open) {
            setClarifyPayload(null);
            setClarifyChecking(false);
          }
        }}
        questions={clarifyPayload?.questions ?? []}
        note={clarifyPayload?.note}
        onConfirm={(answers, saveToProfile) => {
          void runPipelineStream({
            clarification_answers: answers,
            save_clarification_to_profile: saveToProfile,
          });
        }}
      />

      {showOutcome && decisionId && (
        <OutcomeHarness
          decisionId={decisionId}
          onClose={() => setShowOutcome(false)}
        />
      )}
    </div>
  );
}
