import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Fingerprint, Layers } from 'lucide-react';
import type { ModelInfo, Prediction } from '../api/types';
import { humanise, modelWording } from '../lib/format';
import { ScoreScale } from './charts';
import { DecisionBadge, Mono, NovelBadge } from './ui';

const explain: Record<Prediction['decision'], string> = {
  high_risk: 'Strongly resembles known scam messages. Treat as a likely scam.',
  review: 'Falls between the decision thresholds. An analyst should look at it.',
  low_risk: 'Did not score as a scam. This is not proof that the message is safe.',
};

export function PredictionResult({ p, model }: { p: Prediction; model?: ModelInfo | null }) {
  const cfg = model?.decision_config;
  const wording = modelWording(model);
  const low = cfg?.low_risk_threshold ?? 0.2;
  const high = cfg?.high_risk_threshold ?? 0.592;
  const novel = cfg?.novelty_threshold ?? 0.824;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <DecisionBadge decision={p.decision} size="lg" />
        {p.is_unknown && <NovelBadge />}
        {p.needs_review && p.decision !== 'review' && (
          <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 ring-1 ring-amber-200 ring-inset">Queued for review</span>
        )}
      </div>
      <p className="text-sm text-slate-600">
        {explain[p.decision]}
        {p.is_unknown && ' It is also unlike every known family, so it was grouped with similar unfamiliar reports.'}
      </p>

      <div className="grid gap-6 sm:grid-cols-2">
        <ScoreScale
          label="Scam score"
          value={p.scam_score}
          zones={[
            { to: low, className: 'bg-slate-200', label: 'Low risk' },
            { to: high, className: 'bg-amber-200', label: 'Review' },
            { to: 1, className: 'bg-rose-300', label: 'High risk' },
          ]}
          caption={wording.score}
        />
        <ScoreScale
          label="Novelty"
          value={p.novelty_score}
          markerClass="bg-violet-600"
          zones={[
            { to: novel, className: 'bg-violet-100', label: 'Familiar' },
            { to: 1, className: 'bg-violet-300', label: 'Unfamiliar' },
          ]}
          caption={`${humanise(wording.novelty)} distance from known scams. Independent of the scam score.`}
        />
      </div>

      <dl className="grid gap-4 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-2">
        <div>
          <dt className="label flex items-center gap-1.5">
            <Fingerprint className="size-3.5" aria-hidden /> Nearest known family
          </dt>
          <dd className="mt-1 font-medium text-ink-900">
            {p.nearest_known_family_or_null ? humanise(p.nearest_known_family_or_null) : <span className="text-slate-500">None — unfamiliar pattern</span>}
          </dd>
        </div>
        <div>
          <dt className="label flex items-center gap-1.5">
            <Layers className="size-3.5" aria-hidden /> Cluster
          </dt>
          <dd className="mt-1">
            {p.cluster_id_or_null != null ? (
              <Link to={`/variants/${p.cluster_id_or_null}`} className="inline-flex items-center gap-1 font-medium text-accent-700 hover:underline">
                Cluster #{p.cluster_id_or_null} <ArrowRight className="size-3.5" aria-hidden />
              </Link>
            ) : p.cluster_capacity_reached ? (
              <span className="inline-flex items-center gap-1 text-amber-800">
                <AlertTriangle className="size-3.5" aria-hidden /> Cluster capacity reached
              </span>
            ) : (
              <span className="text-slate-500">{p.needs_review ? 'Not clustered' : 'Not needed'}</span>
            )}
          </dd>
        </div>
      </dl>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>
          Event <Mono>{p.event_id}</Mono>
        </span>
        <span>
          Model <Mono>{p.model_version}</Mono>
        </span>
      </div>
    </div>
  );
}
