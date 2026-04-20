import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import { apiFetchErrorMessage, apiUrl } from '../../utils/apiOrigin';

type PersonaItem = {
  user_id: string;
  created_at?: string;
};

type PersonaListResp = {
  current_user_id: string;
  users: PersonaItem[];
};

const POS_KEY = 'fx_persona_fab_pos_v1';
const COLLAPSE_KEY = 'fx_persona_fab_collapsed_v1';
const FAB_W_COLLAPSED = 220;
const FAB_H_COLLAPSED = 48;
const FAB_W_EXPANDED = 320;
const FAB_H_EXPANDED = 220;
const EDGE_PAD = 12;

function clampPos(x: number, y: number, w: number, h: number) {
  const maxX = Math.max(EDGE_PAD, window.innerWidth - w - EDGE_PAD);
  const maxY = Math.max(EDGE_PAD, window.innerHeight - h - EDGE_PAD);
  return {
    x: Math.min(Math.max(EDGE_PAD, x), maxX),
    y: Math.min(Math.max(EDGE_PAD, y), maxY),
  };
}

function defaultPos(collapsed: boolean) {
  const w = collapsed ? FAB_W_COLLAPSED : FAB_W_EXPANDED;
  const h = collapsed ? FAB_H_COLLAPSED : FAB_H_EXPANDED;
  return clampPos(window.innerWidth - w - 20, window.innerHeight - h - 28, w, h);
}

