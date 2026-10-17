import type { ReactNode } from 'react';
import { AlertTriangle, Info, Loader2, RefreshCw, ShieldAlert, ShieldQuestion, Shield, Sparkles } from 'lucide-react';
import type { Decision, ReviewStatus } from '../api/types';
import type { ApiError } from '../api/client';
import { decisionLabel, statusLabel } from '../lib/format';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Card({ title, icon, actions, children, className }: {
  title?: ReactNode;
  icon?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx('card', className)}>
      {title && (
        <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink-900">
            {icon}
            {title}
          </h2>
          {actions}
        </div>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

const decisionStyle: Record<Decision, string> = {
  high_risk: 'bg-rose-50 text-rose-700 ring-rose-200',
  review: 'bg-amber-50 text-amber-800 ring-amber-200',
  low_risk: 'bg-slate-100 text-slate-700 ring-slate-200',
};
const decisionIcon: Record<Decision, typeof Shield> = {
  high_risk: ShieldAlert,
  review: ShieldQuestion,
  low_risk: Shield,
};

export function DecisionBadge({ decision, size = 'sm' }: { decision: Decision; size?: 'sm' | 'lg' }) {
  const Icon = decisionIcon[decision];
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full font-medium ring-1 ring-inset',
        size === 'lg' ? 'px-3 py-1 text-sm' : 'px-2 py-0.5 text-xs',
        decisionStyle[decision],
      )}
    >
      <Icon className={size === 'lg' ? 'size-4' : 'size-3.5'} aria-hidden />
      {decisionLabel[decision]}
    </span>
  );
}

const statusStyle: Record<ReviewStatus, string> = {
  pending: 'bg-sky-50 text-sky-700 ring-sky-200',
  confirmed: 'bg-ink-900 text-white ring-ink-900',
  rejected: 'bg-slate-100 text-slate-500 ring-slate-200 line-through decoration-slate-400',
};

export function StatusBadge({ status }: { status: ReviewStatus }) {
  return (
    <span className={cx('inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', statusStyle[status])}>
      {statusLabel[status]}
    </span>
  );
}

export function NovelBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 ring-1 ring-violet-200 ring-inset">
      <Sparkles className="size-3.5" aria-hidden />
      Unfamiliar
    </span>
  );
}

export function CandidateBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900 ring-1 ring-amber-300 ring-inset">
      <AlertTriangle className="size-3.5" aria-hidden />
      Candidate variant
    </span>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'alert' | 'accent' }) {
  return (
    <div className="card p-4">
      <div className="label">{label}</div>
      <div
        className={cx(
          'mt-1.5 text-2xl font-semibold tabular-nums',
          tone === 'alert' ? 'text-rose-600' : tone === 'accent' ? 'text-accent-700' : 'text-ink-900',
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function ErrorNotice({ error, onRetry }: { error: ApiError; onRetry?: () => void }) {
  const hint =
    error.status === 0
      ? 'Start the API with `docker compose up --build -d --wait`, then retry.'
      : error.status === 401
        ? 'This deployment is authenticated. Add an API key under Connection.'
        : error.status === 429
          ? `The engine queue is full. ${error.retryAfter ? `Try again in ${error.retryAfter}s.` : 'Try again shortly.'}`
          : error.status === 503
            ? 'The engine or storage is unavailable. An operator may need to restart the service.'
            : null;
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{error.message}</p>
        {hint && <p className="mt-1 text-rose-800">{hint}</p>}
        <p className="mt-1 font-mono text-xs text-rose-700/80">
          {error.status ? `HTTP ${error.status} · ` : ''}
          {error.code}
          {error.requestId && ` · request ${error.requestId}`}
        </p>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn btn-ghost shrink-0 py-1.5">
          <RefreshCw className="size-3.5" aria-hidden /> Retry
        </button>
      )}
    </div>
  );
}

export function Note({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' }) {
  return (
    <div
      className={cx(
        'flex items-start gap-2.5 rounded-lg p-3 text-sm',
        tone === 'warn' ? 'bg-amber-50 text-amber-900' : 'bg-slate-100 text-slate-600',
      )}
    >
      <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div>{children}</div>
    </div>
  );
}

export function Spinner({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-slate-500" role="status">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}…
    </div>
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">{icon}</div>
      <p className="font-medium text-ink-900">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={cx('rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700', className)}>{children}</code>;
}
