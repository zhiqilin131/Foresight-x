import { useCallback, useEffect, useState } from 'react';
import { PageBackButton } from '../app/components/PageBackButton';
import { apiUrl } from '../utils/apiOrigin';

function linesToList(text: string): string[] {
  return text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);
}

function listToLines(items: string[]): string {
  return items.join('\n');
}

type ProfileLineRow = {
  id?: string;
  text: string;
  origin: 'user' | 'system';
  channel?: string;
  created_at?: string;
};

type MemoryFactRow = {
  id?: string;
  category: string;
  text: string;
  source?: string;
  created_at?: string;
  subject_ref?: string;
  predicate?: string;
  object_value?: string;
  evidence?: string;
  status?: string;
};

const CHANNEL_LABEL: Record<string, string> = {
  profile: 'Profile',
  clarification: 'Clarification',
  shadow: 'Shadow',
  personalize: 'Personalize',
  legacy: 'Recorded',
};

const MEMORY_CAT_LABEL: Record<string, string> = {
  identity: 'Identity',
  views: 'Views & opinions',
  behavior: 'Behavior & habits',
  goals: 'Goals',
  constraints: 'Constraints',
  other: 'Other',
};

export default function ProfilePage() {
  const [userPriorities, setUserPriorities] = useState('');
  const [clarificationRows, setClarificationRows] = useState<ProfileLineRow[]>([]);
  const [systemRows, setSystemRows] = useState<ProfileLineRow[]>([]);
  const [memoryFacts, setMemoryFacts] = useState<MemoryFactRow[]>([]);
  const [aboutMe, setAboutMe] = useState('');
  const [constraints, setConstraints] = useState('');
  const [values, setValues] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await fetch(apiUrl('/api/profile'));
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as {
        user_priorities?: string[];
        priorities?: string[];
        inferred_priorities?: string[];
        priority_lines?: ProfileLineRow[];
        memory_facts?: MemoryFactRow[];
        about_me: string;
        constraints: string[];
        values: string[];
      };
      const pl = data.priority_lines;
      if (Array.isArray(pl) && pl.length > 0) {
        const profileOnly = pl.filter((x) => x.origin === 'user' && x.channel === 'profile').map((x) => x.text);
        setUserPriorities(listToLines(profileOnly));
        setClarificationRows(pl.filter((x) => x.origin === 'user' && x.channel === 'clarification'));
        setSystemRows(pl.filter((x) => x.origin === 'system'));
      } else {
        const stated = data.user_priorities?.length ? data.user_priorities : (data.priorities ?? []);
        setUserPriorities(listToLines(stated));
        setClarificationRows([]);
        setSystemRows(
          (data.inferred_priorities ?? []).map((text) => ({
            text,
            origin: 'system' as const,
            channel: 'legacy',
          })),
        );
      }
      setMemoryFacts(Array.isArray(data.memory_facts) ? data.memory_facts : []);
      setAboutMe(data.about_me ?? '');
      setConstraints(listToLines(data.constraints ?? []));
      setValues(listToLines(data.values ?? []));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load profile');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setMessage(null);
    setError(null);
    try {
      const body = {
        user_priorities: linesToList(userPriorities),
        priorities: linesToList(userPriorities),
        about_me: aboutMe.trim(),
        constraints: linesToList(constraints),
        values: linesToList(values),
      };
      const res = await fetch(apiUrl('/api/profile'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as { ok?: boolean; path?: string };
      setMessage(data.path ? `Saved to ${data.path}` : 'Saved.');
      void load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    }
  };

  const deletePriorityLine = async (id: string) => {
    if (!id) {
      setError('This row has no id yet — save the profile once to assign ids, then delete.');
      return;
    }
    setDeletingId(id);
    setError(null);
    try {
      const res = await fetch(apiUrl(`/api/profile/priority-line/${encodeURIComponent(id)}`), { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      setMessage('Removed.');
      void load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setDeletingId(null);
    }
  };

  const deleteMemoryFact = async (id: string) => {
    if (!id) return;
    setDeletingId(id);
    setError(null);
    try {
      const res = await fetch(apiUrl(`/api/profile/memory-fact/${encodeURIComponent(id)}`), { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      setMessage('Memory fact removed.');
      void load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Delete failed');
    } finally {
      setDeletingId(null);
    }
  };

  const factsByCat = memoryFacts.reduce<Record<string, MemoryFactRow[]>>((acc, f) => {
    const k = f.category || 'other';
    if (!acc[k]) acc[k] = [];
    acc[k].push(f);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fff5fb] via-[#f5f3ff] to-[#f0f9ff] px-8 py-16">
      <div className="max-w-2xl mx-auto">
        <PageBackButton />
        <h1 className="text-3xl text-gray-900 mb-2" style={{ fontWeight: 700 }}>
          Profile
        </h1>
        <p className="text-gray-600 mb-8 text-sm leading-relaxed">
          Stored per <code className="text-xs bg-white/80 px-1 rounded">FORESIGHT_USER_ID</code> under{' '}
          <code className="text-xs bg-white/80 px-1 rounded">data/profile/</code>.{' '}
          <strong>Priorities you type below</strong> are only what you author in Profile — not clarification popups or
          machine notes. Structured <strong>memory facts</strong> (identity, views, …) are captured from Shadow space
          as concrete lines you can audit or delete.
        </p>

        {error && <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm">{error}</div>}
        {message && <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-sm">{message}</div>}

        <div className="space-y-6">
          <div>
            <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 600 }}>
              Your priorities (one per line)
            </label>
            <p className="text-xs text-gray-500 mb-2 leading-relaxed">
              Only rows you enter here. Clarification answers and system-inferred lines are kept separate so nothing
              automatic overwrites this list.
            </p>
            <textarea
              value={userPriorities}
              onChange={(e) => setUserPriorities(e.target.value)}
              className="w-full min-h-[100px] px-4 py-3 rounded-2xl border border-gray-200/80 bg-white/70 text-sm"
              placeholder={'Family first\nCareer growth in AI'}
            />
          </div>

          {clarificationRows.length > 0 && (
            <div>
              <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 600 }}>
                From clarification (saved with a decision run)
              </label>
              <p className="text-xs text-gray-500 mb-2 leading-relaxed">
                These came from multiple-choice prompts — not the same as free-form priorities. You can remove any row.
              </p>
              <div className="w-full min-h-[60px] px-4 py-3 rounded-2xl border border-amber-100 bg-amber-50/50 text-sm text-gray-800 space-y-2">
                {clarificationRows.map((row, idx) => (
                  <div key={row.id || `clar-${idx}`} className="flex flex-wrap items-start gap-2 justify-between">
                    <div className="flex flex-wrap items-start gap-2 min-w-0">
                      <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-amber-200/80 text-amber-950">
                        {CHANNEL_LABEL[row.channel || 'clarification'] || 'Clarification'}
                      </span>
                      <span className="min-w-0 flex-1 leading-snug">{row.text}</span>
                    </div>
                    <button
                      type="button"
                      disabled={deletingId === row.id}
                      onClick={() => row.id && void deletePriorityLine(row.id)}
                      className="shrink-0 text-xs text-red-700 hover:underline disabled:opacity-40"
                    >
                      {deletingId === row.id ? '…' : 'Remove'}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 600 }}>
              Structured memory (from Shadow &amp; imports)
            </label>
            <p className="text-xs text-gray-500 mb-2 leading-relaxed">
              Short, categorized facts — not therapist paraphrases. Delete anything that is wrong or outdated.
            </p>
            <div className="w-full min-h-[80px] px-4 py-3 rounded-2xl border border-violet-100 bg-violet-50/40 text-sm text-gray-800 space-y-4">
              {memoryFacts.length === 0 ? (
                <span className="text-gray-400 text-sm">
                  No structured facts yet — they appear when Shadow chat stores concrete details you stated.
                </span>
              ) : (
                Object.entries(factsByCat).map(([cat, rows]) => (
                  <div key={cat}>
                    <p className="text-[10px] font-bold uppercase tracking-wide text-violet-800 mb-2">
                      {MEMORY_CAT_LABEL[cat] || cat}
                    </p>
                    <ul className="space-y-2">
                      {rows.map((f) => (
                        <li key={f.id || f.text} className="flex items-start justify-between gap-2">
                          <span className="min-w-0 leading-snug">
                            {f.text}
                            {f.predicate && f.object_value ? (
                              <span className="block text-[10px] text-gray-500 mt-0.5 font-mono leading-tight">
                                {(f.subject_ref || 'user').trim()} · {f.predicate} · {f.object_value}
                              </span>
                            ) : null}
                            {f.evidence ? (
                              <span className="block text-[10px] text-violet-700/90 mt-0.5 italic">
                                Evidence: {f.evidence}
                              </span>
                            ) : null}
                          </span>
                          <button
                            type="button"
                            disabled={deletingId === f.id}
                            onClick={() => f.id && void deleteMemoryFact(f.id)}
                            className="shrink-0 text-xs text-red-700 hover:underline disabled:opacity-40"
                          >
                            {deletingId === f.id ? '…' : 'Delete'}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 600 }}>
              Legacy system lines (one-line notes)
            </label>
            <p className="text-xs text-gray-500 mb-2 leading-relaxed">
              Older inferred lines (e.g. from Personalize). Prefer structured memory above for new data. You can delete
              rows here.
            </p>
            <div className="w-full min-h-[80px] px-4 py-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 text-sm text-gray-800 space-y-2">
              {systemRows.length === 0 ? (
                <span className="text-gray-400">None.</span>
              ) : (
                systemRows.map((row, idx) => (
                  <div key={row.id || `${row.channel}-${idx}`} className="flex flex-wrap items-start gap-2 justify-between">
                    <div className="flex flex-wrap items-start gap-2 min-w-0">
                      <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-indigo-200/80 text-indigo-900">
                        {CHANNEL_LABEL[row.channel || 'legacy'] || row.channel || 'Recorded'}
                      </span>
                      <span className="min-w-0 flex-1 leading-snug">{row.text}</span>
                    </div>
                    <button
                      type="button"
                      disabled={deletingId === row.id}
                      onClick={() => row.id && void deletePriorityLine(row.id)}
                      className="shrink-0 text-xs text-red-700 hover:underline disabled:opacity-40"
                    >
                      {deletingId === row.id ? '…' : 'Delete'}
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 500 }}>
              About me
            </label>
            <textarea
              value={aboutMe}
              onChange={(e) => setAboutMe(e.target.value)}
              className="w-full min-h-[120px] px-4 py-3 rounded-2xl border border-gray-200/80 bg-white/70 text-sm"
              placeholder="Short narrative: values, risk tolerance, context…"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 500 }}>
              Constraints (one per line)
            </label>
            <textarea
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              className="w-full min-h-[80px] px-4 py-3 rounded-2xl border border-gray-200/80 bg-white/70 text-sm"
              placeholder="Cannot relocate before 2027&#10;Max 50h weeks"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-700 mb-2" style={{ fontWeight: 500 }}>
              Values (one per line)
            </label>
            <textarea
              value={values}
              onChange={(e) => setValues(e.target.value)}
              className="w-full min-h-[80px] px-4 py-3 rounded-2xl border border-gray-200/80 bg-white/70 text-sm"
              placeholder="Honesty&#10;Autonomy"
            />
          </div>
          <button
            type="button"
            onClick={() => void save()}
            className="px-8 py-3 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 text-white text-sm font-semibold shadow-lg"
          >
            Save profile
          </button>
        </div>
      </div>
    </div>
  );
}
