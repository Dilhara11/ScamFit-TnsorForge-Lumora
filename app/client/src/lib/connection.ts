import { useSyncExternalStore } from 'react';

/**
 * Connection settings live in sessionStorage only, never in the built bundle.
 * The API key is cleared when the tab closes.
 */
export interface Connection {
  baseUrl: string;
  apiKey: string;
  analyst: string;
}

const KEY = 'svo.connection';
const defaults: Connection = {
  baseUrl: import.meta.env.VITE_SVO_API_BASE_URL ?? '',
  apiKey: '',
  analyst: '',
};

function load(): Connection {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? { ...defaults, ...JSON.parse(raw) } : defaults;
  } catch {
    return defaults;
  }
}

let current = load();
const listeners = new Set<() => void>();

export const getConnection = () => current;

export function setConnection(next: Partial<Connection>) {
  current = { ...current, ...next };
  try {
    sessionStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    /* storage unavailable: keep in memory */
  }
  listeners.forEach((l) => l());
}

export function useConnection() {
  return useSyncExternalStore(
    (l) => (listeners.add(l), () => listeners.delete(l)),
    getConnection,
  );
}
