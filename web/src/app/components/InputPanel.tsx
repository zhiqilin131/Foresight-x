import { AppState } from '../App';

interface InputPanelProps {
  decisionInput: string;
  onInputChange: (value: string) => void;
  onRun: () => void;
  onReset: () => void;
  state: AppState;
}

export function InputPanel({ decisionInput, onInputChange, onRun, onReset, state }: InputPanelProps) {
  return (
    <div className={state === 'empty' ? '' : 'sticky top-16'}>
      <div className="bg-white/50 backdrop-blur-2xl rounded-[32px] p-8 border border-white/80 shadow-[0_8px_32px_rgba(0,0,0,0.06)]">
        <div className="space-y-6">
          {state !== 'empty' && (
            <div className="pb-6 border-b border-gray-200/40">
              <label className="block text-xs uppercase tracking-wider text-gray-500 mb-3" style={{ fontWeight: 600, letterSpacing: '0.05em' }}>
                Your decision
              </label>
              <p className="text-sm text-gray-900 line-clamp-4 leading-relaxed" style={{ fontWeight: 400 }}>
                {decisionInput}
              </p>
            </div>
          )}

          {state === 'empty' && (
            <>
              <div className="space-y-4">
                <label htmlFor="decision-input" className="block text-sm text-gray-700" style={{ fontWeight: 500 }}>
                  Decision input
                </label>
                <textarea
                  id="decision-input"
                  value={decisionInput}
                  onChange={(e) => onInputChange(e.target.value)}
                  placeholder="I got an offer from Company X, they want an answer by Friday..."
                  className="w-full min-h-[240px] px-6 py-5 bg-white/70 backdrop-blur-sm border border-gray-200/60 rounded-3xl resize-none focus:outline-none focus:ring-2 focus:ring-purple-400/50 focus:border-transparent transition-all text-base text-gray-900 placeholder:text-gray-400 leading-relaxed shadow-sm"
                  style={{ fontWeight: 400 }}
                  disabled={state === 'loading'}
                />
              </div>

              <button
                onClick={onRun}
                disabled={!decisionInput.trim() || state === 'loading'}
                className="w-full px-8 py-5 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-full hover:shadow-2xl hover:shadow-purple-500/30 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed transition-all text-base flex items-center justify-center gap-3"
                style={{ fontWeight: 600 }}
              >
                {state === 'loading' ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    Analyzing decision...
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
