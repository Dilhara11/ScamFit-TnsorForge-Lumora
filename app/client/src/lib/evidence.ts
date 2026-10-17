import { useSyncExternalStore } from 'react';
import type { Prediction } from '../api/types';

/**
 * The server never stores raw message text. Representative cluster members are
 * returned as event IDs only, so this browser keeps its own private copy of
 * what it submitted, keyed by event ID, to let analysts read cluster evidence.
 */
export interface EvidenceItem {
  text: string;
  prediction: Prediction;
  submittedAt: number;
}

const KEY = 'svo.evidence';
const RETAIN_KEY = 'svo.evidence.retain';
const MAX_ITEMS = 500;

type Store = { retain: boolean; items: EvidenceItem[] };

function load(): Store {
  try {
    const retain = localStorage.getItem(RETAIN_KEY) !== 'false';
    const items = retain ? (JSON.parse(localStorage.getItem(KEY) ?? '[]') as EvidenceItem[]) : [];
    return { retain, items };
  } catch {
    return { retain: true, items: [] };
  }
}

let store = load();
const listeners = new Set<() => void>();

function commit(next: Store) {
  store = next;
  try {
    localStorage.setItem(RETAIN_KEY, String(next.retain));
    if (next.retain) localStorage.setItem(KEY, JSON.stringify(next.items));
    else localStorage.removeItem(KEY);
  } catch {
    /* quota or privacy mode: in-memory only */
  }
  listeners.forEach((l) => l());
}

export function addEvidence(text: string, prediction: Prediction) {
  const items = [
    { text, prediction, submittedAt: Date.now() },
    ...store.items.filter((i) => i.prediction.event_id !== prediction.event_id),
  ].slice(0, MAX_ITEMS);
  commit({ ...store, items });
}

export const clearEvidence = () => commit({ ...store, items: [] });
export const setRetainEvidence = (retain: boolean) => commit({ retain, items: retain ? store.items : [] });

export function useEvidence() {
  return useSyncExternalStore(
    (l) => (listeners.add(l), () => listeners.delete(l)),
    () => store,
  );
}
