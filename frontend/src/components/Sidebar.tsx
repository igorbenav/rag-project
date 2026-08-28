import { useRef, useState } from 'react';

import type { Collection, Document } from '@/lib/api';

interface Props {
  collection: Collection | null;
  documents: Document[];
  busy: boolean;
  onUpload: (files: File[]) => void;
}

const STATUS_STYLES: Record<Document['status'], string> = {
  ready: 'text-emerald-700 bg-emerald-50',
  processing: 'text-amber-700 bg-amber-50',
  pending: 'text-slate-600 bg-slate-100',
  failed: 'text-red-700 bg-red-50',
};

export function Sidebar({ collection, documents, busy, onUpload }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const send = (files: FileList | null) => {
    const pdfs = Array.from(files ?? []).filter((f) => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfs.length) onUpload(pdfs);
  };

  return (
    <aside className="w-80 shrink-0 border-r border-slate-200 bg-white p-5 flex flex-col gap-5 overflow-y-auto">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Ask your PDFs</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {collection
            ? `${collection.document_count} document(s), ${collection.chunk_count} chunks`
            : 'Loading…'}
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          send(e.dataTransfer.files);
        }}
        onClick={() => input.current?.click()}
        className={`rounded-lg border-2 border-dashed p-6 text-center cursor-pointer transition ${
          dragging ? 'border-slate-900 bg-slate-50' : 'border-slate-300 hover:border-slate-400'
        }`}
      >
        <p className="text-sm font-medium text-slate-700">
          {busy ? 'Ingesting…' : 'Drop PDFs, or click to choose'}
        </p>
        <p className="text-xs text-slate-400 mt-1">Extracted, chunked and embedded on upload</p>
        <input
          ref={input}
          type="file"
          accept="application/pdf"
          multiple
          aria-label="Choose PDF files to ingest"
          // Visually hidden rather than `hidden`: a hidden input is removed
          // from the accessibility tree and cannot be reached by keyboard.
          className="sr-only"
          onChange={(e) => {
            send(e.target.files);
            e.target.value = '';
          }}
        />
      </div>

      <div className="flex-1">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
          Documents
        </h2>
        {documents.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing ingested yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {documents.map((doc) => (
              <li key={doc.id} className="text-sm">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate text-slate-700" title={doc.filename}>
                    {doc.filename}
                  </span>
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-xs ${STATUS_STYLES[doc.status]}`}>
                    {doc.status}
                  </span>
                </div>
                {doc.status === 'ready' && (
                  <span className="text-xs text-slate-400">
                    {doc.page_count} pages · {doc.chunk_count} chunks
                  </span>
                )}
                {doc.error && <span className="text-xs text-red-600">{doc.error}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
