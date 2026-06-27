"""
StackSense Retriever.

Performs vector similarity search on ChromaDB and optional
cross-encoder reranking for improved accuracy.
"""

import time
from typing import List, Dict, Any, Optional

from fastapi import HTTPException
from app.services.embedding_service import embed_query
from app.services.chromadb_service import search_chunks, is_connected
from app.utils.logger import get_logger
from app.utils.metrics import retrieval_latency_seconds, chunks_retrieved

logger = get_logger(__name__)


def retrieve(
    question: str,
    repo_id: str,
    top_k: int = 20,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant code chunks for a question.

    Args:
        question: User's natural language question.
        repo_id: Repository identifier.
        top_k: Number of chunks to retrieve.

    Returns:
        List of relevant chunks sorted by relevance score.
    """
    start_time = time.time()

    if not is_connected():
        logger.error("chromadb_unreachable")
        raise HTTPException(
            status_code=503,
            detail="ChromaDB is currently unreachable. Vector search is unavailable."
        )

    # Embed the question
    query_embedding = embed_query(question)

    # Search ChromaDB
    results = search_chunks(repo_id, query_embedding, top_k=top_k, where=where)

    duration = time.time() - start_time
    retrieval_latency_seconds.observe(duration)
    chunks_retrieved.observe(len(results))

    logger.info(
        "retrieval_complete",
        repo_id=repo_id,
        chunks_found=len(results),
        duration_seconds=round(duration, 3),
    )

    return results
