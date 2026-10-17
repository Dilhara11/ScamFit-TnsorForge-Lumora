import { Link } from 'react-router-dom';
import { ArrowRight, BellRing, Layers, LineChart, Radar, ScanText, ShieldCheck } from 'lucide-react';
import { api } from '../api/client';
import { useApi } from '../lib/hooks';
import { useObservatory } from '../lib/observatory';
import { bytes, int, modelWording, num, pct } from '../lib/format';
import { WindowChart } from '../components/charts';
import { CandidateBadge, Card, Empty, ErrorNotice, Note, PageHeader, Spinner, Stat, StatusBadge } from '../components/ui';

const steps = [
  { to: '/scan', icon: ScanText, title: 'Detect', text: 'Score suspicious messages against known scam families.' },
  { to: '/', icon: Radar, title: 'Monitor', text: 'Watch the unfamiliar-message rate across rolling windows.' },
  { to: '/variants', icon: ShieldCheck, title: 'Respond', text: 'Review recurring unfamiliar clusters as candidate variants.' },
];

export function Overview() {
  const { monitoring, model, windows } = useObservatory();
  const candidates = useApi((s) => api.clusters({ status: 'pending', limit: 100 }, s), [monitoring.data?.cluster_count], 30000);
  const m = monitoring.data;
  const cfg = model.data?.decision_config;
  const w = m?.latest_window;
  const elevated = !!(w && cfg && w.unknown_fraction > cfg.drift_unknown_threshold);
  const pendingCandidates = (candidates.data?.items ?? []).filter((c) => c.candidate_variant);

  return (
    <>
      <PageHeader
        title="Observatory overview"
        subtitle="Surveillance of scam message patterns across Sinhala, Tamil, English, Singlish and Tanglish reports. Families are known scam mechanisms; variants are recurring unfamiliar presentations."
        actions={
          <Link to="/scan" className="btn btn-accent">
            <ScanText className="size-4" aria-hidden /> Scan a message
          </Link>
        }
      />

      {monitoring.error && !m && <ErrorNotice error={monitoring.error} onRetry={monitoring.reload} />}

      {w?.alert && (
        <div role="alert" className="mb-6 flex flex-wrap items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 sm:flex-nowrap">
          <BellRing className="mt-0.5 size-5 shrink-0 text-rose-600" aria-hidden />
          <div className="min-w-0 flex-1 basis-60 text-sm">
            <p className="font-semibold text-rose-900">Drift alert: unfamiliar messages are elevated</p>
            <p className="mt-0.5 text-rose-800">
              {pct(w.unknown_fraction)} of the last {cfg?.window_size ?? 20} reports were unfamiliar, above the {pct(cfg?.drift_unknown_threshold ?? 0.15, 0)} threshold for {cfg?.consecutive_windows ?? 2} consecutive windows. Established detection may be less dependable — review emerging clusters.
            </p>
          </div>
          <Link to="/variants" className="btn btn-primary shrink-0">Open queue</Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Reports scored" value={m ? int(m.event_count) : '—'} hint={m ? `Model ${m.model_version}` : undefined} />
        <Stat
          label="Unfamiliar rate"
          value={w ? pct(w.unknown_fraction) : '—'}
          tone={elevated ? 'alert' : undefined}
          hint={cfg ? `Threshold ${pct(cfg.drift_unknown_threshold, 0)} · latest window` : undefined}
        />
        <Stat label="Pending review" value={m ? int(m.pending_count) : '—'} hint={m ? `${int(m.cluster_count)} clusters tracked${cfg ? ` of ${cfg.max_clusters}` : ''}` : undefined} />
        <Stat label="Candidate variants" value={m ? int(m.candidate_count) : '—'} tone={m?.candidate_count ? 'accent' : undefined} hint="Recurring and unfamiliar" />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title="Unfamiliar-message rate"
          icon={<LineChart className="size-4 text-violet-600" aria-hidden />}
          actions={w && <span className="font-mono text-xs text-slate-400">to report #{w.end_seq}</span>}
        >
          {!m ? (
            <Spinner />
          ) : windows.length === 0 ? (
            <Empty icon={<Radar className="size-6" />} title={m.monitoring === 'ready' ? 'Waiting for the next window' : 'Not enough reports yet'}>
              Monitoring starts after {cfg?.window_size ?? 20} reports, then updates every {cfg?.window_stride ?? 5}. {int(m.event_count)} scored so far.
            </Empty>
          ) : (
            <>
              <WindowChart windows={windows} threshold={cfg?.drift_unknown_threshold ?? 0.15} />
              {w && (
                <dl className="mt-4 grid grid-cols-3 gap-4 border-t border-slate-100 pt-4 text-sm">
                  <div>
                    <dt className="label">Needing review</dt>
                    <dd className="mt-1 font-mono tabular-nums">{pct(w.review_fraction)}</dd>
                  </div>
                  <div>
                    <dt className="label">Mean scam score</dt>
                    <dd className="mt-1 font-mono tabular-nums">{num(w.score_mean)}</dd>
                  </div>
                  <div>
                    <dt className="label">Window alert</dt>
                    <dd className={w.alert ? 'mt-1 font-semibold text-rose-600' : 'mt-1 text-slate-600'}>{w.alert ? 'Raised' : elevated ? 'Elevated, not yet sustained' : 'None'}</dd>
                  </div>
                </dl>
              )}
              <p className="mt-4 text-xs text-slate-500">
                Windows observed by this browser during the session. Each covers the last {cfg?.window_size ?? 20} reports; an alert needs {cfg?.consecutive_windows ?? 2} consecutive windows above threshold. Novelty is {modelWording(model.data).novelty} distance, not fraud probability.
              </p>
            </>
          )}
        </Card>

        <Card
          title="Awaiting analyst"
          icon={<Layers className="size-4 text-amber-600" aria-hidden />}
          actions={
            <Link to="/variants" className="inline-flex items-center gap-1 text-xs font-medium text-accent-700 hover:underline">
              Queue <ArrowRight className="size-3" aria-hidden />
            </Link>
          }
        >
          {candidates.error && !candidates.data ? (
            <ErrorNotice error={candidates.error} onRetry={candidates.reload} />
          ) : !candidates.data ? (
            <Spinner />
          ) : pendingCandidates.length === 0 ? (
            <Empty icon={<ShieldCheck className="size-6" />} title="No candidate variants">
              {candidates.data.items.length
                ? `${candidates.data.items.length} pending cluster${candidates.data.items.length === 1 ? '' : 's'} have not met the recurrence and novelty rule.`
                : 'Clusters appear when messages need review.'}
            </Empty>
          ) : (
            <ul className="-my-2 divide-y divide-slate-100">
              {pendingCandidates.slice(0, 6).map((c) => (
                <li key={c.cluster_id}>
                  <Link to={`/variants/${c.cluster_id}`} className="flex items-center justify-between gap-3 py-3 hover:text-accent-700">
                    <div>
                      <div className="font-medium">Cluster #{c.cluster_id}</div>
                      <div className="text-xs text-slate-500">
                        {c.unique_text_count} distinct · {c.report_count} reports · novelty {num(c.mean_novelty, 2)}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <CandidateBadge />
                      <StatusBadge status={c.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        {steps.map(({ to, icon: Icon, title, text }, i) => (
          <Link key={title} to={to} className="card group flex gap-3 p-4 transition hover:border-accent-500">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-50 text-accent-700">
              <Icon className="size-5" aria-hidden />
            </div>
            <div>
              <div className="text-sm font-semibold text-ink-900">
                {i + 1}. {title}
              </div>
              <p className="text-xs text-slate-500">{text}</p>
            </div>
          </Link>
        ))}
      </div>

      {m && (
        <div className="mt-6">
          <Note>
            Storage: {bytes(m.disk_free_bytes)} free · schema v{m.schema_version} · monitoring {m.monitoring}. The service stores predictions and windows without raw message text.
          </Note>
        </div>
      )}
    </>
  );
}
