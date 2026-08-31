/**
 * CodeLens — API Client
 *
 * IMPORTANT: NEXT_PUBLIC_API_URL must be set in Vercel environment variables
 * AND the project must be redeployed after setting it for the variable to
 * be baked into the production JS bundle.
 *
 * Set it to: https://codelens-production-c946.up.railway.app
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://codelens-production-c946.up.railway.app";

import type {
  QueryResponse,
  IngestResponse,
  RepoInfo,
  IngestStatus,
} from "./types";
import type { Message } from "./types";

export async function ingestRepo(
  repoUrl: string,
  branch?: string,
  token?: string | null,
): Promise<IngestResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}/api/ingest`, {
    method: "POST",
    headers,
    body: JSON.stringify({ repo_url: repoUrl, branch }),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Ingestion failed");
  }

  return res.json();
}

export async function queryRepo(
  repoId: string,
  question: string,
  topK: number = 5,
  languageFilter?: string,
  pathFilter?: string,
  token?: string | null,
): Promise<QueryResponse> {
  const body: Record<string, unknown> = {
    repo_id: repoId,
    question,
    top_k: topK,
  };
  if (languageFilter) body.language_filter = languageFilter;
  if (pathFilter) body.path_filter = pathFilter;

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Query failed");
  }

  return res.json();
}

export async function listRepos(): Promise<{
  repos: RepoInfo[];
  total: number;
}> {
  const res = await fetch(`${API_URL}/api/repos`);

  if (!res.ok) {
    throw new Error("Failed to fetch repos");
  }

  return res.json();
}

export async function deleteRepo(repoId: string): Promise<{ status: string, message: string }> {
  const res = await fetch(`${API_URL}/api/repos/${repoId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Failed to delete repository");
  }
  return res.json();
}

export async function getIngestStatus(
  repoId: string
): Promise<IngestStatus> {
  const [owner, repo] = repoId.split("/");
  const res = await fetch(`${API_URL}/api/ingest/status/${owner}/${repo}`);

  if (!res.ok) {
    throw new Error("Failed to get status");
  }

  return res.json();
}

export async function checkHealth(): Promise<{
  status: string;
  version: string;
  chromadb_connected: boolean;
}> {
  const res = await fetch(`${API_URL}/health`);
  return res.json();
}

export async function getChatHistory(repoId: string, token: string): Promise<Message[]> {
  const [owner, repo] = repoId.split("/");
  const res = await fetch(`${API_URL}/api/query/history/${owner}/${repo}`, {
    headers: {
      "Authorization": `Bearer ${token}`
    }
  });

  if (!res.ok) {
    console.error("Failed to fetch chat history");
    return [];
  }

  const data = await res.json();
  return data.messages;
}

export interface RepoFile {
  file_path: string;
  language: string;
  chunk_count: number;
}

export interface RepoFilesResponse {
  files: RepoFile[];
  total_files: number;
  languages: string[];
  total_chunks: number;
}

export async function getRepoFiles(repoId: string): Promise<RepoFilesResponse> {
  const [owner, repo] = repoId.split("/");
  const res = await fetch(`${API_URL}/api/repos/${owner}/${repo}/files`);

  if (!res.ok) {
    throw new Error("Failed to fetch file tree");
  }

  return res.json();
}

// ── Streaming Query ────────────────────────────────────────────────────────

export interface StreamCallbacks {
  /** Called immediately when citations arrive (< 1s after sending) */
  onCitations: (citations: QueryResponse["citations"], confidence: number) => void;
  /** Called for each LLM output token */
  onToken: (token: string) => void;
  /** Called when the full stream is complete */
  onDone: (latencyMs: number, fullAnswer: string) => void;
  /** Called if an error occurs */
  onError: (message: string) => void;
}

/**
 * Stream an AI answer word-by-word using Server-Sent Events.
 * Uses fetch + ReadableStream so we can pass auth headers (EventSource can't).
 */
export async function streamQuery(
  repoId: string,
  question: string,
  topK: number = 5,
  languageFilter: string | undefined,
  pathFilter: string | undefined,
  token: string | null | undefined,
  callbacks: StreamCallbacks,
): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const body: Record<string, unknown> = { repo_id: repoId, question, top_k: topK };
  if (languageFilter) body.language_filter = languageFilter;
  if (pathFilter)     body.path_filter     = pathFilter;

  const res = await fetch(`${API_URL}/api/query/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Stream request failed");
  }

  if (!res.body) throw new Error("Response body is null");

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let   buffer  = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by double newlines
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";   // keep incomplete last chunk

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      try {
        const payload = JSON.parse(line.slice(6));
        if (payload.type === "citations") {
          callbacks.onCitations(payload.citations, payload.confidence ?? 0);
        } else if (payload.type === "token") {
          callbacks.onToken(payload.t);
        } else if (payload.type === "done") {
          callbacks.onDone(payload.latency_ms, payload.answer);
        } else if (payload.type === "error") {
          callbacks.onError(payload.message);
        }
      } catch {
        // Skip malformed SSE lines
      }
    }
  }
}
