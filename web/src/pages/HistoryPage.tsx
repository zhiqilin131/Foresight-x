import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';
import { PageBackButton } from '../app/components/PageBackButton';
import { OutcomeHarness } from '../app/components/OutcomeHarness';
import { SavedOutcomeModal } from '../app/components/SavedOutcomeModal';
import { apiUrl } from '../utils/apiOrigin';

interface TraceRow {
  decision_id: string;
  timestamp: string;
  decision_type: string;
  preview: string;
}

export default function HistoryPage() {
  const [rows, setRows] = useState<TraceRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [outcomeForId, setOutcomeForId] = useState<string | null>(null);
  const [savedOutcomeForId, setSavedOutcomeForId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(apiUrl('/api/traces'));
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as TraceRow[];
      setRows(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onDelete = async (id: string) => {
    if (!window.confirm(`Delete trace ${id}? Linked outcome file (if any) will be removed too.`)) {
      return;
    }
    setBusy(id);
    setError(null);
    try {
      const res = await fetch(apiUrl(`/api/traces/${encodeURIComponent(id)}`), { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fff5fb] via-[#f5f3ff] to-[#f0f9ff] px-8 py-16">
      <div className="max-w-3xl mx-auto">
        <PageBackButton />
        <h1 className="text-3xl text-gray-900 mb-2" style={{ fontWeight: 700 }}>
          Decision history
        </h1>
        <p className="text-gray-600 mb-8 text-sm">
          Traces stored under <code className="text-xs bg-white/80 px-1 rounded">data/traces</code>. Open a row to see
          the same result view as when you first ran the decision. Deleting a trace also removes a matching outcome in{' '}
          <code className="text-xs bg-white/80 px-1 rounded">data/outcomes</code> if present.
        </p>

        {error && <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm">{error}</div>}

        <ul className="space-y-3">
          {rows.length === 0 && !error && (
            <li className="text-gray-500 text-sm">No saved traces yet.</li>
          )}
          {rows.map((r) => (
            <li
              key={r.decision_id}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-2xl bg-white/60 border border-white/80 shadow-sm"
            >
              <Link to={`/trace/${encodeURIComponent(r.decision_id)}`} className="min-w-0 flex-1 text-left group">
                <div className="text-xs font-mono text-gray-400 mb-1">{r.decision_id}</div>
                <div className="text-sm text-gray-800 group-hover:text-purple-800 transition-colors">
                  {r.preview || '(empty)'}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {r.timestamp} · {r.decision_type}
                </div>
              </Link>
              <div className="flex flex-wrap gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setSavedOutcomeForId(r.decision_id)}
                  className="px-4 py-2 text-sm rounded-full border border-indigo-200 text-indigo-900 hover:bg-indigo-50"
                >
                  Saved outcome
                </button>
                <button
                  type="button"
                  onClick={() => setOutcomeForId(r.decision_id)}
                  className="px-4 py-2 text-sm rounded-full border border-purple-200 text-purple-900 hover:bg-purple-50"
                >
                  Record outcome
                </button>
                <button
                  type="button"
                  onClick={() => void onDelete(r.decision_id)}
                  disabled={busy === r.decision_id}
                  className="px-4 py-2 text-sm rounded-full border border-red-200 text-red-800 hover:bg-red-50 disabled:opacity-50"
                >
                  {busy === r.decision_id ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {outcomeForId && (
        <OutcomeHarness
          decisionId={outcomeForId}
          onClose={() => setOutcomeForId(null)}
        />
      )}

      {savedOutcomeForId && (
        <SavedOutcomeModal decisionId={savedOutcomeForId} onClose={() => setSavedOutcomeForId(null)} />
      )}
    </div>
  );
}
