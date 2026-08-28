import { useState } from 'react';

import { setApiKey } from '@/lib/api';

/**
 * Shown when the API rejects the stored key.
 *
 * The key is issued by the backend on first start and printed to its log; this
 * is the same credential any other client would present.
 */
export function ApiKeyGate({ onSaved }: { onSaved: () => void }) {
  const [value, setValue] = useState('');

  return (
    <div className="flex h-screen items-center justify-center bg-slate-50">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setApiKey(value);
          onSaved();
        }}
        className="w-96 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="text-lg font-semibold text-slate-900">API key required</h1>
        <p className="mt-1 text-sm text-slate-500">
          One is created on first start and written to the backend log:
          <code className="mt-2 block rounded bg-slate-100 px-2 py-1 text-xs">
            docker compose logs web | grep rag_
          </code>
        </p>
        <input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="rag_…"
          className="mt-4 w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900"
        />
        <button
          type="submit"
          className="mt-3 w-full rounded-md bg-slate-900 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Continue
        </button>
      </form>
    </div>
  );
}
