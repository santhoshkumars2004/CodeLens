"""
StackSense — Embedder (app/embeddings/embedder.py)

Thin wrapper around EmbeddingService for use by the ingestion and query pipelines.
The actual model logic lives in app/services/embedding_service.py.
"""

from typing import List

from app.services.embedding_service import (
    EmbeddingService,
    embed_texts as _embed_texts,
    embed_query as _embed_query,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of code chunks.

    Args:
        texts: List of code/text strings to embed.

    Returns:
        List of embedding vectors.
    """
    return _embed_texts(texts)


def embed_query(query: str) -> List[float]:
    """
    Generate an embedding for a natural-language search query.

    Args:
        query: The user's search question.

    Returns:
        Embedding vector.
    """
    return _embed_query(query)


def get_embedding_model() -> EmbeddingService:
    """Return the singleton EmbeddingService instance."""
    return EmbeddingService()
