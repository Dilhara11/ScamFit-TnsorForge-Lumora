import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { History, ListChecks, Loader2, RotateCcw, ScanText, Send, Square } from 'lucide-react';
import { ApiError } from '../api/client';
import type { Prediction } from '../api/types';
import { useEvidence } from '../lib/evidence';
import { newId } from '../lib/ids';
import { useObservatory } from '../lib/observatory';
import { scoreMessage } from '../lib/submit';
import { num, relative } from '../lib/format';
import { PredictionResult } from '../components/PredictionResult';
import { Card, cx, DecisionBadge, Empty, ErrorNotice, Mono, NovelBadge, PageHeader } from '../components/ui';

const MAX = 10000;

// Fictional illustrations only; not real messages or identifiers.
const samples = [
  { label: 'English', text: 'URGENT: Your bank account will be suspended today. Verify your details now at http://example.invalid/verify' },
  { label: 'Singlish', text: 'Machan oyage parcel eka customs eke hira wela. Rs. 2500 gewala release karanna me link eka click karanna' },
  { label: 'Sinhala', text: 'ඔබගේ ගිණුම අත්හිටුවා ඇත. තහවුරු කිරීමට මෙම සබැඳිය ක්ලික් කරන්න.' },
  { label: 'Tamil', text: 'உங்கள் கணக்கு முடக்கப்பட்டுள்ளது. உறுதிப்படுத்த இந்த இணைப்பைக் கிளிக் செய்யவும்.' },
  { label: 'Ordinary', text: 'The office opens tomorrow at 9. Please bring the signed forms.' },
];

type Mode = 'single' | 'batch';

export function Scan() {
  const [mode, setMode] = useState<Mode>('single');
  return (
    <>
      <PageHeader
        title="Scan messages"
        subtitle="Score suspicious SMS, WhatsApp or email text. Each scan is logged for drift monitoring; the server keeps the scores, never the text."
      />
      <div className="mb-5 inline-flex rounded-lg border border-slate-200 bg-white p-1" role="tablist">
        {(
          [
            ['single', 'Single message', ScanText],
            ['batch', 'Batch replay', ListChecks],
          ] as const
        ).map(([m, label, Icon]) => (
          <button
            key={m}
            type="button"
            role="tab"
            aria-selected={mode === m}
            onClick={() => setMode(m)}
            className={cx('btn py-1.5', mode === m ? 'bg-ink-900 text-white' : 'text-slate-600 hover:bg-slate-50')}
          >
            <Icon className="size-4" aria-hidden /> {label}
          </button>
        ))}
      </div>
      {mode === 'single' ? <Single /> : <Batch />}
    </>
  );
}

