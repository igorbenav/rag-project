/**
 * Client for the public API.
 *
 * Every call here maps to a documented endpoint — there is no private surface
 * for the UI. If the interface can do it, so can curl.
 */

const BASE = '/api/v1';

export type DocumentStatus = 'pending' | 'processing' | 'ready' | 'failed';

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  document_count: number;
  chunk_count: number;
}

export interface Document {
  id: string;
  filename: string;
  status: DocumentStatus;
  page_count: number;
  chunk_count: number;
  error: string | null;
}

export interface IngestionJob {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_documents: number;
  completed_documents: number;
  failed_documents: number;
}

export interface Citation {
  chunk_id: string;
  document_id: string;
  page: number;
  snippet: string;
}

export interface Candidate {
  chunk_id: string;
  document_id: string;
  page: number;
  fused_score: number;
  dense_rank: number | null;
  keyword_rank: number | null;
  rerank_position: number | null;
  found_by: string[];
}

export interface Trace {
  intent: string;
  intent_decided_by: string;
  retrieved: boolean;
  dense_query: string | null;
  keyword_query: string | null;
  key_terms: string[];
  dense_count: number;
  keyword_count: number;
  fused_count: number;
  reranked: boolean;
  top_similarity: number | null;
  candidates: Candidate[];
}

export interface UnsupportedClaim {
  sentence: string;
  reason: string;
}

export interface AnswerTable {
  columns: string[];
  rows: string[][];
}

export interface Query {
  id: string;
  question: string;
  answer: string;
  answered: boolean;
  intent: string;
  answer_list: string[];
  answer_table: AnswerTable | null;
  refusal_reason: string | null;
  disclaimer: string | null;
  citations: Citation[];
  unsupported_claims: UnsupportedClaim[];
  evidence_checked: boolean;
  trace: Trace | null;
  elapsed_seconds: number;
}

export interface Chunk {
  id: string;
  document_id: string;
  content: string;
  page: number;
  ordinal: number;
}

interface Page<T> {
  items: T[];
  total: number;
}

/** An RFC 9457 problem document, which is what every error here is. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly type: string,
    detail: string,
  ) {
    super(detail);
  }
}

/**
 * The key is held in localStorage, which any script running on this origin can
 * read. That is acceptable here because the page loads no third-party code and
 * the server sends a Content-Security-Policy restricting script-src to 'self',
 * so there is no origin from which such a script could arrive.
 *
 * A session cookie marked httpOnly would remove the exposure entirely and is
 * what a multi-user deployment should use; it needs a login flow this demo has
 * no other reason to build.
 */
let apiKey = localStorage.getItem('apiKey') ?? '';

export function setApiKey(key: string): void {
  apiKey = key.trim();
  localStorage.setItem('apiKey', apiKey);
}

export function getApiKey(): string {
  return apiKey;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (apiKey) headers.set('X-API-Key', apiKey);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!response.ok) {
    // Errors are problem+json, so the detail is always in the same place.
    const problem = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      problem.type ?? '/problems/unknown',
      problem.detail ?? response.statusText,
    );
  }

  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const api = {
  listCollections: () => request<Page<Collection>>('/collections?limit=50'),

  createCollection: (name: string) =>
    request<Collection>('/collections', { method: 'POST', body: JSON.stringify({ name }) }),

  getCollection: (id: string) => request<Collection>(`/collections/${id}`),

  listDocuments: (collectionId: string) =>
    request<Page<Document>>(`/collections/${collectionId}/documents?limit=50`),

  ingest: (collectionId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append('files', file));
    return request<IngestionJob>(`/collections/${collectionId}/documents`, {
      method: 'POST',
      body: form,
    });
  },

  getIngestion: (id: string) => request<IngestionJob>(`/ingestions/${id}`),

  ask: (collectionId: string, question: string) =>
    request<Query>(`/collections/${collectionId}/queries`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    }),

  getChunk: (id: string) => request<Chunk>(`/chunks/${id}`),
};
