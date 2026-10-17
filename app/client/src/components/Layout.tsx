import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Activity, BookOpen, Layers, Menu, PlugZap, ScanText, X } from 'lucide-react';
import { modelWording } from '../lib/format';
import { useObservatory } from '../lib/observatory';
import { ConnectionDialog } from './ConnectionDialog';
import { cx } from './ui';

const nav = [
  { to: '/', label: 'Overview', icon: Activity, end: true },
  { to: '/scan', label: 'Scan messages', icon: ScanText },
  { to: '/variants', label: 'Variant queue', icon: Layers },
  { to: '/model', label: 'Model & limits', icon: BookOpen },
];

function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8" aria-hidden>
        <rect width="32" height="32" rx="8" className="fill-ink-800" />
        <circle cx="16" cy="16" r="9" fill="none" className="stroke-accent-500" strokeWidth="2" />
        <circle cx="16" cy="16" r="4" fill="none" className="stroke-accent-500" strokeWidth="2" opacity=".6" />
        <circle cx="22" cy="11" r="2.5" className="fill-amber-400" />
      </svg>
      <div className="leading-tight">
        <div className="text-sm font-semibold text-white">Scam Variant</div>
        <div className="text-xs text-accent-500">Observatory · Sri Lanka</div>
      </div>
    </div>
  );
}

function StatusPill() {
  const { ready, model } = useObservatory();
  const ok = !!ready.data && !ready.error;
  const mode = model.data?.mode;
  return (
    <div className="space-y-2 rounded-lg bg-ink-950/50 p-3 text-xs">
      <div className="flex items-center gap-2">
        <span className={cx('size-2 rounded-full', ok ? 'bg-accent-500' : ready.loading && !ready.error ? 'bg-slate-400' : 'bg-rose-500')} />
        <span className="font-medium text-white">{ok ? 'Engine ready' : ready.loading && !ready.error ? 'Connecting…' : 'Engine unavailable'}</span>
      </div>
      {ready.data && <div className="font-mono text-slate-400">{ready.data.model_version}</div>}
      {mode && (
        <div className={cx('inline-block rounded px-1.5 py-0.5 font-medium', mode === 'local_demo' ? 'bg-amber-400/15 text-amber-300' : 'bg-accent-500/15 text-accent-500')}>
          {mode === 'local_demo' ? 'Local demo mode' : 'Authenticated'}
        </div>
      )}
    </div>
  );
}

export function Layout() {
  const { monitoring, model } = useObservatory();
  const [open, setOpen] = useState(false);
  const [conn, setConn] = useState(false);
  const pending = monitoring.data?.pending_count ?? 0;

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <Logo />
      <nav className="flex flex-col gap-1" aria-label="Main">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setOpen(false)}
            className={({ isActive }) =>
              cx(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition',
                isActive ? 'bg-white/10 text-white' : 'text-slate-300 hover:bg-white/5 hover:text-white',
              )
            }
          >
            <Icon className="size-4" aria-hidden />
            <span className="flex-1">{label}</span>
            {to === '/variants' && pending > 0 && (
              <span className="rounded-full bg-amber-400 px-1.5 text-xs font-semibold text-ink-900" aria-label={`${pending} pending`}>
                {pending}
              </span>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto space-y-3">
        <StatusPill />
        <button type="button" onClick={() => setConn(true)} className="btn w-full justify-start text-slate-300 hover:bg-white/5 hover:text-white">
          <PlugZap className="size-4" aria-hidden /> Connection
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 hidden w-64 bg-ink-900 lg:block">{sidebar}</aside>

      <div className="sticky top-0 z-30 flex items-center justify-between bg-ink-900 px-4 py-3 lg:hidden">
        <Logo />
        <button type="button" onClick={() => setOpen(true)} className="rounded-lg p-2 text-white hover:bg-white/10" aria-label="Open menu">
          <Menu className="size-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-ink-950/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-ink-900">
            <button type="button" onClick={() => setOpen(false)} className="absolute top-4 right-3 rounded p-1 text-slate-300 hover:text-white" aria-label="Close menu">
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-10">
        <Outlet />
        <footer className="mt-16 border-t border-slate-200 pt-6 text-xs text-slate-400">
          Private, unreviewed demonstration. {modelWording(model.data).summary} Low risk does not mean safe.
        </footer>
      </main>

      {conn && <ConnectionDialog onClose={() => setConn(false)} />}
    </div>
  );
}