export function PersonaSwitcher({ compact: _compact = false }: { compact?: boolean }) {
  const [items, setItems] = useState<PersonaItem[]>([]);
  const [current, setCurrent] = useState('');
  const [newId, setNewId] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    return window.localStorage.getItem(COLLAPSE_KEY) !== '0';
  });
  const [pos, setPos] = useState<{ x: number; y: number } | null>(() => {
    if (typeof window === 'undefined') return null;
    try {
      const raw = window.localStorage.getItem(POS_KEY);
      if (!raw) return null;
      const p = JSON.parse(raw) as { x: number; y: number };
      if (typeof p.x === 'number' && typeof p.y === 'number') return p;
    } catch {
      // ignore and use default
    }
    return null;
  });
  const dragRef = useRef<{ dx: number; dy: number; dragging: boolean }>({
    dx: 0,
    dy: 0,
    dragging: false,
  });

  const selectedExists = useMemo(() => items.some((x) => x.user_id === current), [items, current]);
  const panelW = collapsed ? FAB_W_COLLAPSED : FAB_W_EXPANDED;
  const panelH = collapsed ? FAB_H_COLLAPSED : FAB_H_EXPANDED;

  const load = useCallback(async () => {
    try {
      const res = await fetch(apiUrl('/api/personas'));
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as PersonaListResp;
      setItems(Array.isArray(data.users) ? data.users : []);
      setCurrent(String(data.current_user_id ?? ''));
    } catch (e) {
      setErr(apiFetchErrorMessage(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0');
    setPos((prev) => {
      const base = prev ?? defaultPos(collapsed);
      return clampPos(base.x, base.y, panelW, panelH);
    });
  }, [collapsed, panelH, panelW]);

  useEffect(() => {
    if (!pos || typeof window === 'undefined') return;
    window.localStorage.setItem(POS_KEY, JSON.stringify(pos));
  }, [pos]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!pos) setPos(defaultPos(collapsed));
  }, [collapsed, pos]);

  useEffect(() => {
    const onResize = () => {
      setPos((prev) => {
        const base = prev ?? defaultPos(collapsed);
        return clampPos(base.x, base.y, panelW, panelH);
      });
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [collapsed, panelH, panelW]);

  const beginDrag = (ev: ReactPointerEvent) => {
    if (ev.button !== 0) return;
    const x = pos?.x ?? defaultPos(collapsed).x;
    const y = pos?.y ?? defaultPos(collapsed).y;
    dragRef.current = {
      dx: ev.clientX - x,
      dy: ev.clientY - y,
      dragging: true,
    };
    const move = (e: PointerEvent) => {
      if (!dragRef.current.dragging) return;
      const nx = e.clientX - dragRef.current.dx;
      const ny = e.clientY - dragRef.current.dy;
      setPos(clampPos(nx, ny, panelW, panelH));
    };
    const up = () => {
      dragRef.current.dragging = false;
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const switchPersona = async (uid: string) => {
    if (!uid || uid === current) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(apiUrl('/api/personas/switch'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid }),
      });
      if (!res.ok) throw new Error(await res.text());
      setCurrent(uid);
      setMsg(`Switched to ${uid}`);
      // Force clean state reload so all pages refresh profile/memory scoped data.
      window.location.reload();
    } catch (e) {
      setErr(apiFetchErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const createPersona = async () => {
    const uid = newId.trim();
    if (!uid) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(apiUrl('/api/personas'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: uid }),
      });
      if (!res.ok) throw new Error(await res.text());
      setNewId('');
      await load();
      setMsg(`Created ${uid}`);
    } catch (e) {
      setErr(apiFetchErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const deletePersona = async () => {
    if (!selectedExists) return;
    if (!window.confirm(`Delete persona "${current}" and its memory/profile?`)) return;
    setBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(apiUrl(`/api/personas/${encodeURIComponent(current)}`), { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      await load();
      setMsg(`Deleted ${current}`);
    } catch (e) {
      setErr(apiFetchErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const left = pos?.x ?? defaultPos(collapsed).x;
  const top = pos?.y ?? defaultPos(collapsed).y;

  return (
    <div
      className="fixed z-[70] select-none"
      style={{ left, top, width: `${panelW}px` }}
      role="region"
      aria-label="Persona switcher"
    >
      {collapsed ? (
        <div className="flex items-center gap-2 rounded-full border border-purple-200/80 bg-white/95 shadow-lg backdrop-blur px-2 py-1.5">
          <button
            type="button"
            onPointerDown={beginDrag}
            className="px-2 py-1 text-gray-500 cursor-grab active:cursor-grabbing"
            title="Drag to move"
            aria-label="Drag to move persona button"
          >
            ⋮⋮
          </button>
          <button
            type="button"
            onClick={() => setCollapsed(false)}
            className="flex-1 text-left text-xs text-gray-700 truncate"
            title="Expand persona controls"
          >
            Persona: <span className="font-semibold">{current || 'loading...'}</span>
          </button>
        </div>
      ) : (
        <div className="rounded-2xl border border-purple-200/80 bg-white/95 shadow-xl backdrop-blur p-3 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <button
              type="button"
              onPointerDown={beginDrag}
              className="text-xs px-2 py-1 rounded-md border border-purple-200 bg-purple-50 text-purple-700 cursor-grab active:cursor-grabbing"
              title="Drag to move"
            >
              Move
            </button>
            <p className="text-xs font-semibold text-gray-700">Persona controls</p>
            <button
              type="button"
              onClick={() => setCollapsed(true)}
              className="text-xs px-2 py-1 rounded-md border border-gray-200 bg-white text-gray-600"
              title="Collapse"
            >
              Collapse
            </button>
          </div>
          <div className="space-y-2">
            <label className="block text-[11px] font-medium text-gray-600">Switch persona</label>
            <select
              className="w-full text-xs border border-purple-200 rounded-lg px-2 py-2 bg-white"
              disabled={busy}
              value={current}
              onChange={(e) => void switchPersona(e.target.value)}
              title="Switch persona"
            >
              {items.map((x) => (
                <option key={x.user_id} value={x.user_id}>
                  {x.user_id}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              placeholder="new_persona"
              className="flex-1 text-xs px-2 py-2 rounded-lg border border-purple-200 bg-white"
              disabled={busy}
            />
            <button
              type="button"
              onClick={() => void createPersona()}
              disabled={busy || !newId.trim()}
              className="text-xs px-3 py-2 rounded-lg bg-purple-600 text-white disabled:opacity-50"
            >
              Add
            </button>
            <button
              type="button"
              onClick={() => void deletePersona()}
              disabled={busy || !selectedExists}
              className="text-xs px-3 py-2 rounded-lg border border-red-300 text-red-700 bg-white disabled:opacity-50"
            >
              Delete
            </button>
          </div>
        </div>
      )}
      {msg && (
        <div className="mt-2 text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-2 py-1.5">
          {msg}
        </div>
      )}
      {err && (
        <div className="mt-2 text-[11px] text-red-700 bg-red-50 border border-red-200 rounded-lg px-2 py-1.5">
          {err}
        </div>
      )}
    </div>
  );
}
