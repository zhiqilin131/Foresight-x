import { useEffect, useRef, useState } from 'react';
import { AppState } from '../model';
import { VoiceInputButton } from './VoiceInputButton';

interface InputPanelProps {
  decisionInput: string;
  onInputChange: (value: string) => void;
  onRun: () => void;
  onReset: () => void;
  state: AppState;
  isClarifyChecking?: boolean;
  clarifyOpen?: boolean;
  loadingStage?: string | null;
  stageLabel?: Record<string, string>;
  /** Append browser / server transcript into the decision field */
  onVoiceTranscript?: (text: string) => void;
}

export function InputPanel({
  decisionInput,
  onInputChange,
  onRun,
  onReset,
  state,
  isClarifyChecking = false,
  clarifyOpen = false,
  loadingStage,
  stageLabel,
  onVoiceTranscript,
}: InputPanelProps) {
  const [justClicked, setJustClicked] = useState(false);
  const clickTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (clickTimerRef.current !== null) {
        window.clearTimeout(clickTimerRef.current);
      }
    };
  }, []);

  const handleRunClick = () => {
    setJustClicked(true);
    if (clickTimerRef.current !== null) {
      window.clearTimeout(clickTimerRef.current);
    }
    clickTimerRef.current = window.setTimeout(() => {
      setJustClicked(false);
      clickTimerRef.current = null;
    }, 900);
    onRun();
  };

  return (
    <div>
      <div className="bg-white/50 backdrop-blur-2xl rounded-[32px] p-8 border border-white/80 shadow-[0_8px_32px_rgba(0,0,0,0.06)]">
        <div className="space-y-6">
          {state === 'empty' && (
            <>
              <div className="space-y-4">
                <div className="flex justify-between items-center gap-2">
                  <label htmlFor="decision-input" className="block text-sm text-gray-700" style={{ fontWeight: 500 }}>
                    Decision input
                  </label>
                  {onVoiceTranscript && (
                    <VoiceInputButton
                      onTranscript={onVoiceTranscript}
                      disabled={state === 'loading'}
                      compact
                    />
                  )}
                </div>
                <textarea
                  id="decision-input"
                  value={decisionInput}
                  onChange={(e) => onInputChange(e.target.value)}
                  placeholder="I got an offer from Company X, they want an answer by Friday..."
                  className="w-full min-h-[240px] px-6 py-5 bg-white/70 backdrop-blur-sm border border-gray-200/60 rounded-3xl resize-none focus:outline-none focus:ring-2 focus:ring-purple-400/50 focus:border-transparent transition-all text-base text-gray-900 placeholder:text-gray-400 leading-relaxed shadow-sm"
                  style={{ fontWeight: 400 }}
                  disabled={state === 'loading'}
                />
                <p className="text-[11px] text-gray-500 leading-relaxed -mt-1">
                  Optional multiple-choice prompts appear only when the model judges your message too vague; clear
                  decisions (e.g. A vs B with stated constraints) usually skip that step.
                </p>
              </div>

              <button
                onClick={handleRunClick}
                disabled={!decisionInput.trim() || state === 'loading' || isClarifyChecking || clarifyOpen}
                className={`w-full px-8 py-5 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-full hover:shadow-2xl hover:shadow-purple-500/30 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed transition-all text-base flex items-center justify-center gap-3 ${
                  justClicked ? 'ring-4 ring-purple-200 scale-[0.995]' : ''
                }`}
                style={{ fontWeight: 600 }}
              >
                {state === 'loading' ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span className="flex flex-col items-center gap-1">
                      <span>Analyzing decision…</span>
                      {loadingStage && stageLabel && (
                        <span className="text-xs font-normal opacity-90">
                          {stageLabel[loadingStage] ?? loadingStage}
                        </span>
                      )}
                    </span>
                  </>
                ) : isClarifyChecking ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span>Checking if clarification is needed…</span>
                  </>
                ) : clarifyOpen ? (
                  <>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 3l1.545 4.635L18.18 9.18l-4.635 1.545L12 15.36l-1.545-4.635L5.82 9.18l4.635-1.545L12 3z" />
                    </svg>
                    Waiting for your clarification
                  </>
                ) : justClicked ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    Run request received
                  </>
                ) : (
                  <>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 3l1.545 4.635L18.18 9.18l-4.635 1.545L12 15.36l-1.545-4.635L5.82 9.18l4.635-1.545L12 3z" />
                    </svg>
                    Run Foresight-X
                  </>
                )}
              </button>
            </>
          )}

          {state === 'loading' && (
            <div className="py-2 space-y-3">
              <p className="text-sm text-gray-700" style={{ fontWeight: 600 }}>
                Running pipeline…
              </p>
              {loadingStage && stageLabel && (
                <p className="text-xs text-gray-500 leading-relaxed">
                  {stageLabel[loadingStage] ?? loadingStage}
                </p>
              )}
              <div className="w-8 h-8 border-2 border-purple-200 border-t-purple-600 rounded-full animate-spin" />
            </div>
          )}

          {state === 'result' && (
            <button
              onClick={onReset}
              className="w-full px-8 py-4 bg-white/70 backdrop-blur-sm text-gray-700 border border-gray-200/60 rounded-full hover:bg-white/90 hover:shadow-lg transition-all text-base"
              style={{ fontWeight: 500 }}
            >
              New Decision
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
