import { api, ApiError } from '../api/client';
import type { Prediction } from '../api/types';
import { addEvidence } from './evidence';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Score one message. A full engine queue (429) is retried with the same event
 * ID after Retry-After, which the server treats as the same report.
 */
export async function scoreMessage(text: string, eventId: string, attempts = 4): Promise<Prediction> {
  for (let i = 1; ; i++) {
    try {
      const p = await api.predict({ text, event_id: eventId });
      addEvidence(text, p);
      return p;
    } catch (e) {
      if (!(e instanceof ApiError) || e.status !== 429 || i >= attempts) throw e;
      await sleep((e.retryAfter ?? 1) * 1000);
    }
  }
}
