import { useState } from 'react';
import { InputPanel } from './components/InputPanel';
import { ReportPanel } from './components/ReportPanel';
import { OutcomeHarness } from './components/OutcomeHarness';
import { mapTraceToReport } from '../utils/mapTrace';

export type AppState = 'empty' | 'loading' | 'result';

export interface DecisionReport {
  situation: string;
  insights: {
    decisionType?: string;
    timePressure?: string;
    stress?: string;
    biasRisks?: string[];
    memoryPatterns?: string[];
  };
  options: Array<{
    id: string;
    name: string;
    description: string;
  }>;
  tradeoffs?: {
    headers: string[];
    rows: Array<{
      optionId: string;
      optionName: string;
      scores: Record<string, number | string>;
    }>;
  };
  recommendation: {
    reasoning: string;
    chosenOption: string;
  };
  actions: Array<{
    text: string;
    deadline?: string;
  }>;
  reflection: {
    possibleErrors?: string[];
    uncertaintySources?: string[];
    informationGaps?: string[];
    selfImprovement?: string;
  };
}

export default function App() {
  const [state, setState] = useState<AppState>('empty');
  const [decisionInput, setDecisionInput] = useState('');
  const [report, setReport] = useState<DecisionReport | null>(null);
  const [fullTrace, setFullTrace] = useState<Record<string, unknown> | null>(null);
  const [notes, setNotes] = useState<string[]>([]);
  const [tracePath, setTracePath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showJson, setShowJson] = useState(false);
  const [showOutcome, setShowOutcome] = useState(false);

  const handleRunDecision = async () => {
    setError(null);
    setState('loading');
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_input: decisionInput }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }
      const data = (await res.json()) as {
        trace: Record<string, unknown>;
        notes?: string[];
        trace_path?: string;
      };
      setFullTrace(data.trace);
      setNotes(data.notes ?? []);
      setTracePath(data.trace_path ?? null);
      setReport(mapTraceToReport(data.trace));
      setState('result');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Run failed');
      setState('empty');
    }
  };

  const handleReset = () => {
    setState('empty');
    setDecisionInput('');
    setReport(null);
    setFullTrace(null);
    setNotes([]);
    setTracePath(null);
    setShowJson(false);
    setShowOutcome(false);
    setError(null);
  };

  const decisionId =
    fullTrace && typeof fullTrace.decision_id === 'string' ? fullTrace.decision_id : null;

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
              <div className="text-center mb-16">
                <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-purple-500/10 to-blue-500/10 backdrop-blur-xl rounded-3xl mb-8 border border-white/60 shadow-xl">
                  <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="url(#gradient)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <defs>
                      <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#a855f7" />
                        <stop offset="100%" stopColor="#3b82f6" />
                      </linearGradient>
                    </defs>
                    <path d="M12 3l1.545 4.635L18.18 9.18l-4.635 1.545L12 15.36l-1.545-4.635L5.82 9.18l4.635-1.545L12 3z" />
                  </svg>
                </div>
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
              />
            </div>
          </div>
        ) : (
          <div className="max-w-[1600px] mx-auto px-8 py-16">
            <div className="mb-12">
              <h1 className="text-5xl text-gray-900 mb-3 tracking-tight" style={{ fontWeight: 700, letterSpacing: '-0.03em' }}>
                Foresight-X
              </h1>
              <p className="text-lg text-gray-500" style={{ fontWeight: 400 }}>
                Evidence-grounded decision agent
              </p>
              {notes.length > 0 && (
                <div className="mt-4 space-y-2">
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
              {tracePath && (
                <p className="mt-3 text-sm text-emerald-800 bg-emerald-50/90 border border-emerald-200/60 rounded-xl px-4 py-2">
                  Trace saved to {tracePath}
                </p>
              )}
            </div>

            <div className="grid grid-cols-12 gap-8">
              <div className="col-span-4">
                <InputPanel
                  decisionInput={decisionInput}
                  onInputChange={setDecisionInput}
                  onRun={handleRunDecision}
                  onReset={handleReset}
                  state={state}
                />
              </div>

              <div className="col-span-8">
                <ReportPanel
                  state={state}
                  report={report}
                  fullTrace={fullTrace}
                  showJson={showJson}
                  onToggleJson={() => setShowJson(!showJson)}
                  onShowOutcome={() => setShowOutcome(true)}
                  canRecordOutcome={Boolean(decisionId)}
                />
              </div>
            </div>
          </div>
        )}
      </div>

      {showOutcome && decisionId && (
        <OutcomeHarness
          decisionId={decisionId}
          onClose={() => setShowOutcome(false)}
        />
      )}
    </div>
  );
}
