import { useState } from 'react';

import { api, type Chunk, type Citation, type Query } from '@/lib/api';
import { Trace } from './Trace';

/** A citation that expands into the passage it points at. */
function CitationChip({ citation, filename }: { citation: Citation; filename: string }) {
  const [chunk, setChunk] = useState<Chunk | null>(null);
  const [open, setOpen] = useState(false);

  const toggle = async () => {
    setOpen(!open);
    // Fetched on demand from /chunks/{id} — the same URL an API client uses.
    if (!chunk) setChunk(await api.getChunk(citation.chunk_id));
  };

  return (
    <>
      <button
        onClick={toggle}
        title={citation.snippet}
        className="rounded border border-slate-300 bg-white px-1.5 py-0.5 text-xs text-slate-600 hover:border-slate-900 hover:text-slate-900"
      >
        {filename.replace(/\.pdf$/i, '').slice(0, 24)} p{citation.page}
      </button>
      {open && chunk && (
        <p className="mt-2 w-full whitespace-pre-wrap rounded bg-slate-50 p-3 text-xs leading-relaxed text-slate-600">
          {chunk.content}
        </p>
      )}
    </>
  );
}

/** Renders whichever shape the shaping pass produced, defaulting to prose. */
function AnswerBody({ query }: { query: Query }) {
  const prose = (
    <p className={`text-sm ${query.answered ? 'text-slate-800' : 'text-slate-500 italic'}`}>
      {query.answer}
    </p>
  );

  if (query.answer_table) {
    return (
      <>
        {prose}
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                {query.answer_table.columns.map((column) => (
                  <th key={column} className="border-b border-slate-200 pb-1 pr-4 font-medium">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-slate-800">
              {query.answer_table.rows.map((row) => (
                <tr key={row.join('|')}>
                  {row.map((cell, index) => (
                    <td key={index} className="border-b border-slate-100 py-1 pr-4">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </>
    );
  }

  if (query.answer_list.length > 0) {
    return (
      <>
        {prose}
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-800">
          {query.answer_list.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </>
    );
  }

  return prose;
}

export function Message({ query, documents }: { query: Query; documents: Map<string, string> }) {
  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-slate-900">{query.question}</p>

      <div className="rounded-lg border border-slate-200 bg-white p-4">
        {query.disclaimer && (
          <p className="mb-2 rounded bg-amber-50 px-2 py-1 text-xs text-amber-800">{query.disclaimer}</p>
        )}

        <AnswerBody query={query} />

        {query.unsupported_claims.length > 0 && (
          <div className="mt-2 rounded bg-red-50 px-2 py-1.5">
            <p className="text-xs font-medium text-red-800">
              Not supported by the cited passages:
            </p>
            {query.unsupported_claims.map((claim) => (
              <p key={claim.sentence} className="text-xs text-red-700">
                “{claim.sentence}” — {claim.reason}
              </p>
            ))}
          </div>
        )}

        {query.citations.length > 0 && (
          <div className="mt-3 flex flex-wrap items-start gap-1.5">
            {query.citations.map((citation) => (
              <CitationChip
                key={citation.chunk_id}
                citation={citation}
                filename={documents.get(citation.document_id) ?? 'document'}
              />
            ))}
          </div>
        )}

        {query.trace && <Trace trace={query.trace} documents={documents} />}

        <p className="mt-2 text-xs text-slate-400">
          {query.elapsed_seconds.toFixed(2)}s
          {query.refusal_reason && ` · ${query.refusal_reason.replace(/_/g, ' ')}`}
          {query.evidence_checked && ' · evidence checked'}
        </p>
      </div>
    </div>
  );
}
