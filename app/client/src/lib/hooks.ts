import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { useConnection } from './connection';

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Fetch on mount, on dependency change, on connection change, and optionally
 * on an interval. Keeps the last good data visible while refreshing.
 */
export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
  intervalMs?: number,
): AsyncState<T> {
  const conn = useConnection();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  useEffect(() => {
    const ctrl = new AbortController();
    setLoading(true);
    fetcherRef
      .current(ctrl.signal)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => {
        if (e?.name !== 'AbortError') setError(e instanceof ApiError ? e : new ApiError(0, 'client_error', String(e), null, null));
      })
      .finally(() => !ctrl.signal.aborted && setLoading(false));
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, conn.baseUrl, conn.apiKey]);

  useEffect(() => {
    if (!intervalMs) return;
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') setTick((t) => t + 1);
    }, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
