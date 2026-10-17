import type { Decision, ReviewStatus } from '../api/types';

export const pct = (v: number, digits = 1) => `${(v * 100).toFixed(digits)}%`;
export const num = (v: number, digits = 3) => v.toFixed(digits);
export const int = (v: number) => v.toLocaleString();

export function bytes(v: number) {
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`;
}

export const dateTime = (epochMs: number) =>
  new Date(epochMs).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

export function relative(epochMs: number) {
  const s = Math.round((Date.now() - epochMs) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return dateTime(epochMs);
}

export const decisionLabel: Record<Decision, string> = {
  high_risk: 'High risk',
  review: 'Needs review',
  low_risk: 'Low risk',
};

export const statusLabel: Record<ReviewStatus, string> = {
  pending: 'Pending',
  confirmed: 'Confirmed',
  rejected: 'Rejected',
};

/** Humanise identifiers such as `unreviewed_mixed_source_demonstration`. */
export const humanise = (s: string) => s.replace(/[_-]+/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

const representations: Record<string, string> = {
  tfidf: 'Character TF-IDF',
  e5: 'Multilingual E5 embeddings',
};
export const representationLabel = (r: string) => representations[r] ?? humanise(r);

/**
 * How to describe scores and novelty for the serving model. Calibration and
 * representation come from GET /api/v1/model, so wording follows the model.
 */
export function modelWording(m?: { scores_calibrated: boolean; representation: string } | null) {
  const novelty = !m || m.representation === 'tfidf' ? 'lexical' : 'semantic';
  return {
    novelty,
    score: m?.scores_calibrated ? 'Calibrated score.' : 'Uncalibrated — a ranking score, not a probability.',
    summary: `${m?.scores_calibrated ? 'Scores are calibrated' : 'Scores are uncalibrated'} and novelty is ${novelty}.`,
  };
}
