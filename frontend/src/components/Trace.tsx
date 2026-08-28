import { useState } from 'react';

import type { Trace as TraceData } from '@/lib/api';

/**
 * Why an answer used the passages it did.
 *
 * Retrieval is otherwise invisible: two retrievers disagree, a fusion step
 * merges them and a reranker reorders the result, and the user sees only the
 * last line of that. This shows each stage's verdict on every candidate, which
 * is what "why did it answer that?" actually needs.
 */
export function Trace({ trace, documents }: { trace: TraceData; documents: Map<string, string> }) {
  const [open, setOpen] = useState(false);

  if (!trace.retrieved) {
    return (
      <p className="mt-2 text-xs text-slate-400">
        No search — classified as {trace.intent.replace(/_/g, ' ')} by {trace.intent_decided_by}.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs font-medium text-slate-500 hover:text-slate-900"
      >
        {open ? '▾' : '▸'} retrieval trace · {trace.dense_count} dense, {trace.keyword_count} keyword
        → {trace.fused_count} fused{trace.reranked ? ' → reranked' : ''}
      </button>

      {open && (
        <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs">
          <dl className="grid grid-cols-[7rem_1fr] gap-y-1 text-slate-600">
            <dt className="text-slate-400">dense query</dt>
            <dd className="font-mono">{trace.dense_query}</dd>
            <dt className="text-slate-400">key terms</dt>
            <dd className="font-mono">{trace.key_terms.join(', ') || '—'}</dd>
            <dt className="text-slate-400">top similarity</dt>
            <dd className="font-mono">{trace.top_similarity?.toFixed(3) ?? '—'}</dd>
          </dl>

          <table className="mt-3 w-full text-left">
            <thead className="text-slate-400">
              <tr>
                <th className="pb-1 font-medium">passage</th>
                <th className="pb-1 font-medium">dense</th>
                <th className="pb-1 font-medium">keyword</th>
                <th className="pb-1 font-medium">fused</th>
                <th className="pb-1 font-medium">final</th>
              </tr>
            </thead>
            <tbody className="font-mono text-slate-600">
              {trace.candidates.map((candidate) => (
                <tr key={candidate.chunk_id} className="border-t border-slate-200">
                  <td className="py-1 pr-2">
                    {(documents.get(candidate.document_id) ?? 'document').slice(0, 22)} p{candidate.page}
                  </td>
                  <td>{candidate.dense_rank ?? '—'}</td>
                  <td>{candidate.keyword_rank ?? '—'}</td>
                  <td>{candidate.fused_score.toFixed(4)}</td>
                  <td>{candidate.rerank_position ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-slate-400">
            Ranks are per retriever, 1 is best. A dash means that retriever never found the passage.
          </p>
        </div>
      )}
    </div>
  );
}
