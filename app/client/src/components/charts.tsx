import type { Window } from '../api/types';
import { cx } from './ui';
import { num, pct } from '../lib/format';

interface Zone {
  to: number;
  className: string;
  label: string;
}

/**
 * A 0–1 scale with the frozen model thresholds drawn on it, so a score is
 * always read against the boundaries that produced the decision.
 */
export function ScoreScale({ label, value, zones, caption, markerClass = 'bg-ink-900' }: {
  label: string;
  value: number;
  zones: Zone[];
  caption?: string;
  markerClass?: string;
}) {
  const clamped = Math.min(1, Math.max(0, value));
  let from = 0;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="label">{label}</span>
        <span className="font-mono text-lg font-semibold text-ink-900 tabular-nums">{num(value)}</span>
      </div>
      <div
        className="relative mt-2 h-3"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={Number(value.toFixed(3))}
      >
        <div className="flex h-full overflow-hidden rounded-full">
          {zones.map((z) => {
            const w = (z.to - from) * 100;
            from = z.to;
            return <div key={z.label} className={z.className} style={{ width: `${w}%` }} title={z.label} />;
          })}
        </div>
        <div
          className={cx('absolute top-1/2 size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow', markerClass)}
          style={{ left: `${clamped * 100}%` }}
        />
      </div>
      <div className="relative mt-1.5 h-4 text-[10px] text-slate-400">
        {zones.slice(0, -1).map((z) => (
          <span key={z.label} className="absolute -translate-x-1/2 font-mono" style={{ left: `${z.to * 100}%` }}>
            {num(z.to, 2)}
          </span>
        ))}
      </div>
      {caption && <p className="mt-1 text-xs text-slate-500">{caption}</p>}
    </div>
  );
}

/**
 * Unfamiliar-message rate per rolling window, against the drift threshold.
 * Alerted windows are marked; the series is only what this browser observed.
 */
export function WindowChart({ windows, threshold }: { windows: Window[]; threshold: number }) {
  const W = 640;
  const H = 180;
  const pad = { l: 36, r: 12, t: 12, b: 24 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const maxY = Math.max(threshold * 2, ...windows.map((w) => w.unknown_fraction), 0.1);
  const x = (i: number) => pad.l + (windows.length <= 1 ? iw / 2 : (i / (windows.length - 1)) * iw);
  const y = (v: number) => pad.t + ih - (v / maxY) * ih;
  const path = windows.map((w, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(w.unknown_fraction).toFixed(1)}`).join(' ');
  const area = windows.length > 1 ? `${path} L${x(windows.length - 1)},${y(0)} L${x(0)},${y(0)} Z` : '';
  const ticks = [0, maxY / 2, maxY];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Unfamiliar-message rate per monitoring window">
      {ticks.map((t) => (
        <g key={t}>
          <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} className="stroke-slate-100" />
          <text x={pad.l - 6} y={y(t) + 3} textAnchor="end" className="fill-slate-400 font-mono text-[10px]">
            {pct(t, 0)}
          </text>
        </g>
      ))}
      <line x1={pad.l} x2={W - pad.r} y1={y(threshold)} y2={y(threshold)} className="stroke-rose-400" strokeDasharray="4 4" />
      <text x={W - pad.r} y={y(threshold) - 5} textAnchor="end" className="fill-rose-500 text-[10px] font-medium">
        drift threshold {pct(threshold, 0)}
      </text>
      {area && <path d={area} className="fill-violet-500/10" />}
      <path d={path} fill="none" className="stroke-violet-600" strokeWidth={2} strokeLinejoin="round" />
      {windows.map((w, i) => (
        <circle
          key={w.end_seq}
          cx={x(i)}
          cy={y(w.unknown_fraction)}
          r={w.alert ? 5 : 3}
          className={w.alert ? 'fill-rose-500 stroke-white' : 'fill-violet-600 stroke-white'}
          strokeWidth={1.5}
        >
          <title>
            {`Window ending at report #${w.end_seq}: ${pct(w.unknown_fraction)} unfamiliar, ${pct(w.review_fraction)} needing review${w.alert ? ' — ALERT' : ''}`}
          </title>
        </circle>
      ))}
      {windows.length > 0 && (
        <>
          <text x={x(0)} y={H - 6} textAnchor="start" className="fill-slate-400 font-mono text-[10px]">
            #{windows[0].end_seq}
          </text>
          {windows.length > 1 && (
            <text x={x(windows.length - 1)} y={H - 6} textAnchor="end" className="fill-slate-400 font-mono text-[10px]">
              #{windows[windows.length - 1].end_seq}
            </text>
          )}
        </>
      )}
    </svg>
  );
}

/** Small proportional bar for table cells. */
export function MiniBar({ value, max = 1, className = 'bg-violet-500' }: { value: number; max?: number; className?: string }) {
  return (
    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100" aria-hidden>
      <div className={cx('h-full rounded-full', className)} style={{ width: `${Math.min(100, (value / max) * 100)}%` }} />
    </div>
  );
}
