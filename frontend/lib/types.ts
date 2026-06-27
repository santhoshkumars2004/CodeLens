/**
 * CodeLens — TypeScript Type Definitions
 */

export interface Citation {
  file_path: string;
  start_line: number;
  end_line: number;
  content: string;
  language: string;
  relevance_score: number;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  confidence_score: number;
  query: string;
  repo_id: string;
  latency_ms: number;
  rewritten_query?: string;
}

export interface IngestResponse {
  repo_id: string;
  status: string;
  files_indexed: number;
  chunks_created: number;
  languages: string[];
  duration_seconds: number;
  message: string;
}

export interface RepoInfo {
  repo_id: string;
  repo_url: string;
  files_indexed: number;
  chunks_count: number;
  languages: string[];
  indexed_at: string;
  status: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence_score?: number;
  latency_ms?: number;
  timestamp: Date;
}

export interface IngestStatus {
  repo_id: string;
  status: string;
  progress: number;
  message: string;
}
