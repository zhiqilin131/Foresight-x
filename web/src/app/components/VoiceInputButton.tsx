import { Mic, Square, Upload } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { apiUrl } from '../../utils/apiOrigin';

type SpeechRecCtor = new () => {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((ev: Event) => void) | null;
  onerror: ((ev: Event) => void) | null;
  onend: (() => void) | null;
};

function getSpeechRecognition(): SpeechRecCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { SpeechRecognition?: SpeechRecCtor; webkitSpeechRecognition?: SpeechRecCtor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

interface VoiceInputButtonProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  /** Prefer browser STT; still show upload as fallback */
  compact?: boolean;
}

export function VoiceInputButton({ onTranscript, disabled, compact }: VoiceInputButtonProps) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<InstanceType<SpeechRecCtor> | null>(null);

  const stop = useCallback(() => {
    try {
      recRef.current?.stop();
    } catch {
      /* noop */
    }
    setListening(false);
  }, []);

  const start = useCallback(() => {
    if (disabled) return;
    setError(null);
    const SR = getSpeechRecognition();
    if (!SR) {
      setError('This browser does not support live speech-to-text. Try Chrome or Edge, or upload an audio file.');
      return;
    }
    const r = new SR();
    r.lang = 'en-US';
    r.continuous = false;
    r.interimResults = false;
    r.onresult = (ev: Event) => {
      const e = ev as unknown as { results: Array<Array<{ transcript?: string }>> };
      const t = e.results?.[0]?.[0]?.transcript?.trim();
      if (t) onTranscript(t);
      setListening(false);
    };
    r.onerror = () => {
      setError('Speech recognition failed. Try uploading audio instead.');
      setListening(false);
    };
    r.onend = () => setListening(false);
    recRef.current = r;
    try {
      r.start();
      setListening(true);
    } catch {
      setError('Could not start the microphone.');
      setListening(false);
    }
  }, [disabled, onTranscript]);

  useEffect(() => {
    return () => {
      try {
        recRef.current?.abort();
      } catch {
        /* noop */
      }
    };
  }, []);

  const uploadAudio = async (file: File) => {
    if (disabled) return;
    setError(null);
    const fd = new FormData();
    fd.append('file', file, file.name);
    try {
      const res = await fetch(apiUrl('/api/transcribe'), { method: 'POST', body: fd });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }
      const j = (await res.json()) as { text?: string };
      if (j.text) onTranscript(j.text);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Transcription failed');
    }
  };

  return (
    <div className={`flex ${compact ? 'flex-row items-center gap-2' : 'flex-col items-end gap-1'}`}>
      <div className="flex items-center gap-2">
        <label
          className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-full text-xs border border-gray-200 bg-white/80 hover:bg-white cursor-pointer ${
            disabled ? 'opacity-50 pointer-events-none' : ''
          }`}
        >
          <Upload className="w-3.5 h-3.5 text-purple-600" aria-hidden />
          <span>Upload audio</span>
          <input
            type="file"
            accept="audio/*"
            className="hidden"
            disabled={disabled}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void uploadAudio(f);
              e.target.value = '';
            }}
          />
        </label>
        <button
          type="button"
          disabled={disabled}
          onClick={() => (listening ? stop() : start())}
          className={`inline-flex items-center justify-center w-10 h-10 rounded-full border transition-all ${
            listening
              ? 'border-red-300 bg-red-50 text-red-700'
              : 'border-purple-200 bg-white/90 text-purple-800 hover:bg-purple-50'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
          title={listening ? 'Stop' : 'Voice input'}
          aria-pressed={listening}
        >
          {listening ? <Square className="w-4 h-4 fill-current" /> : <Mic className="w-4 h-4" />}
        </button>
      </div>
      {error && <span className="text-xs text-amber-800 max-w-[220px] text-right leading-snug">{error}</span>}
    </div>
  );
}
