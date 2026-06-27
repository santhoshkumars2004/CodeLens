"""
CodeLens Prometheus Metrics Module.

Defines all Prometheus metric collectors used across the application
for monitoring query performance, LLM usage, and ingestion stats.
"""

from prometheus_client import Counter, Histogram, Gauge


# ── Query Metrics ───────────────────────────────────────────────────
query_latency_seconds = Histogram(
    "codelens_query_latency_seconds",
    "Time spent processing a query (retrieval + generation)",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

queries_total = Counter(
    "codelens_queries_total",
    "Total number of queries processed",
    ["repo_id", "status"],
)

# ── LLM Metrics ─────────────────────────────────────────────────────
llm_tokens_used = Counter(
    "codelens_llm_tokens_used_total",
    "Total LLM tokens consumed",
    ["type"],  # "prompt" or "completion"
)

llm_latency_seconds = Histogram(
    "codelens_llm_latency_seconds",
    "Time spent on LLM inference calls",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# ── Retrieval Metrics ───────────────────────────────────────────────
retrieval_latency_seconds = Histogram(
    "codelens_retrieval_latency_seconds",
    "Time spent on vector retrieval",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
)

chunks_retrieved = Histogram(
    "codelens_chunks_retrieved",
    "Number of chunks retrieved per query",
    buckets=[1, 3, 5, 10, 15, 20],
)

# ── Ingestion Metrics ───────────────────────────────────────────────
ingestion_duration_seconds = Histogram(
    "codelens_ingestion_duration_seconds",
    "Time spent indexing a repository",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

files_indexed_total = Counter(
    "codelens_files_indexed_total",
    "Total number of files indexed across all repos",
)

chunks_stored_total = Counter(
    "codelens_chunks_stored_total",
    "Total number of chunks stored in vector DB",
)

repos_indexed = Gauge(
    "codelens_repos_indexed",
    "Number of repositories currently indexed",
)
