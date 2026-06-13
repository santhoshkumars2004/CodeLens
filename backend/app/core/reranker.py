"""
StackSense Reranker.

Uses a cross-encoder model to rerank retrieved chunks
for improved relevance accuracy.
"""

from typing import List, Dict, Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

_reranker = None


def get_reranker():
    """Get or initialize the cross-encoder reranker (singleton)."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder
        import os
        
        # We manually downloaded the model via curl into local_model to avoid HF cache issues
        local_dir = "/Users/santsiva/Desktop/Project/Stacksense/backend/local_model"
        
        logger.info("loading_reranker", model="local_model")
        if os.path.exists(local_dir):
            _reranker = CrossEncoder(local_dir, local_files_only=True)
        else:
            _reranker = CrossEncoder(settings.reranker_model)
            
        logger.info("reranker_loaded")
    return _reranker


import math

def sigmoid(x: float) -> float:
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
    Rerank chunks using cross-encoder for better relevance.

    Args:
        question: User's question.
        chunks: Retrieved chunks from vector search.
        top_k: Number of top results to return.

    Returns:
        Reranked list of chunks (top_k best).
    """
    if not chunks:
        return []

    reranker = get_reranker()

    # Create query-document pairs for cross-encoder
    pairs = [(question, chunk["content"]) for chunk in chunks]

    # Score all pairs
    scores = reranker.predict(pairs)

    # Attach scores and sort using sigmoid to get probabilities between 0 and 1
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = sigmoid(float(score))

    reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)

    logger.info(
        "reranking_complete",
        input_chunks=len(chunks),
        output_chunks=min(top_k, len(reranked)),
    )

    return reranked[:top_k]
