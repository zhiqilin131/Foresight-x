import { useCallback, useRef, useState } from 'react';
import { Link } from 'react-router';
import { Mail, MessageCircle, Plug, Sparkles } from 'lucide-react';
import { PageBackButton } from '../app/components/PageBackButton';
import { apiUrl } from '../utils/apiOrigin';

type PluginId = 'gmail' | 'messenger' | 'slack';

const PLUGINS: { id: PluginId; label: string; sub: string }[] = [
  { id: 'gmail', label: 'Gmail', sub: 'Read threads (OAuth) — planned' },
  { id: 'messenger', label: 'Messenger', sub: 'Meta chat export — planned' },
  { id: 'slack', label: 'Slack', sub: 'Workspace history — planned' },
];

export default function PersonalizePage() {
  const [text, setText] = useState('');
  const [connectBanner, setConnectBanner] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    summary_lines: string[];
    profile_path?: string;
    confidence?: number;
    last_updated?: string;
  } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onFakeConnect = (id: PluginId) => {
    setConnectBanner(`Connect failed: ${id} integration is not available in this build. (The protocol is defined; paste or upload text below instead.)`);
  };

  const onPickFile = useCallback(() => fileRef.current?.click(), []);

  const onFile = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.txt')) {
      setError('Please choose a .txt file.');
      e.target.value = '';
      return;
    }
    setError(null);
    const reader = new FileReader();
    reader.onload = () => {
      const t = typeof reader.result === 'string' ? reader.result : '';
      setText(t);
    };
    reader.readAsText(f, 'UTF-8');
    e.target.value = '';
  }, []);

  const analyze = useCallback(async () => {
    const body = text.trim();
    if (!body || sending) return;
    setError(null);
    setResult(null);
    setSending(true);
    try {
      const res = await fetch(apiUrl('/api/personalization/ingest'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: body }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const data = (await res.json()) as {
        ok?: boolean;
        summary_lines?: string[];
        profile_path?: string;
        confidence?: number;
        last_updated?: string;
      };
      setResult({
        summary_lines: Array.isArray(data.summary_lines) ? data.summary_lines : [],
        profile_path: data.profile_path,
        confidence: data.confidence,
        last_updated: data.last_updated,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
    } finally {
      setSending(false);
    }
  }, [text, sending]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fff5fb] via-[#f5f3ff] to-[#f0f9ff] px-6 py-12">
      <div className="max-w-2xl mx-auto">
        <PageBackButton />
        <header className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
              <Sparkles className="w-6 h-6 text-white" aria-hidden />
            </div>
            <div>
              <h1 className="text-2xl md:text-3xl text-gray-900" style={{ fontWeight: 700 }}>
                Personalize from chats &amp; email
              </h1>
              <p className="text-sm text-gray-600 mt-1 leading-relaxed">
                The model updates its picture of you: habits, tensions, and goals implied in your own words. Not therapy —
                pattern extraction only.
              </p>
            </div>
          </div>
        </header>

        <section className="mb-8 rounded-3xl border border-white/80 bg-white/60 backdrop-blur-sm p-5">
          <div className="flex items-center gap-2 text-sm font-semibold text-gray-900 mb-3">
            <Plug className="w-4 h-4 text-violet-600 shrink-0" aria-hidden />
            Connect sources (preview)
          </div>
          <p className="text-xs text-gray-500 mb-4 leading-relaxed">
            OAuth integrations are stubbed: Gmail and Messenger could plug in here; this demo only accepts manual paste or
            .txt upload.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {PLUGINS.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onFakeConnect(p.id)}
                className="text-left rounded-2xl border border-gray-200/80 bg-white/80 px-4 py-3 hover:border-violet-300/80 transition-colors"
              >
                <div className="text-sm font-medium text-gray-900">{p.label}</div>
                <div className="text-xs text-gray-500 mt-1">{p.sub}</div>
              </button>
            ))}
          </div>
          {connectBanner && (
            <div className="mt-4 text-sm text-amber-900 bg-amber-50/95 border border-amber-200/80 rounded-xl px-4 py-3">
              {connectBanner}
            </div>
          )}
        </section>

        <section className="rounded-3xl border border-white/80 bg-white/70 backdrop-blur-sm p-5 mb-6">
          <label className="block text-sm font-semibold text-gray-900 mb-2">Paste text or upload a .txt export</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste email threads, chat logs, or notes…"
            rows={12}
            className="w-full px-4 py-3 rounded-2xl border border-gray-200/80 bg-white/90 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-400/40 min-h-[200px]"
          />
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <input ref={fileRef} type="file" accept=".txt,text/plain" className="hidden" onChange={onFile} />
            <button
              type="button"
              onClick={onPickFile}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-gray-200 bg-white text-sm text-gray-800 hover:bg-gray-50"
            >
              <Mail className="w-4 h-4 text-violet-600" aria-hidden />
              Upload .txt
            </button>
            <span className="text-xs text-gray-500">Plain text only; large pastes are truncated server-side.</span>
          </div>
        </section>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm whitespace-pre-wrap">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={() => void analyze()}
          disabled={!text.trim() || sending}
          className="w-full py-3.5 rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-sm font-semibold disabled:opacity-40 shadow-lg shadow-violet-500/15"
        >
          {sending ? 'Analyzing…' : 'Analyze & update perceived profile'}
        </button>

        {result && (
          <div className="mt-8 rounded-3xl border border-emerald-200/80 bg-emerald-50/50 p-5">
            <h2 className="text-sm font-semibold text-emerald-950 mb-3">Saved to your machine-perceived profile</h2>
            <ul className="space-y-2 text-sm text-gray-800">
              {result.summary_lines.map((line, i) => (
                <li key={i} className="flex gap-2">
                  <MessageCircle className="w-4 h-4 text-emerald-700 shrink-0 mt-0.5" aria-hidden />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
            {result.last_updated && (
              <p className="text-xs text-gray-500 mt-4">Updated {result.last_updated}</p>
            )}
            {typeof result.confidence === 'number' && (
              <p className="text-xs text-gray-500">Profile confidence (rough): {result.confidence.toFixed(2)}</p>
            )}
            {result.profile_path && <p className="text-xs text-gray-400 mt-2 font-mono break-all">{result.profile_path}</p>}
            <Link
              to="/profile"
              className="inline-block mt-5 text-sm font-medium text-violet-700 underline underline-offset-2"
            >
              Open Profile to review inferred fields
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
