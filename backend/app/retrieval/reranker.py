"""
CodeLens — Reranker (app/retrieval/reranker.py)

Uses a cross-encoder model to score and re-rank the top chunks
retrieved from vector search for improved relevance.

Replaces: app/core/reranker.py
"""

import math
import os
from typing import List, Dict, Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_reranker = None
_reranker_available: bool | None = None


def get_reranker():
    """Get or initialize the cross-encoder reranker model (singleton).
    
    Returns None if sentence-transformers is not installed (e.g. Railway free tier).
    In that case rerank_chunks() will skip reranking and return chunks as-is.
    """
    global _reranker, _reranker_available
    if _reranker_available is False:
        return None
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info("rerank_model_loading", source="huggingface", model=settings.reranker_model)
            _reranker = CrossEncoder(settings.reranker_model)
            _reranker_available = True
            logger.info("rerank_model_ready")
        except ImportError:
            _reranker_available = False
            logger.warning("rerank_model_skipped", reason="sentence-transformers not installed (production mode)")
            return None
    return _reranker


def _sigmoid(x: float) -> float:
    """Convert raw cross-encoder logit to [0, 1] probability."""
    try:
        return 1.0 / (1.0 + math.exp(-x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def rerank_chunks(
    question: str,
    chunks: List[Dict[str, Any]],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Rerank retrieved chunks using a cross-encoder for precision relevance scoring.

    Args:
        question: User's question.
        chunks: Retrieved chunks from vector search.
        top_k: Number of top results to return after reranking.

    Returns:
        Reranked list of the top_k most relevant chunks.
    """
    if not chunks:
        return []

    reranker = get_reranker()
    
    # If reranker is unavailable (production/no sentence-transformers), skip reranking
    if reranker is None:
        logger.info("rerank_skipped_unavailable", returning=min(top_k, len(chunks)))
        return chunks[:top_k]

    logger.info(
        "rerank_start",
        input_chunks=len(chunks),
        top_k=top_k,
        question=question[:80],
    )

    pairs = [(question, chunk["content"]) for chunk in chunks]
    raw_scores = reranker.predict(pairs)

    for chunk, score in zip(chunks, raw_scores):
        chunk["rerank_score"] = round(_sigmoid(float(score)), 4)

    reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
    top = reranked[:top_k]

    # Log per-chunk scores so you can see exactly what made the cut
    logger.info(
        "rerank_scores",
        total_scored=len(reranked),
        kept=len(top),
    )
    for rank, chunk in enumerate(top, 1):
        meta = chunk.get("metadata", {})
        logger.info(
            "rerank_result",
            rank=rank,
            score=chunk["rerank_score"],
            file=meta.get("file_path", "?"),
            name=meta.get("name", ""),
            lines=f"{meta.get('start_line', '?')}-{meta.get('end_line', '?')}",
        )

    return top
