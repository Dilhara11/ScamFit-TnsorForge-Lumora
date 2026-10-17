import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Check, CheckCircle2, Circle, FileText, History, Loader2, RotateCcw, ShieldCheck, ShieldX } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { ClusterDetail, DecisionConfig, ReviewAudit, ReviewResult, ReviewStatus } from '../api/types';
import { useConnection } from '../lib/connection';
import { useEvidence } from '../lib/evidence';
import { useApi } from '../lib/hooks';
import { newId } from '../lib/ids';
import { useObservatory } from '../lib/observatory';
import { dateTime, num, statusLabel } from '../lib/format';
import { CandidateBadge, Card, cx, DecisionBadge, Empty, ErrorNotice, Mono, Note, PageHeader, Spinner, StatusBadge } from '../components/ui';

export function VariantDetail() {
  const id = Number(useParams().id);
  const { model } = useObservatory();
  const detail = useApi((s) => api.cluster(id, s), [id]);
  const cfg = model.data?.decision_config;

  if (!Number.isInteger(id) || id < 1) return <ErrorNotice error={new ApiError(404, 'not_found', 'Unknown cluster', null, null)} />;

  const c = detail.data;
  return (
    <>
      <Link to="/variants" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-accent-700">
        <ArrowLeft className="size-4" aria-hidden /> Variant queue
      </Link>
      <PageHeader
        title={`Cluster #${id}`}
        subtitle={c ? `First seen at report #${c.first_seq}, last at #${c.last_seq} · model ${c.model_version}` : undefined}
        actions={c && (
          <>
            {c.candidate_variant && <CandidateBadge />}
            <StatusBadge status={c.status} />
          </>
        )}
      />
      {detail.error && !c ? (
        <ErrorNotice error={detail.error} onRetry={detail.error.status === 404 ? undefined : detail.reload} />
      ) : !c ? (
        <Spinner label="Loading cluster" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <Criteria c={c} cfg={cfg} />
            <Evidence c={c} />
          </div>
          <div className="space-y-6">
            <ReviewPanel c={c} onReviewed={detail.reload} authenticated={model.data?.mode === 'authenticated'} />
            <AuditTrail key={c.status} id={id} refreshKey={c.status} />
          </div>
        </div>
      )}
    </>
  );
}

