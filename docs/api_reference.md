# StackSense — API Reference

Base URL: `http://localhost:8000`

---

## Health Check

### `GET /health`

Check if the backend and its dependencies are healthy.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "chromadb_connected": true,
  "timestamp": "2024-01-01T00:00:00.000000"
}
```

---

## Ingest Repository

### `POST /api/ingest`

Clone and index a GitHub repository.

**Request Body:**
```json
{
  "repo_url": "https://github.com/owner/repo",
  "branch": "main"  // optional
}
```

**Response:**
```json
{
  "repo_id": "owner/repo",
  "status": "completed",
  "files_indexed": 142,
  "chunks_created": 567,
  "languages": ["python", "javascript", "yaml"],
  "duration_seconds": 23.45,
  "message": "Successfully indexed 142 files into 567 chunks"
}
```

---

## Query Codebase

### `POST /api/query`

Ask a natural language question about an indexed repository.

**Request Body:**
```json
{
  "repo_id": "owner/repo",
  "question": "How does authentication work?",
  "top_k": 5  // optional, default 5
}
```

**Response:**
```json
{
  "answer": "Authentication is handled in...",
  "citations": [
    {
      "file_path": "src/auth/login.py",
      "start_line": 45,
      "end_line": 67,
      "content": "def authenticate(...):\n...",
      "language": "python",
      "relevance_score": 0.92
    }
  ],
  "confidence_score": 0.87,
  "query": "How does authentication work?",
  "repo_id": "owner/repo",
  "latency_ms": 2340.5
}
```

---

## List Repositories

### `GET /api/repos`

List all indexed repositories.

**Response:**
```json
{
  "repos": [
    {
      "repo_id": "owner/repo",
      "repo_url": "https://github.com/owner/repo",
      "files_indexed": 142,
      "chunks_count": 567,
      "languages": ["python"],
      "indexed_at": "2024-01-01T00:00:00",
      "status": "indexed"
    }
  ],
  "total": 1
}
```

---

## Metrics

### `GET /metrics`

Prometheus-compatible metrics endpoint.

Key metrics:
- `stacksense_query_latency_seconds` — Query processing time
- `stacksense_queries_total` — Total queries by repo and status
- `stacksense_llm_tokens_used_total` — LLM token consumption
- `stacksense_ingestion_duration_seconds` — Repo indexing time
- `stacksense_repos_indexed` — Number of indexed repos

---

## Interactive Docs

- **Swagger UI**: `GET /docs`
- **ReDoc**: `GET /redoc`
