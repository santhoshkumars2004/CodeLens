"""
StackSense Embedding Service.

Wraps HuggingFace sentence-transformers to generate embeddings
for code chunks and queries. Runs entirely locally (free).
"""

from typing import List

from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Singleton model instance
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Get or initialize the embedding model (singleton)."""
    global _model
    if _model is None:
        logger.info("loading_embedding_model", model=settings.embedding_model)
        _model = SentenceTransformer(
            settings.embedding_model,
            local_files_only=True
        )
        logger.info("embedding_model_loaded", model=settings.embedding_model)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed.

    Returns:
        List of embedding vectors.
    """
    model = get_embedding_model()
    batch_size = settings.embedding_batch_size

    logger.debug("embedding_texts", count=len(texts), batch_size=batch_size)

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )

    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """
    Generate embedding for a single query string.

    Args:
        query: The search query text.

    Returns:
        Embedding vector.
    """
    model = get_embedding_model()
    embedding = model.encode(
        query,
        normalize_embeddings=True,
    )
    return embedding.tolist()
