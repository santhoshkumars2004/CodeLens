"""
CodeLens — Retriever (app/retrieval/retriever.py)

Embeds a query and performs similarity search against ChromaDB.
Replaces: app/core/retriever.py
"""

import time
from typing import List, Dict, Any, Optional

from app.embeddings.embedder import embed_query
from app.vectordb.vector_store import search_chunks
from app.vectordb.bm25_store import search_bm25
from app.query.rewriter import rewrite_query
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
    Retrieve relevant code chunks for a natural language question.

    Args:
        question: User's natural language question.
        repo_id: Repository identifier.
        top_k: Number of chunks to retrieve from vector DB.
        where: Optional ChromaDB metadata filter.

    Returns:
        List of relevant chunks sorted by relevance score.
    """
    start_time = time.time()

    logger.info(
        "retrieve_start",
        repo_id=repo_id,
        question=question[:100],
        top_k=top_k,
    )

    # 0. Rewrite query for better code-search coverage
    search_query = rewrite_query(question)

    # 1. Semantic Search (Dense)
    query_embedding = embed_query(search_query)
    dense_results = search_chunks(repo_id, query_embedding, top_k=top_k, where=where)
    
    # 2. Lexical Search (Sparse / BM25) — use rewritten query for keyword matching too
    sparse_results = search_bm25(repo_id, search_query, top_k=top_k)
    
    # 3. Reciprocal Rank Fusion (RRF)
    # Combine the two sets of results. RRF Score = 1 / (k + rank)
    # We use a standard k=60
    rrf_k = 60
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict[str, Any]] = {}
    
    for rank, chunk in enumerate(dense_results):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
        chunk_map[cid] = chunk
        
    for rank, chunk in enumerate(sparse_results):
        cid = chunk["id"]
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))
        # BM25 chunk format is slightly different, ensure relevance_score exists
        if cid not in chunk_map:
            # If it's only found in BM25, give it a base relevance score so reranker doesn't break
            # In a real system we'd normalize BM25 score, but RRF is doing the real ranking here
            chunk["relevance_score"] = 0.5 
            chunk_map[cid] = chunk
            
    # Sort combined results by RRF score descending
    fused_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    results = [chunk_map[cid] for cid in fused_ids[:top_k]]
    
    # Optional: Log the fact that we fused them
    logger.info("hybrid_search_fusion", dense_count=len(dense_results), sparse_count=len(sparse_results), fused_count=len(results))

    duration = round(time.time() - start_time, 3)
    retrieval_latency_seconds.observe(duration)
    chunks_retrieved.observe(len(results))

    if results:
        top = results[0]
        logger.info(
            "retrieve_complete",
            chunks_found=len(results),
            top_file=top["metadata"].get("file_path", "?"),
            top_relevance=top["relevance_score"],
            duration_seconds=duration,
        )
    else:
        logger.warning("retrieve_no_results", repo_id=repo_id, duration_seconds=duration)

    return results