function Single() {
  const { model, monitoring } = useObservatory();
  const evidence = useEvidence();
  const [text, setText] = useState('');
  const [eventId, setEventId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<Prediction | null>(null);
  const valid = text.trim().length > 0 && text.length <= MAX;

  function edit(next: string) {
    setText(next);
    // New text is a new report; only an unchanged retry may reuse the ID.
    setEventId(null);
    setError(null);
  }

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!valid || busy) return;
    const id = eventId ?? newId('web');
    setEventId(id);
    setBusy(true);
    setError(null);
    try {
      setResult(await scoreMessage(text, id));
      setText('');
      setEventId(null);
      monitoring.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(0, 'client_error', String(err), null, null));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="space-y-6 lg:col-span-3">
        <Card>
          <form onSubmit={submit} className="space-y-3">
            <label htmlFor="msg" className="text-sm font-medium text-ink-900">
              Message text
            </label>
            <textarea
              id="msg"
              className="input min-h-40 resize-y text-base"
              placeholder="Paste a message in Sinhala, Tamil, English, Singlish or Tanglish…"
              value={text}
              maxLength={MAX}
              onChange={(e) => edit(e.target.value)}
              onKeyDown={(e) => (e.ctrlKey || e.metaKey) && e.key === 'Enter' && submit()}
            />
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-500">Try:</span>
              {samples.map((s) => (
                <button key={s.label} type="button" onClick={() => edit(s.text)} className="rounded-full border border-slate-200 px-2.5 py-0.5 text-xs text-slate-600 hover:border-accent-500 hover:text-accent-700">
                  {s.label}
                </button>
              ))}
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-slate-100 pt-3">
              <span className={cx('text-xs tabular-nums', text.length > MAX * 0.9 ? 'text-amber-700' : 'text-slate-400')}>
                {text.length.toLocaleString()} / {MAX.toLocaleString()}
              </span>
              <button type="submit" className="btn btn-accent" disabled={!valid || busy}>
                {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
                {busy ? 'Scoring…' : 'Score message'}
                <kbd className="hidden rounded bg-white/20 px-1 text-[10px] sm:inline">Ctrl ↵</kbd>
              </button>
            </div>
          </form>
          {error && (
            <div className="mt-4 space-y-2">
              <ErrorNotice error={error} onRetry={error.retryable ? submit : undefined} />
              {error.retryable && eventId && (
                <p className="text-xs text-slate-500">
                  Retry reuses event <Mono>{eventId}</Mono>, so the report is never counted twice.
                </p>
              )}
            </div>
          )}
        </Card>

        <div aria-live="polite">
          {result && (
            <Card title="Result">
              <PredictionResult p={result} model={model.data} />
            </Card>
          )}
        </div>
      </div>

      <Card className="lg:col-span-2" title="Recent scans on this device" icon={<History className="size-4 text-slate-400" aria-hidden />}>
        {evidence.items.length === 0 ? (
          <Empty icon={<ScanText className="size-6" />} title="Nothing scanned yet">
            {evidence.retain ? 'Scans you submit appear here.' : 'Local evidence is turned off under Connection.'}
          </Empty>
        ) : (
          <ul className="-my-2 divide-y divide-slate-100">
            {evidence.items.slice(0, 12).map((it) => (
              <li key={it.prediction.event_id}>
                <button type="button" onClick={() => setResult(it.prediction)} className="w-full py-3 text-left hover:bg-slate-50">
                  <p className="line-clamp-2 text-sm text-slate-700">{it.text}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                    <DecisionBadge decision={it.prediction.decision} />
                    {it.prediction.is_unknown && <NovelBadge />}
                    <span>{relative(it.submittedAt)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

interface Row {
  text: string;
  eventId: string;
  state: 'queued' | 'running' | 'done' | 'error';
  result?: Prediction;
  error?: ApiError;
}

function Batch() {
  const { monitoring } = useObservatory();
  const [input, setInput] = useState('');
  const [rows, setRows] = useState<Row[]>([]);
  const [running, setRunning] = useState(false);
  const stop = useRef(false);
  const lines = input.split('\n').map((l) => l.trim()).filter(Boolean);
  const tooLong = lines.filter((l) => l.length > MAX).length;

  async function run(initial: Row[]) {
    setRows(initial);
    setRunning(true);
    stop.current = false;
    const update = (i: number, patch: Partial<Row>) => setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)));
    // Sequential, in order: monitoring windows depend on report order.
    for (let i = 0; i < initial.length && !stop.current; i++) {
      if (initial[i].state === 'done') continue;
      update(i, { state: 'running', error: undefined });
      try {
        update(i, { state: 'done', result: await scoreMessage(initial[i].text, initial[i].eventId) });
      } catch (e) {
        update(i, { state: 'error', error: e instanceof ApiError ? e : new ApiError(0, 'client_error', String(e), null, null) });
      }
    }
    setRunning(false);
    monitoring.reload();
  }

  const start = () => run(lines.map((text) => ({ text, eventId: newId('batch'), state: 'queued' })));
  // Failed rows keep their event IDs, so resuming cannot double-count a report.
  const resume = () => run(rows.map((r) => (r.state === 'done' ? r : { ...r, state: 'queued' })));
  const done = rows.filter((r) => r.state === 'done');
  const failed = rows.filter((r) => r.state === 'error').length;

  return (
    <div className="space-y-6">
      <Card>
        <div className="space-y-3">
          <label htmlFor="batch" className="text-sm font-medium text-ink-900">
            One message per line
          </label>
          <textarea
            id="batch"
            className="input min-h-48 resize-y font-mono text-xs"
            placeholder={'Replay a sequence of reports to exercise drift monitoring.\nEach line is submitted in order as a separate report.'}
            value={input}
            disabled={running}
            onChange={(e) => setInput(e.target.value)}
          />
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3">
            <span className="text-xs text-slate-500">
              {lines.length} message{lines.length === 1 ? '' : 's'}
              {tooLong > 0 && <span className="text-rose-600"> · {tooLong} over {MAX.toLocaleString()} characters</span>}
            </span>
            <div className="flex gap-2">
              {running ? (
                <button type="button" className="btn btn-ghost" onClick={() => (stop.current = true)}>
                  <Square className="size-4" aria-hidden /> Stop
                </button>
              ) : (
                failed > 0 && (
                  <button type="button" className="btn btn-ghost" onClick={resume}>
                    <RotateCcw className="size-4" aria-hidden /> Retry {failed} failed
                  </button>
                )
              )}
              <button type="button" className="btn btn-accent" disabled={running || !lines.length || tooLong > 0} onClick={start}>
                {running ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Send className="size-4" aria-hidden />}
                {running ? `Scoring ${done.length + 1} of ${rows.length}…` : 'Run batch'}
              </button>
            </div>
          </div>
        </div>
      </Card>

      {rows.length > 0 && (
        <Card
          title={`Results · ${done.length}/${rows.length}`}
          actions={
            done.length > 0 && (
              <span className="text-xs text-slate-500">
                {done.filter((r) => r.result!.decision === 'high_risk').length} high risk · {done.filter((r) => r.result!.is_unknown).length} unfamiliar
              </span>
            )
          }
        >
          <div className="-mx-5 -my-5 overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left">
                <tr className="label">
                  <th className="px-5 py-2.5 font-semibold">#</th>
                  <th className="px-3 py-2.5 font-semibold">Message</th>
                  <th className="px-3 py-2.5 font-semibold">Decision</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Score</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Novelty</th>
                  <th className="px-5 py-2.5 font-semibold">Cluster</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((r, i) => (
                  <tr key={r.eventId} className={r.state === 'running' ? 'bg-accent-50/50' : undefined}>
                    <td className="px-5 py-2.5 font-mono text-xs text-slate-400">{i + 1}</td>
                    <td className="max-w-xs truncate px-3 py-2.5 text-slate-700" title={r.text}>
                      {r.text}
                    </td>
                    {r.result ? (
                      <>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center gap-1.5">
                            <DecisionBadge decision={r.result.decision} />
                            {r.result.is_unknown && <NovelBadge />}
                          </div>
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono tabular-nums">{num(r.result.scam_score)}</td>
                        <td className="px-3 py-2.5 text-right font-mono tabular-nums">{num(r.result.novelty_score)}</td>
                        <td className="px-5 py-2.5">
                          {r.result.cluster_id_or_null != null ? (
                            <Link to={`/variants/${r.result.cluster_id_or_null}`} className="font-medium text-accent-700 hover:underline">
                              #{r.result.cluster_id_or_null}
                            </Link>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                      </>
                    ) : (
                      <td colSpan={4} className="px-3 py-2.5 text-xs text-slate-500">
                        {r.state === 'running' ? 'Scoring…' : r.state === 'error' ? <span className="text-rose-700">{r.error?.message}</span> : 'Queued'}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
