"""
StackSense RAG Pipeline.

Orchestrates the full query pipeline:
Question → Retrieve → Rerank → Generate → Response.
"""

import time
from typing import Dict, Any

from app.core.retriever import retrieve
from app.core.reranker import rerank_chunks
from app.core.generator import generate
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.metrics import query_latency_seconds, queries_total

logger = get_logger(__name__)
settings = get_settings()


def query_pipeline(
    question: str,
    repo_id: str,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Execute the full RAG pipeline for a codebase question.

    Flow: Retrieve top-k chunks → Rerank → Generate answer with LLM.

    Args:
        question: Natural language question about the codebase.
        repo_id: Repository identifier.
        top_k: Number of final chunks to use for generation.

    Returns:
        Complete response with answer, citations, and metrics.
    """
    start_time = time.time()

    try:
        # Step 1: Retrieve relevant chunks (get more than needed for reranking)
        retrieved_chunks = retrieve(
            question=question,
            repo_id=repo_id,
            top_k=settings.retriever_top_k,
        )

        if not retrieved_chunks:
            queries_total.labels(repo_id=repo_id, status="no_results").inc()
            return {
                "answer": "I couldn't find any relevant code in this repository "
                          "to answer your question. The repository might not be "
                          "indexed yet, or the question might not relate to the "
                          "codebase content.",
                "citations": [],
                "confidence_score": 0.0,
                "query": question,
                "repo_id": repo_id,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
            }

        # Step 2: Rerank for better relevance
        reranked_chunks = rerank_chunks(
            question=question,
            chunks=retrieved_chunks,
            top_k=top_k,
        )

        # Step 3: Generate answer with LLM
        result = generate(
            question=question,
            chunks=reranked_chunks,
            repo_id=repo_id,
        )

        latency_ms = round((time.time() - start_time) * 1000, 2)
        query_latency_seconds.observe(latency_ms / 1000)
        queries_total.labels(repo_id=repo_id, status="success").inc()

        # Calculate confidence from rerank scores
        if reranked_chunks:
            avg_score = sum(
                c.get("rerank_score", 0) for c in reranked_chunks
            ) / len(reranked_chunks)
            confidence = min(max(avg_score, 0), 1)
        else:
            confidence = 0.0

        response = {
            "answer": result["answer"],
            "citations": result["citations"],
            "confidence_score": round(confidence, 4),
            "query": question,
            "repo_id": repo_id,
            "latency_ms": latency_ms,
        }

        logger.info(
            "query_completed",
            repo_id=repo_id,
            latency_ms=latency_ms,
            citations=len(result["citations"]),
            confidence=round(confidence, 4),
        )

        return response

    except Exception as e:
        queries_total.labels(repo_id=repo_id, status="error").inc()
        logger.error("query_failed", repo_id=repo_id, error=str(e))
        raise
