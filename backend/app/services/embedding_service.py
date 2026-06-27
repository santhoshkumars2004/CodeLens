"""
StackSense Embedding Service (app/services/embedding_service.py)

Wraps HuggingFace sentence-transformers to generate dense vector
embeddings for code chunks and natural-language queries.

Model: jinaai/jina-embeddings-v2-base-code
  - Free, runs 100% locally via sentence-transformers
  - Trained on code + natural-language pairs (GitHub + StackOverflow)
  - Understands import statements, function names, and code semantics
  - Embedding dimension: 768
  - First run downloads ~350 MB from HuggingFace (cached afterwards)

Usage:
    svc = EmbeddingService()
    vectors = svc.embed(["def authenticate_user(username, password):"])
    query_vec = svc.embed_query("how does authentication work?")
"""

import math
import time
from typing import List

from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Constants ─────────────────────────────────────────────────────────
MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"
BATCH_SIZE = 32     # Memory-efficient batch size for local inference


class EmbeddingService:
    """
    Code-aware embedding service using Jina AI's code embedding model.

    The model is loaded once and reused across all calls (singleton pattern).
    On the very first call it will download the model weights (~350 MB)
    from HuggingFace Hub — this takes 2–3 minutes on a typical connection.
    Subsequent startups load from the local cache in seconds.
    """

    _instance: "EmbeddingService | None" = None
    _model: SentenceTransformer | None = None

    def __new__(cls) -> "EmbeddingService":
        """Singleton — only one model is ever loaded into memory."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self) -> SentenceTransformer:
        """
        Load the embedding model if not already loaded.

        Logs a clear message on first run so the user knows a download
        may be happening.
        """
        if self._model is not None:
            return self._model

        model_name = getattr(settings, "embedding_model", MODEL_NAME)

        logger.info(
            "embed_model_loading",
            model=model_name,
        )
        logger.info(
            "Loading code embedding model — first run may take 2-3 minutes to download...",
        )

        start = time.time()
        self._model = SentenceTransformer(model_name)
        duration = round(time.time() - start, 1)

        try:
            dim = self._model.get_embedding_dimension()
        except AttributeError:
            dim = self._model.get_sentence_embedding_dimension()
        logger.info(
            "embed_model_ready",
            model=model_name,
            dimensions=dim,
            load_time_seconds=duration,
        )

        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of code or text strings.

        Processes in batches of 32 to keep memory usage manageable.
        All vectors are L2-normalized (unit length) for cosine similarity.

        Args:
            texts: List of code snippets or text strings to embed.

        Returns:
            List of embedding vectors (each a list of 768 floats).
        """
        if not texts:
            return []

        model = self._load_model()
        total = len(texts)
        total_batches = math.ceil(total / BATCH_SIZE)

        logger.info(
            "embed_start",
            total_chunks=total,
            batch_size=BATCH_SIZE,
            total_batches=total_batches,
        )

        start = time.time()

        embeddings = model.encode(
            texts,
            batch_size=BATCH_SIZE,
            show_progress_bar=True,      # Shows tqdm bar during long ingestion runs
            normalize_embeddings=True,   # L2-normalize → cosine similarity = dot product
            convert_to_numpy=True,
        )

        duration = round(time.time() - start, 2)
        logger.info(
            "embed_complete",
            total_embeddings=len(embeddings),
            dimensions=len(embeddings[0]) if len(embeddings) > 0 else 0,
            duration_seconds=duration,
            chunks_per_second=round(total / duration, 1) if duration > 0 else 0,
        )

        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """
        Generate a single embedding for a natural-language search query.

        Uses the same model and normalization as embed() so the query vector
        is directly comparable to stored chunk vectors via cosine similarity.

        Args:
            query: Natural-language question or search term.

        Returns:
            Embedding vector (768 floats, L2-normalized).
        """
        model = self._load_model()
        logger.info("embed_query", query_preview=query[:80])

        embedding = model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embedding.tolist()


# ── Module-level helpers (keeps backward compatibility with old callers) ──

_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return the singleton EmbeddingService instance."""
    global _service
    if _service is None:
        _service = EmbeddingService()
    return _service


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Convenience wrapper — embed a list of texts."""
    return get_embedding_service().embed(texts)


def embed_query(query: str) -> List[float]:
    """Convenience wrapper — embed a single query string."""
    return get_embedding_service().embed_query(query)


# ── Quick self-test ───────────────────────────────────────────────────

if __name__ == "__main__":
    svc = EmbeddingService()

    test_code = ["def authenticate_user(username, password):"]
    result = svc.embed(test_code)

    print(f"\nEmbedding dimension: {len(result[0])}")
    print(f"First 5 values: {[round(v, 4) for v in result[0][:5]]}")
    print("Embedding service working correctly!")

    # Also test query embedding
    query_vec = svc.embed_query("how does user authentication work?")
    print(f"\nQuery embedding dimension: {len(query_vec)}")
    print("Query embedding working correctly!")
