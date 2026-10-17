import type {
  Cluster,
  ClusterDetail,
  ErrorEnvelope,
  ModelInfo,
  Monitoring,
  Page,
  Prediction,
  PredictionRequest,
  Ready,
  ReviewAudit,
  ReviewRequest,
  ReviewResult,
  ReviewStatus,
} from './types';
import { getConnection } from '../lib/connection';

/** An API failure carrying the server's error envelope where one exists. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string | null;
  readonly retryAfter: number | null;

  constructor(status: number, code: string, message: string, requestId: string | null, retryAfter: number | null) {
    super(message);
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.retryAfter = retryAfter;
  }

  /** Safe to resend with the same idempotency ID. */
  get retryable() {
    return this.status === 0 || this.status === 408 || this.status === 429 || this.status >= 500;
  }
}

async function request<T>(path: string, init: RequestInit = {}, signal?: AbortSignal): Promise<T> {
  const { baseUrl, apiKey } = getConnection();
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  if (apiKey) headers.set('X-API-Key', apiKey);
  if (init.body) headers.set('Content-Type', 'application/json');

  let res: Response;
  try {
    res = await fetch(baseUrl.replace(/\/+$/, '') + path, { ...init, headers, signal });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new ApiError(0, 'network_error', 'Cannot reach the API. Check that the service is running.', null, null);
  }

  const requestId = res.headers.get('X-Request-ID');
  const retryAfterHeader = res.headers.get('Retry-After');
  const retryAfter = retryAfterHeader ? Number(retryAfterHeader) || null : null;
  const body = await res.json().catch(() => null);

  if (!res.ok) {
    const env = body as ErrorEnvelope | null;
    throw new ApiError(
      res.status,
      env?.error?.code ?? 'http_error',
      env?.error?.message ?? `Request failed with status ${res.status}`,
      env?.error?.request_id ?? requestId,
      retryAfter,
    );
  }
  return body as T;
}

const post = <T>(path: string, payload: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(payload) });

function query(params: Record<string, string | number | null | undefined>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== '') q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : '';
}

export const api = {
  ready: (signal?: AbortSignal) => request<Ready>('/health/ready', {}, signal),
  model: (signal?: AbortSignal) => request<ModelInfo>('/api/v1/model', {}, signal),
  monitoring: (signal?: AbortSignal) => request<Monitoring>('/api/v1/monitoring', {}, signal),
  predict: (body: PredictionRequest) => post<Prediction>('/api/v1/predictions', body),
  clusters: (p: { status?: ReviewStatus | null; limit?: number; after_id?: number }, signal?: AbortSignal) =>
    request<Page<Cluster>>(`/api/v1/clusters${query(p)}`, {}, signal),
  cluster: (id: number, signal?: AbortSignal) => request<ClusterDetail>(`/api/v1/clusters/${id}`, {}, signal),
  review: (id: number, body: ReviewRequest) => post<ReviewResult>(`/api/v1/clusters/${id}/reviews`, body),
  reviews: (id: number, p: { limit?: number; after_id?: number }, signal?: AbortSignal) =>
    request<Page<ReviewAudit>>(`/api/v1/clusters/${id}/reviews${query(p)}`, {}, signal),
};
