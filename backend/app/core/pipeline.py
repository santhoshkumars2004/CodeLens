"""
CodeLens RAG Pipeline.

Orchestrates the full query pipeline:
Question → Retrieve → Rerank → Generate → Response.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any

from app.core.retriever import retrieve
from app.core.reranker import rerank_chunks
from app.core.generator import generate
from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.metrics import query_latency_seconds, queries_total

logger = get_logger(__name__)
settings = get_settings()


def _load_skip_manifest(repo_id: str) -> Dict[str, str]:
    """
    Load the skip manifest for a repo — maps relative_path → skip reason.
    Returns empty dict if the manifest doesn't exist yet (pre-fix ingestion).
    """
    safe_id = repo_id.replace("/", "_")
    manifest_path = Path(settings.chroma_persist_dir) / f"skip_manifest_{safe_id}.json"
    if not manifest_path.exists():
        return {}
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("skip_manifest_load_failed", repo_id=repo_id, error=str(exc))
        return {}


def _detect_filtered_file(question: str, skip_manifest: Dict[str, str]) -> Dict[str, str] | None:
    """
    Check if the user's question mentions any file that was filtered during ingestion.

    Strategy: extract word tokens from the question and look for any skip_manifest
    key that contains that token (case-insensitive, partial match on filename).

    Returns a dict {path, reason} for the best match, or None.
    """
    if not skip_manifest:
        return None

    question_lower = question.lower()
    # Split into meaningful tokens (ignore short words)
    tokens = [t.strip("'\".,?!()") for t in question_lower.split() if len(t) > 3]

    best_match = None
    for skipped_path, reason in skip_manifest.items():
        skipped_name = Path(skipped_path).name.lower()
        skipped_path_lower = skipped_path.lower().replace("\\", "/")

        for token in tokens:
            # Match on filename or path segment
            if token in skipped_name or token in skipped_path_lower:
                best_match = {"path": skipped_path, "reason": reason}
                break
        if best_match:
            break

    return best_match


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
            latency_ms = round((time.time() - start_time) * 1000, 2)

            # ── Transparency: check if user asked about a filtered file ──────
            skip_manifest = _load_skip_manifest(repo_id)
            filtered_match = _detect_filtered_file(question, skip_manifest)

            if filtered_match:
                logger.info(
                    "no_results_filtered_file_detected",
                    repo_id=repo_id,
                    file=filtered_match["path"],
                    reason=filtered_match["reason"],
                )
                answer = (
                    f"This file was not indexed.\n\n"
                    f"The file `{filtered_match['path']}` exists in the repository "
                    f"but was intentionally skipped during indexing.\n\n"
                    f"Reason: {filtered_match['reason']}\n\n"
                    f"What you can do:\n"
                    f"- If this file contains important logic you want to query, "
                    f"re-index the repository and it will be included.\n"
                    f"- The current filter is designed to skip config files, "
                    f"lock files, and binary assets that don't contain queryable code logic."
                )
            else:
                answer = (
                    "I couldn't find any relevant code in this repository to answer "
                    "your question. The repository might not be indexed yet, or the "
                    "question might not relate to the indexed source code.\n\n"
                    "Tip: Try asking about a specific function, class, or file "
                    "that you know exists in the codebase."
                )

            return {
                "answer": answer,
                "citations": [],
                "confidence_score": 0.0,
                "query": question,
                "repo_id": repo_id,
                "latency_ms": latency_ms,
                "filtered_file": filtered_match,
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
