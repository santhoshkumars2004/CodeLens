/**
 * StackSense — API Client
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import type {
  QueryResponse,
  IngestResponse,
  RepoInfo,
  IngestStatus,
} from "./types";

export async function ingestRepo(
  repoUrl: string,
  branch?: string
): Promise<IngestResponse> {
  const res = await fetch(`${API_URL}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
): Promise<QueryResponse> {
  const body: Record<string, unknown> = {
    repo_id: repoId,
    question,
    top_k: topK,
  };
  if (languageFilter) body.language_filter = languageFilter;
  if (pathFilter) body.path_filter = pathFilter;

  const res = await fetch(`${API_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
