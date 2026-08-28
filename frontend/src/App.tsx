import { useCallback, useEffect, useState } from 'react';

import { ApiKeyGate } from '@/components/ApiKeyGate';
import { Message } from '@/components/Message';
import { Sidebar } from '@/components/Sidebar';
import { ApiError, api, getApiKey, type Collection, type Document, type Query } from '@/lib/api';

const COLLECTION_NAME = 'My documents';
const POLL_INTERVAL_MS = 1500;

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getApiKey()));
  const [collection, setCollection] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [messages, setMessages] = useState<Query[]>([]);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const filenames = new Map(documents.map((doc) => [doc.id, doc.filename]));

  /** Reuse the demo collection if it exists; the API has no "get or create". */
  const load = useCallback(async () => {
    const existing = await api.listCollections();
    const found =
      existing.items.find((item) => item.name === COLLECTION_NAME) ??
      (await api.createCollection(COLLECTION_NAME));

    setCollection(await api.getCollection(found.id));
    setDocuments((await api.listDocuments(found.id)).items);
  }, []);

  useEffect(() => {
    if (!authed) return;
    load().catch((err) => {
      if (err instanceof ApiError && err.status === 401) setAuthed(false);
      else setError(String(err.message));
    });
  }, [authed, load]);

  const upload = async (files: File[]) => {
    if (!collection) return;
    setIngesting(true);
    setError(null);

    try {
      // Ingestion returns 202 with a job; the UI polls it rather than holding
      // a request open for work that takes as long as it takes.
      const job = await api.ingest(collection.id, files);
      for (;;) {
        const status = await api.getIngestion(job.id);
        setDocuments((await api.listDocuments(collection.id)).items);
        if (status.status === 'completed' || status.status === 'failed') break;
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
      }
      setCollection(await api.getCollection(collection.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIngesting(false);
    }
  };

  const ask = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!collection || !question.trim() || asking) return;

    const asked = question;
    setQuestion('');
    setAsking(true);
    setError(null);

    try {
      const answer = await api.ask(collection.id, asked);
      setMessages((current) => [...current, answer]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setQuestion(asked);
    } finally {
      setAsking(false);
    }
  };

  if (!authed) return <ApiKeyGate onSaved={() => setAuthed(true)} />;

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900">
      <Sidebar collection={collection} documents={documents} busy={ingesting} onUpload={upload} />

      <main className="flex flex-1 flex-col">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.length === 0 && (
              <div className="pt-16 text-center">
                <p className="text-slate-500">Upload a PDF, then ask about it.</p>
                <p className="mt-1 text-sm text-slate-400">
                  Answers cite the page they came from. Greetings don't search.
                </p>
              </div>
            )}

            {messages.map((message) => (
              <Message key={message.id} query={message} documents={filenames} />
            ))}

            {asking && <p className="text-sm text-slate-400">Searching and answering…</p>}
            {error && (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
            )}
          </div>
        </div>

        <form onSubmit={ask} className="border-t border-slate-200 bg-white p-4">
          <div className="mx-auto flex max-w-3xl gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about the documents…"
              className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm outline-none focus:border-slate-900"
            />
            <button
              type="submit"
              disabled={asking || !question.trim()}
              className="rounded-lg bg-slate-900 px-5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-40"
            >
              Ask
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
