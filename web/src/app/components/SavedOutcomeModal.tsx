import { useEffect, useState } from 'react';
import { apiUrl } from '../../utils/apiOrigin';

type OutcomePayload = {
  decision_id: string;
  user_took_recommended_action: boolean;
  actual_outcome: string;
  user_reported_quality: number;
  reversed_later: boolean;
  timestamp: string;
};

interface SavedOutcomeModalProps {
  decisionId: string;
  onClose: () => void;
}

export function SavedOutcomeModal({ decisionId, onClose }: SavedOutcomeModalProps) {
  const [loading, setLoading] = useState(true);
  const [outcome, setOutcome] = useState<OutcomePayload | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setMissing(false);
    setOutcome(null);
    void (async () => {
      try {
        const res = await fetch(apiUrl(`/api/outcomes/${encodeURIComponent(decisionId)}`));
        if (cancelled) return;
        if (res.status === 404) {
          setMissing(true);
          return;
        }
        if (!res.ok) throw new Error(await res.text());
        const data = (await res.json()) as OutcomePayload;
        setOutcome(data);
      } catch {
        if (!cancelled) setMissing(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [decisionId]);

  return (
    <div
      className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="saved-outcome-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-3xl bg-white border border-white/90 shadow-2xl p-6 max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start gap-4 mb-4">
          <h2 id="saved-outcome-title" className="text-lg text-gray-900" style={{ fontWeight: 700 }}>
            Saved outcome
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 px-3 py-1.5 rounded-full text-sm border border-gray-200 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
        <p className="text-xs font-mono text-gray-400 mb-4 break-all">{decisionId}</p>

        {loading && <p className="text-sm text-gray-600">Loading…</p>}

        {!loading && missing && (
          <div className="rounded-2xl border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
            <p className="mb-1" style={{ fontWeight: 600 }}>
              No outcome recorded
            </p>
            <p className="text-amber-900/90">
              There is no saved outcome file for this decision yet. Use &quot;Record outcome&quot; to add one.
            </p>
          </div>
        )}

        {!loading && outcome && (
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-gray-500 text-xs mb-0.5">Recorded at</dt>
              <dd className="text-gray-900">{outcome.timestamp}</dd>
            </div>
            <div>
              <dt className="text-gray-500 text-xs mb-0.5">Took recommended action</dt>
              <dd className="text-gray-900">{outcome.user_took_recommended_action ? 'Yes' : 'No'}</dd>
            </div>
            <div>
              <dt className="text-gray-500 text-xs mb-0.5">What happened</dt>
              <dd className="text-gray-900 whitespace-pre-wrap">{outcome.actual_outcome}</dd>
            </div>
            <div>
              <dt className="text-gray-500 text-xs mb-0.5">Quality (1–5)</dt>
              <dd className="text-gray-900">{outcome.user_reported_quality}</dd>
            </div>
            <div>
              <dt className="text-gray-500 text-xs mb-0.5">Reversed later</dt>
              <dd className="text-gray-900">{outcome.reversed_later ? 'Yes' : 'No'}</dd>
            </div>
          </dl>
        )}
      </div>
    </div>
  );
}
