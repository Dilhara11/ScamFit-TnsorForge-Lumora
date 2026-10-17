import { AlertTriangle, Gauge, Radar, Settings2 } from 'lucide-react';
import { useObservatory } from '../lib/observatory';
import { humanise, num, pct, representationLabel } from '../lib/format';
import { Card, ErrorNotice, Mono, PageHeader, Spinner } from '../components/ui';

export function Model() {
  const { model } = useObservatory();
  const m = model.data;
  if (model.error && !m) return <ErrorNotice error={model.error} onRetry={model.reload} />;
  if (!m) return <Spinner label="Loading model" />;
  const c = m.decision_config;

  const decision: [string, string, string][] = [
    ['Low-risk below', num(c.low_risk_threshold), 'Scores below this are low risk — not verified safe.'],
    ['High-risk at or above', num(c.high_risk_threshold), 'Scores between the two thresholds need review.'],
    ['Novelty threshold', num(c.novelty_threshold), 'Above this, a message is unfamiliar to all known families.'],
    ['Cluster similarity', num(c.cluster_similarity, 2), 'Minimum similarity to join an existing cluster.'],
  ];
  const monitoring: [string, string, string][] = [
    ['Window size', `${c.window_size} reports`, 'Each window summarises the most recent reports.'],
    ['Window stride', `every ${c.window_stride} reports`, 'How often a new window is computed.'],
    ['Drift threshold', pct(c.drift_unknown_threshold, 0), 'Unfamiliar fraction that marks a window as elevated.'],
    ['Sustained alert', `${c.consecutive_windows} windows`, 'Consecutive elevated windows that raise an alert.'],
    ['Candidate recurrence', `${c.min_cluster_unique} distinct texts`, 'Minimum distinct texts for a candidate variant.'],
    ['Cluster capacity', `${c.max_clusters}`, 'Maximum clusters per model version.'],
  ];

  return (
    <>
      <PageHeader
        title="Model & limits"
        subtitle="The frozen configuration behind every score on this console, and what it can and cannot tell you. Thresholds are part of the model artifact and cannot be changed from here."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          ['Model version', <Mono key="v">{m.model_version}</Mono>],
          ['Representation', representationLabel(m.representation)],
          ['Scope', humanise(m.scope)],
          ['Scores calibrated', m.scores_calibrated ? 'Yes' : 'No'],
        ].map(([k, v]) => (
          <div key={String(k)} className="card p-4">
            <div className="label">{k}</div>
            <div className="mt-1.5 text-sm font-medium text-ink-900">{v}</div>
          </div>
        ))}
      </div>

      <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="flex items-center gap-2 font-semibold text-amber-900">
          <AlertTriangle className="size-4" aria-hidden /> Known limitations
        </h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-amber-900">
          {m.limitations.map((l) => <li key={l}>{l}</li>)}        </ul>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Decision thresholds" icon={<Gauge className="size-4 text-accent-600" aria-hidden />}>
          <ConfigList rows={decision} />
        </Card>
        <Card title="Drift monitoring" icon={<Radar className="size-4 text-violet-600" aria-hidden />}>
          <ConfigList rows={monitoring} />
        </Card>
      </div>

      <div className="mt-6">
        <Card title="Deployment" icon={<Settings2 className="size-4 text-slate-400" aria-hidden />}>
          <p className="text-sm text-slate-600">
            {m.mode === 'local_demo'
              ? 'Local demonstration mode: no credentials, loopback only. Analyst names on reviews are unverified. Do not expose this mode through a tunnel, proxy or LAN.'
              : 'Authenticated mode: analyst identity on reviews is derived from the API key.'}
          </p>
        </Card>
      </div>
    </>
  );
}

function ConfigList({ rows }: { rows: [string, string, string][] }) {
  return (
    <dl className="-my-3 divide-y divide-slate-100">
      {rows.map(([k, v, hint]) => (
        <div key={k} className="flex items-start justify-between gap-4 py-3">
          <div>
            <dt className="text-sm font-medium text-ink-900">{k}</dt>
            <dd className="text-xs text-slate-500">{hint}</dd>
          </div>
          <dd className="shrink-0 font-mono text-sm tabular-nums text-ink-900">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
