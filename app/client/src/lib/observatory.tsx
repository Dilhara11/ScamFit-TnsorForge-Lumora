import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { api } from '../api/client';
import type { ModelInfo, Monitoring, Ready, Window } from '../api/types';
import { useApi, type AsyncState } from './hooks';

/**
 * The API exposes only the latest monitoring window. To show a trend, this
 * browser records each distinct window it observes (per model version) in
 * sessionStorage. The chart is therefore a session view, not full history.
 */
const HISTORY_KEY = 'svo.windows';
const HISTORY_MAX = 120;

function loadHistory(): Record<string, Window[]> {
  try {
    return JSON.parse(sessionStorage.getItem(HISTORY_KEY) ?? '{}');
  } catch {
    return {};
  }
}

interface Observatory {
  ready: AsyncState<Ready>;
  model: AsyncState<ModelInfo>;
  monitoring: AsyncState<Monitoring>;
  windows: Window[];
}

const Ctx = createContext<Observatory | null>(null);

export function ObservatoryProvider({ children }: { children: ReactNode }) {
  const ready = useApi((s) => api.ready(s), [], 15000);
  const model = useApi((s) => api.model(s), [ready.data?.model_version]);
  const monitoring = useApi((s) => api.monitoring(s), [], 10000);
  const [history, setHistory] = useState(loadHistory);

  const m = monitoring.data;
  useEffect(() => {
    const w = m?.latest_window;
    if (!m || !w) return;
    setHistory((h) => {
      const series = h[m.model_version] ?? [];
      if (series.some((s) => s.end_seq === w.end_seq)) return h;
      const next = { ...h, [m.model_version]: [...series, w].sort((a, b) => a.end_seq - b.end_seq).slice(-HISTORY_MAX) };
      try {
        sessionStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      } catch {
        /* in-memory only */
      }
      return next;
    });
  }, [m]);

  const windows = m ? (history[m.model_version] ?? []) : [];
  return <Ctx.Provider value={{ ready, model, monitoring, windows }}>{children}</Ctx.Provider>;
}

export function useObservatory() {
  const v = useContext(Ctx);
  if (!v) throw new Error('useObservatory outside provider');
  return v;
}