function Criteria({ c, cfg }: { c: ClusterDetail; cfg?: DecisionConfig }) {
  const minUnique = cfg?.min_cluster_unique ?? 3;
  const threshold = cfg?.novelty_threshold ?? 0.824;
  const checks = [
    {
      ok: c.unique_text_count >= minUnique,
      title: 'Recurs with distinct wording',
      detail: `${c.unique_text_count} distinct text${c.unique_text_count === 1 ? '' : 's'} (${minUnique} required)`,
      progress: Math.min(1, c.unique_text_count / minUnique),
    },
    {
      ok: c.mean_novelty > threshold,
      title: 'Stays unfamiliar to known families',
      detail: `Mean novelty ${num(c.mean_novelty)} vs threshold ${num(threshold)}`,
      progress: Math.min(1, c.mean_novelty / threshold),
    },
  ];
  return (
    <Card title="Candidate-variant evidence">
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <div className="label">Reports</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-900">{c.report_count}</div>
        </div>
        <div>
          <div className="label">Distinct texts</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-900">{c.unique_text_count}</div>
        </div>
        <div>
          <div className="label">Mean novelty</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-violet-700">{num(c.mean_novelty)}</div>
        </div>
      </div>
      <ul className="mt-5 space-y-3">
        {checks.map((k) => (
          <li key={k.title} className="flex items-start gap-3">
            {k.ok ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-accent-600" aria-label="Met" /> : <Circle className="mt-0.5 size-5 shrink-0 text-slate-300" aria-label="Not met" />}
            <div className="flex-1">
              <div className="text-sm font-medium text-ink-900">{k.title}</div>
              <div className="text-xs text-slate-500">{k.detail}</div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div className={cx('h-full rounded-full', k.ok ? 'bg-accent-600' : 'bg-slate-300')} style={{ width: `${k.progress * 100}%` }} />
              </div>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-xs text-slate-500">
        {c.candidate_variant
          ? 'Both conditions are met. This is a hypothesis for an analyst to judge, not a confirmed new scam.'
          : 'This cluster is being watched. It becomes a candidate variant only when both conditions are met.'}
      </p>
    </Card>
  );
}

function Evidence({ c }: { c: ClusterDetail }) {
  const { items } = useEvidence();
  const byId = new Map(items.map((i) => [i.prediction.event_id, i]));
  const known = c.representative_event_ids.filter((e) => byId.has(e)).length;
  return (
    <Card title="Representative reports" icon={<FileText className="size-4 text-slate-400" aria-hidden />}
      actions={<span className="text-xs text-slate-500">{known} of {c.representative_event_ids.length} readable here</span>}>
      {c.representative_event_ids.length === 0 ? (
        <Empty icon={<FileText className="size-6" />} title="No representatives" />
      ) : (
        <ul className="space-y-3">
          {c.representative_event_ids.map((eid) => {
            const ev = byId.get(eid);
            return (
              <li key={eid} className="rounded-lg border border-slate-200 p-3">
                {ev ? (
                  <>
                    <p className="text-sm whitespace-pre-wrap text-slate-800">{ev.text}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                      <DecisionBadge decision={ev.prediction.decision} />
                      <span>score {num(ev.prediction.scam_score)}</span>
                      <span>novelty {num(ev.prediction.novelty_score)}</span>
                      <Mono>{eid}</Mono>
                    </div>
                  </>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <Mono>{eid}</Mono>
                    <span className="text-xs text-slate-400">Text not held on this device</span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <div className="mt-4">
        <Note>The server stores no message text. Reports are readable only on the device that submitted them, matched by event ID.</Note>
      </div>
    </Card>
  );
}

const actions: { status: ReviewStatus; label: string; icon: typeof Check; className: string }[] = [
  { status: 'confirmed', label: 'Confirm variant', icon: ShieldCheck, className: 'btn-primary' },
  { status: 'rejected', label: 'Reject', icon: ShieldX, className: 'btn-ghost' },
  { status: 'pending', label: 'Return to pending', icon: RotateCcw, className: 'btn-ghost' },
];

function ReviewPanel({ c, onReviewed, authenticated }: { c: ClusterDetail; onReviewed: () => void; authenticated: boolean }) {
  const { monitoring } = useObservatory();
  const conn = useConnection();
  const [choice, setChoice] = useState<ReviewStatus | null>(null);
  // Kept across retries of the same decision so the server records it once.
  const [reviewId, setReviewId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<ReviewResult | null>(null);

  function pick(s: ReviewStatus) {
    setChoice(s);
    setReviewId(null);
    setError(null);
    setResult(null);
  }

  async function submit() {
    if (!choice) return;
    const rid = reviewId ?? newId('review');
    setReviewId(rid);
    setBusy(true);
    setError(null);
    try {
      const actor = !authenticated && conn.analyst ? conn.analyst : undefined;
      setResult(await api.review(c.cluster_id, { review_id: rid, status: choice, ...(actor ? { actor } : {}) }));
      setChoice(null);
      setReviewId(null);
      onReviewed();
      monitoring.reload();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Analyst decision">
      <div className="space-y-2">
        {actions.map(({ status, label, icon: Icon, className }) => (
          <button
            key={status}
            type="button"
            disabled={status === c.status || busy}
            onClick={() => pick(status)}
            aria-pressed={choice === status}
            className={cx('btn w-full justify-start', className, choice === status && 'ring-2 ring-accent-500 ring-offset-1')}
          >
            <Icon className="size-4" aria-hidden /> {label}
            {status === c.status && <span className="ml-auto text-xs opacity-70">current</span>}
          </button>
        ))}
      </div>

      {choice && (
        <div className="mt-4 space-y-3 rounded-lg bg-slate-50 p-3 text-sm">
          <p className="text-slate-700">
            Mark cluster #{c.cluster_id} as <strong>{statusLabel[choice].toLowerCase()}</strong>
            {authenticated ? '' : ` as ${conn.analyst || 'local-demo-analyst'} (unverified)`}.
            {choice === 'confirmed' && ' This records your judgement only. It does not retrain the model or approve training data.'}
          </p>
          <div className="flex gap-2">
            <button type="button" className="btn btn-accent flex-1" onClick={submit} disabled={busy}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Check className="size-4" aria-hidden />} Record decision
            </button>
            <button type="button" className="btn btn-ghost" onClick={() => setChoice(null)} disabled={busy}>Cancel</button>
          </div>
        </div>
      )}

      {error && <div className="mt-4"><ErrorNotice error={error} onRetry={error.retryable ? submit : undefined} /></div>}

      {result && (
        <div role="status" className="mt-4 rounded-lg border border-accent-100 bg-accent-50 p-3 text-sm text-accent-700">
          <p className="font-medium">Recorded: {statusLabel[result.status]} by {result.actor}{result.actor_verified ? '' : ' (unverified)'}</p>
          <p className="mt-0.5 text-xs">Automatic retraining: no. A model update requires a separate, controlled process.</p>
        </div>
      )}
    </Card>
  );
}

function AuditTrail({ id, refreshKey }: { id: number; refreshKey: string }) {
  const [extra, setExtra] = useState<ReviewAudit[]>([]);
  const [cursor, setCursor] = useState<number | null | undefined>(undefined);
  const first = useApi((s) => api.reviews(id, { limit: 20 }, s), [id, refreshKey]);
  const items = [...(first.data?.items ?? []), ...extra];
  const next = cursor === undefined ? first.data?.next_after_id ?? null : cursor;

  async function more() {
    if (next === null) return;
    const page = await api.reviews(id, { limit: 20, after_id: next });
    setExtra((e) => [...e, ...page.items]);
    setCursor(page.next_after_id);
  }

  return (
    <Card title="Audit trail" icon={<History className="size-4 text-slate-400" aria-hidden />}>
      {first.error && !first.data ? (
        <ErrorNotice error={first.error} onRetry={first.reload} />
      ) : !first.data ? (
        <Spinner />
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-500">No decisions recorded yet.</p>
      ) : (
        <ol className="relative space-y-4 border-l border-slate-200 pl-4">
          {items.map((r) => (
            <li key={r.id} className="relative">
              <span className="absolute top-1.5 -left-[21px] size-2.5 rounded-full border-2 border-white bg-accent-600" />
              <div className="flex items-center gap-2">
                <StatusBadge status={r.status} />
                <span className="text-sm font-medium text-ink-900">{r.actor}</span>
                {!r.actor_verified && <span className="text-xs text-slate-400">unverified</span>}
              </div>
              <div className="mt-0.5 text-xs text-slate-500">{dateTime(r.created * 1000)}</div>
            </li>
          ))}
        </ol>
      )}
      {next !== null && items.length > 0 && (
        <button type="button" className="btn btn-ghost mt-4 w-full py-1.5 text-xs" onClick={more}>Load more</button>
      )}
    </Card>
  );
}
