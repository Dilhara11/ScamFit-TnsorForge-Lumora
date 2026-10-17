import { useEffect, useRef, useState, type FormEvent } from 'react';
import { X } from 'lucide-react';
import { setConnection, useConnection } from '../lib/connection';
import { clearEvidence, setRetainEvidence, useEvidence } from '../lib/evidence';
import { useObservatory } from '../lib/observatory';

export function ConnectionDialog({ onClose }: { onClose: () => void }) {
  const conn = useConnection();
  const evidence = useEvidence();
  const { model } = useObservatory();
  const [form, setForm] = useState(conn);
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    ref.current?.showModal();
  }, []);

  function save(e: FormEvent) {
    e.preventDefault();
    setConnection({ baseUrl: form.baseUrl.trim(), apiKey: form.apiKey.trim(), analyst: form.analyst.trim() });
    onClose();
  }

  const authenticated = model.data?.mode === 'authenticated';

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="m-auto w-full max-w-lg rounded-xl p-0 shadow-xl backdrop:bg-ink-950/60"
      aria-labelledby="conn-title"
    >
      <form onSubmit={save}>
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <h2 id="conn-title" className="font-semibold text-ink-900">Connection</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-slate-400 hover:text-slate-700" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        <div className="space-y-5 px-6 py-5">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">API base URL</span>
            <input
              className="input mt-1 font-mono"
              value={form.baseUrl}
              onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
              placeholder="Same origin (via proxy)"
            />
            <span className="mt-1 block text-xs text-slate-500">
              Leave empty to use this site's proxy. A different origin must be listed in <code>SVO_ALLOWED_ORIGINS</code>.
            </span>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">API key {authenticated ? '' : '(authenticated mode only)'}</span>
            <input
              className="input mt-1 font-mono"
              type="password"
              autoComplete="off"
              value={form.apiKey}
              onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
            />
            <span className="mt-1 block text-xs text-slate-500">Held in this tab's session storage only and sent as <code>X-API-Key</code>.</span>
          </label>
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Analyst alias (local demo)</span>
            <input
              className="input mt-1"
              value={form.analyst}
              maxLength={80}
              pattern="[A-Za-z0-9._ \-]+"
              disabled={authenticated}
              onChange={(e) => setForm({ ...form, analyst: e.target.value })}
              placeholder={authenticated ? 'Derived from your API key' : 'local-demo-analyst'}
            />
            <span className="mt-1 block text-xs text-slate-500">
              Recorded on reviews as an <em>unverified</em> name. Letters, digits, space, <code>. _ -</code>.
            </span>
          </label>
          <fieldset className="rounded-lg border border-slate-200 p-4">
            <legend className="px-1 text-sm font-medium text-slate-700">Local evidence</legend>
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 accent-accent-600"
                checked={evidence.retain}
                onChange={(e) => setRetainEvidence(e.target.checked)}
              />
              <span>
                Keep submitted message text in this browser so cluster members can be read.
                <span className="block text-xs text-slate-500">The server never stores message text. {evidence.items.length} items stored here.</span>
              </span>
            </label>
            <button type="button" className="btn btn-ghost mt-3 py-1.5 text-xs" onClick={clearEvidence} disabled={!evidence.items.length}>
              Clear local evidence
            </button>
          </fieldset>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 px-6 py-4">
          <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn btn-primary">Save</button>
        </div>
      </form>
    </dialog>
  );
}
