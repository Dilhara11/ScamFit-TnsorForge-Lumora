import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ChevronRight, Layers, Loader2, RefreshCw } from 'lucide-react';
import { api, ApiError } from '../api/client';
import type { Cluster, ReviewStatus } from '../api/types';
import { useConnection } from '../lib/connection';
import { useObservatory } from '../lib/observatory';
import { num } from '../lib/format';
import { MiniBar } from '../components/charts';
import { CandidateBadge, Card, cx, Empty, ErrorNotice, Note, PageHeader, Spinner, StatusBadge } from '../components/ui';

const filters: { value: ReviewStatus | ''; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
  { value: '', label: 'All' },
];

type Sort = 'id' | 'novelty' | 'reports' | 'recent';
const sorters: Record<Sort, (a: Cluster, b: Cluster) => number> = {
  id: (a, b) => a.cluster_id - b.cluster_id,
  novelty: (a, b) => b.mean_novelty - a.mean_novelty,
  reports: (a, b) => b.report_count - a.report_count,
  recent: (a, b) => b.last_seq - a.last_seq,
};

export function Variants() {
  const [params, setParams] = useSearchParams();
  const status = (params.get('status') ?? 'pending') as ReviewStatus | '';
  const candidatesOnly = params.get('candidates') === '1';
  const sort = (params.get('sort') ?? 'recent') as Sort;
  const { model, monitoring } = useObservatory();
  const conn = useConnection();
  const cfg = model.data?.decision_config;

  const [items, setItems] = useState<Cluster[]>([]);
  const [cursor, setCursor] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);

  const load = useCallback(
    async (after: number, append: boolean) => {
      setLoading(true);
      try {
        const page = await api.clusters({ status: status || null, limit: 100, after_id: after });
        setItems((prev) => (append ? [...prev, ...page.items] : page.items));
        setCursor(page.next_after_id);
        setError(null);
      } catch (e) {
        setError(e as ApiError);
      } finally {
        setLoading(false);
      }
    },
    [status],
  );

  useEffect(() => {
    load(0, false);
  }, [load, conn.baseUrl, conn.apiKey]);

  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v === null) next.delete(k);
    else next.set(k, v);
    setParams(next, { replace: true });
  };

  const shown = useMemo(
    () => items.filter((c) => !candidatesOnly || c.candidate_variant).sort(sorters[sort]),
    [items, candidatesOnly, sort],
  );

  return (
    <>
      <PageHeader
        title="Variant queue"
        subtitle="Messages that need review are grouped by similarity. A cluster becomes a candidate variant once it recurs with enough distinct texts and stays unfamiliar."
        actions={
          <button type="button" className="btn btn-ghost" onClick={() => load(0, false)} disabled={loading}>
            <RefreshCw className={cx('size-4', loading && 'animate-spin')} aria-hidden /> Refresh
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1" role="tablist" aria-label="Review status">
          {filters.map((f) => (
            <button
              key={f.label}
              type="button"
              role="tab"
              aria-selected={status === f.value}
              onClick={() => set('status', f.value)}
              className={cx('rounded-md px-3 py-1 text-sm font-medium', status === f.value ? 'bg-ink-900 text-white' : 'text-slate-600 hover:bg-slate-50')}
            >
              {f.label}
              {f.value === 'pending' && monitoring.data ? ` (${monitoring.data.pending_count})` : ''}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" className="accent-accent-600" checked={candidatesOnly} onChange={(e) => set('candidates', e.target.checked ? '1' : null)} />
          Candidate variants only
        </label>
        <label className="ml-auto flex items-center gap-2 text-sm text-slate-600">
          Sort
          <select className="input w-auto py-1" value={sort} onChange={(e) => set('sort', e.target.value)}>
            <option value="recent">Most recent activity</option>
            <option value="novelty">Highest novelty</option>
            <option value="reports">Most reports</option>
            <option value="id">Cluster ID</option>
          </select>
        </label>
      </div>

      {error && <div className="mb-4"><ErrorNotice error={error} onRetry={() => load(0, false)} /></div>}

      <Card>
        {loading && !items.length ? (
          <Spinner label="Loading clusters" />
        ) : shown.length === 0 ? (
          <Empty icon={<Layers className="size-6" />} title={candidatesOnly ? 'No candidate variants here' : 'No clusters'}>
            Clusters form when scanned messages need review. Use Scan messages, or replay a batch, to populate the queue.
          </Empty>
        ) : (
          <div className="-m-5 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left">
                <tr className="label">
                  <th className="px-5 py-2.5 font-semibold">Cluster</th>
                  <th className="px-3 py-2.5 font-semibold">Signal</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Distinct texts</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Reports</th>
                  <th className="px-3 py-2.5 font-semibold">Mean novelty</th>
                  <th className="px-3 py-2.5 font-semibold">Seen</th>
                  <th className="px-5 py-2.5"><span className="sr-only">Open</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {shown.map((c) => (
                  <tr key={c.cluster_id} className="group relative hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link to={`/variants/${c.cluster_id}`} className="font-semibold text-ink-900 after:absolute after:inset-0">
                        #{c.cluster_id}
                      </Link>
                      <div className="mt-1"><StatusBadge status={c.status} /></div>
                    </td>
                    <td className="px-3 py-3">
                      {c.candidate_variant ? <CandidateBadge /> : <span className="text-xs text-slate-500">Watching</span>}
                    </td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums">
                      {c.unique_text_count}
                      {cfg && c.unique_text_count < cfg.min_cluster_unique && <span className="text-slate-400"> / {cfg.min_cluster_unique}</span>}
                    </td>
                    <td className="px-3 py-3 text-right font-mono tabular-nums">{c.report_count}</td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2">
                        <MiniBar value={c.mean_novelty} className={cfg && c.mean_novelty > cfg.novelty_threshold ? 'bg-violet-600' : 'bg-violet-300'} />
                        <span className="font-mono text-xs tabular-nums">{num(c.mean_novelty)}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-500">
                      #{c.first_seq}–#{c.last_seq}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <ChevronRight className="inline size-4 text-slate-300 group-hover:text-accent-600" aria-hidden />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {cursor !== null && (
          <div className="mt-5 flex justify-center border-t border-slate-100 pt-4">
            <button type="button" className="btn btn-ghost" disabled={loading} onClick={() => load(cursor, true)}>
              {loading && <Loader2 className="size-4 animate-spin" aria-hidden />} Load more
            </button>
          </div>
        )}
      </Card>

      {cfg && (
        <div className="mt-4">
          <Note>
            Candidate rule: at least {cfg.min_cluster_unique} distinct texts and mean novelty above {num(cfg.novelty_threshold)}. Distinct texts are not proof of independent reporters. Up to {cfg.max_clusters} clusters are tracked per model version.
          </Note>
        </div>
      )}
    </>
  );
}
