import { AppState, DecisionReport } from '../App';
import { LoadingState } from './LoadingState';
import { EmptyState } from './EmptyState';
import { ReportSections } from './ReportSections';
import { TableOfContents } from './TableOfContents';

interface ReportPanelProps {
  state: AppState;
  report: DecisionReport | null;
  fullTrace: Record<string, unknown> | null;
  showJson: boolean;
  onToggleJson: () => void;
  onShowOutcome: () => void;
  canRecordOutcome: boolean;
}

export function ReportPanel({
  state,
  report,
  fullTrace,
  showJson,
  onToggleJson,
  onShowOutcome,
  canRecordOutcome,
}: ReportPanelProps) {
  if (state === 'empty') {
    return <EmptyState />;
  }

  if (state === 'loading') {
    return <LoadingState />;
  }

  if (state === 'result' && report) {
    return (
      <div className="space-y-5">
        <h3 className="text-lg text-gray-800 tracking-tight" style={{ fontWeight: 600 }}>
          7-section output
        </h3>
        <ReportSections report={report} />

        <div className="flex gap-4">
          <button
            type="button"
            onClick={onShowOutcome}
            disabled={!canRecordOutcome}
            className="px-7 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-full hover:shadow-2xl hover:shadow-purple-500/30 transition-all text-base disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ fontWeight: 600 }}
          >
            Record Outcome
          </button>
          <button
            onClick={onToggleJson}
            className="px-7 py-4 bg-white/50 backdrop-blur-2xl text-gray-700 border border-white/80 rounded-full hover:bg-white/70 hover:shadow-lg transition-all text-base"
            style={{ fontWeight: 500 }}
          >
            {showJson ? 'Hide' : 'Show'} JSON
          </button>
        </div>

        {showJson && fullTrace && (
          <div className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
            <p className="text-xs text-gray-500 mb-2" style={{ fontWeight: 600 }}>
              Trace JSON (DecisionTrace)
            </p>
            <pre className="text-xs text-gray-900 overflow-x-auto max-h-[480px]" style={{ fontWeight: 400 }}>
              {JSON.stringify(fullTrace, null, 2)}
            </pre>
          </div>
        )}
      </div>
    );
  }

  return null;
}
