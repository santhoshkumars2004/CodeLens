"""
CodeLens -- Streaming Query Pipeline (app/query/stream_pipeline.py)

Async generator that executes the full RAG flow and yields Server-Sent Events:
  1. Retrieve chunks  ->  yield "citations" event (immediately, < 1s)
  2. Rerank chunks
  3. Stream LLM tokens ->  yield "token" events (word-by-word)
  4. yield "done" event with final metadata + save to Supabase
"""

import asyncio
import json
import time
from typing import AsyncGenerator, List, Dict, Any

from app.retrieval.retriever import retrieve
from app.retrieval.reranker import rerank_chunks
from app.llm.client import generate_answer_stream
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.metrics import query_latency_seconds, queries_total
from app.db.supabase import save_chat_history

logger = get_logger(__name__)
settings = get_settings()


def _build_citations(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build citation objects from reranked chunk metadata."""
    citations = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        citations.append({
            "file_path":       meta.get("file_path", "unknown"),
            "start_line":      meta.get("start_line", 0),
            "end_line":        meta.get("end_line", 0),
            "content":         chunk.get("content", ""),
            "language":        meta.get("language", "unknown"),
            "relevance_score": round(
                chunk.get("rerank_score", chunk.get("relevance_score", 0)), 4
            ),
        })
    return citations


async def stream_query_pipeline(
    question: str,
    repo_id: str,
    top_k: int = 5,
    where: dict | None = None,
    path_filter: str | None = None,
    user_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator yielding SSE-formatted strings for the streaming endpoint.

    Event types emitted:
      {"type": "citations", "citations": [...], "confidence": 0.82}
      {"type": "token",     "t": "The "}
      {"type": "done",      "latency_ms": 1240, "answer": "...full text..."}
      {"type": "error",     "message": "..."}
    """
    start_time = time.time()

    def sse(payload: dict) -> str:
        return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

    try:
        # Step 1: Retrieve
        retrieved_chunks = await retrieve(
            question=question,
            repo_id=repo_id,
            top_k=settings.retriever_top_k,
            where=where,
        )

        # Step 1b: Path filter
        if path_filter and retrieved_chunks:
            filtered = [
                c for c in retrieved_chunks
                if path_filter.lower() in c.get("metadata", {}).get("file_path", "").lower()
            ]
            if filtered:
                retrieved_chunks = filtered

        if not retrieved_chunks:
            queries_total.labels(repo_id=repo_id, status="no_results").inc()
            yield sse({
                "type": "error",
                "message": (
                    "I could not find any relevant code to answer your question. "
                    "The repository might not be indexed yet."
                ),
            })
            return

        # Step 2: Rerank
        reranked_chunks = rerank_chunks(
            question=question,
            chunks=retrieved_chunks,
            top_k=top_k,
        )

        # Step 3: Emit citations immediately (before LLM starts)
        citations = _build_citations(reranked_chunks)
        if reranked_chunks:
            avg_score = sum(c.get("rerank_score", 0) for c in reranked_chunks) / len(reranked_chunks)
            confidence = round(min(max(avg_score, 0.0), 1.0), 4)
        else:
            confidence = 0.0

        yield sse({"type": "citations", "citations": citations, "confidence": confidence})

        # Step 4: Run LLM stream in thread pool (sync generator -> async)
        full_answer_parts: List[str] = []
        loop = asyncio.get_event_loop()

        def _collect_tokens() -> List[str]:
            return list(generate_answer_stream(question, reranked_chunks, repo_id))

        tokens = await loop.run_in_executor(None, _collect_tokens)

        for token in tokens:
            full_answer_parts.append(token)
            yield sse({"type": "token", "t": token})
            await asyncio.sleep(0)  # yield control back to event loop

        full_answer = "".join(full_answer_parts)
        latency_ms = round((time.time() - start_time) * 1000, 2)

        query_latency_seconds.observe(latency_ms / 1000)
        queries_total.labels(repo_id=repo_id, status="success").inc()

        yield sse({"type": "done", "latency_ms": latency_ms, "answer": full_answer})

        # Step 5: Save to Supabase after stream completes
        if user_id:
            try:
                save_chat_history(
                    user_id=user_id,
                    repo_id=repo_id,
                    question=question,
                    answer=full_answer,
                    citations=citations,
                )
            except Exception as save_err:
                logger.warning("stream_save_history_failed", error=str(save_err))

        logger.info(
            "stream_pipeline_complete",
            repo_id=repo_id,
            latency_ms=latency_ms,
            tokens=len(tokens),
            citations=len(citations),
        )

    except Exception as e:
        queries_total.labels(repo_id=repo_id, status="error").inc()
        logger.error("stream_pipeline_failed", repo_id=repo_id, error=str(e))
        yield sse({"type": "error", "message": "Query failed: " + str(e)})
