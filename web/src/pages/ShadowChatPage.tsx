import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';
import { PageBackButton } from '../app/components/PageBackButton';
import { VoiceInputButton } from '../app/components/VoiceInputButton';
import { apiUrl } from '../utils/apiOrigin';

type Role = 'user' | 'assistant';

interface Msg {
  role: Role;
  content: string;
}

type ShadowToastState = { id: number; text: string; fadeOut: boolean };

export default function ShadowChatPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisionModal, setDecisionModal] = useState(false);
  const [shadowToast, setShadowToast] = useState<ShadowToastState | null>(null);
  const toastIdRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);

  const showRecordedToast = useCallback((text: string) => {
    const id = ++toastIdRef.current;
    setShadowToast({ id, text, fadeOut: false });
    window.setTimeout(() => {
      setShadowToast((t) => (t?.id === id ? { ...t, fadeOut: true } : t));
    }, 2700);
    window.setTimeout(() => {
      setShadowToast((t) => (t?.id === id ? null : t));
    }, 3000);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;
    setError(null);
    setInput('');
    const before = messages;
    const next: Msg[] = [...before, { role: 'user', content: text }];
    setMessages(next);
    setSending(true);
    try {
      const res = await fetch(apiUrl('/api/shadow/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: next.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const data = (await res.json()) as {
        reply: string;
        suggest_decision_navigation?: boolean;
        recorded_observation?: string | null;
      };
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      if (data.suggest_decision_navigation) setDecisionModal(true);
      if (data.recorded_observation && data.recorded_observation.trim()) {
        showRecordedToast(data.recorded_observation.trim());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed');
      setMessages(before);
    } finally {
      setSending(false);
    }
  }, [input, messages, sending, showRecordedToast]);

  const appendVoice = (t: string) => {
    setInput((s) => (s.trim() ? `${s.trim()} ${t}` : t));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#fff5fb] via-[#f5f3ff] to-[#f0f9ff] px-6 py-12 relative">
      {shadowToast && (
        <div
          className="fixed bottom-8 left-1/2 z-[100] w-[min(92vw,28rem)] -translate-x-1/2 pointer-events-none"
          role="status"
          aria-live="polite"
        >
          <div
            className={`rounded-2xl border border-purple-200/80 bg-white/95 px-4 py-3 shadow-lg shadow-purple-500/10 backdrop-blur-sm transition-opacity duration-300 ease-out ${
              shadowToast.fadeOut ? 'opacity-0' : 'opacity-100'
            }`}
          >
            <p className="text-xs font-semibold text-purple-900 uppercase tracking-wide">Recorded</p>
            <p className="text-sm text-gray-800 mt-1 leading-snug line-clamp-4">
              Noted for your shadow profile: {shadowToast.text}
            </p>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto">
        <PageBackButton />
        <header className="mb-6">
          <h1 className="text-2xl md:text-3xl text-gray-900" style={{ fontWeight: 700 }}>
            Shadow space
          </h1>
          <p className="text-sm text-gray-600 mt-2 leading-relaxed">
            Pure chat: therapist-leaning, friendly presence. No decision recommendations here — patterns may be noted in
            your shadow profile.
          </p>
        </header>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm whitespace-pre-wrap">
            {error}
          </div>
        )}

        <div className="rounded-3xl border border-white/80 bg-white/60 backdrop-blur-sm p-4 min-h-[320px] max-h-[55vh] overflow-y-auto mb-4 space-y-4">
          {messages.length === 0 && (
            <p className="text-sm text-gray-500 text-center py-12">
              Say anything on your mind.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={`${i}-${m.role}`}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-purple-600 text-white rounded-br-md'
                    : 'bg-white border border-gray-100 text-gray-800 rounded-bl-md shadow-sm'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-2 bg-white/80 border border-gray-100 text-xs text-gray-500">
                …
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="space-y-3">
          <div className="relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder="Type or use voice… Shift+Enter for newline"
              rows={4}
              disabled={sending}
              className="w-full px-4 py-3 pr-28 bg-white/80 border border-gray-200/80 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-purple-400/40 text-sm text-gray-900"
            />
            <div className="absolute bottom-3 right-3">
              <VoiceInputButton onTranscript={appendVoice} disabled={sending} compact />
            </div>
          </div>
          <button
            type="button"
            onClick={() => void send()}
            disabled={!input.trim() || sending}
            className="w-full py-3 rounded-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white text-sm font-semibold disabled:opacity-40"
          >
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>

        <p className="mt-6 text-center text-xs text-gray-500">
          Need a structured decision analysis?{' '}
          <Link to="/" className="text-purple-700 underline">
            Foresight decision mode
          </Link>
        </p>
      </div>

      {decisionModal && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/45 backdrop-blur-sm">
          <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full p-6 border border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Switch to decision mode?</h2>
            <p className="text-sm text-gray-600 mb-6 leading-relaxed">
              Shadow space does not rank options or score choices here. For evidence-grounded decision analysis, run a
              full Foresight-X pipeline from the home screen.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-end">
              <button
                type="button"
                className="px-4 py-2.5 rounded-full border border-gray-200 text-gray-800 text-sm"
                onClick={() => setDecisionModal(false)}
              >
                Stay here
              </button>
              <button
                type="button"
                className="px-4 py-2.5 rounded-full bg-purple-600 text-white text-sm font-medium"
                onClick={() => navigate('/')}
              >
                Go to decision mode
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
