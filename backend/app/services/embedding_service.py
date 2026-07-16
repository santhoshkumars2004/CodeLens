"""
CodeLens Embedding Service (app/services/embedding_service.py)

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
from typing import List, Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Constants ─────────────────────────────────────────────────────────
# Override by setting EMBEDDING_MODEL env var:
#   - Local (high quality): jinaai/jina-embeddings-v2-base-code (~800MB RAM, uses PyTorch)
#   - Railway free tier:    fastembed/BAAI/bge-small-en-v1.5    (~100MB RAM, no PyTorch)
DEFAULT_MODEL = "fastembed/BAAI/bge-small-en-v1.5"
BATCH_SIZE = 16


class EmbeddingService:
    _instance: "EmbeddingService | None" = None
    _model: Any = None
    _is_fastembed: bool = False

    def __new__(cls) -> "EmbeddingService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        model_name = getattr(settings, "embedding_model", None) or DEFAULT_MODEL
        
        logger.info("embed_model_loading", model=model_name)
        start = time.time()

        if model_name.startswith("fastembed/"):
            # Use ultra-lightweight fastembed (ONNX, No PyTorch)
            self._is_fastembed = True
            real_name = model_name.replace("fastembed/", "")
            from fastembed import TextEmbedding
            self._model = TextEmbedding(real_name)
            dim = 384 # BGE small is 384, adjust if needed
        else:
            # Use SentenceTransformers (Requires PyTorch, ~800MB+ RAM)
            self._is_fastembed = False
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(model_name)
            try:
                dim = self._model.get_embedding_dimension()
            except AttributeError:
                dim = self._model.get_sentence_embedding_dimension()

        duration = round(time.time() - start, 1)
        logger.info(
            "embed_model_ready",
            model=model_name,
            dimensions=dim,
            load_time_seconds=duration,
            is_fastembed=self._is_fastembed
        )

        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        model = self._load_model()
        start = time.time()

        if self._is_fastembed:
            # fastembed returns a generator of numpy arrays
            import numpy as np
            embeddings_gen = model.embed(texts, batch_size=BATCH_SIZE)
            embeddings = [emb.tolist() for emb in embeddings_gen]
            
            # fastembed already normalizes vectors
        else:
            embeddings_arr = model.encode(
                texts,
                batch_size=BATCH_SIZE,
                show_progress_bar=False,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            embeddings = embeddings_arr.tolist()

        duration = round(time.time() - start, 2)
        logger.info("embed_complete", total=len(texts), duration_seconds=duration)
        return embeddings

    def embed_query(self, query: str) -> List[float]:
        model = self._load_model()
        if self._is_fastembed:
            # fastembed query takes string or list
            embeddings_gen = model.query_embed(query)
            return next(embeddings_gen).tolist()
        else:
            embedding = model.encode(
                query,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            return embedding.tolist()


# ── Module-level helpers ──

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
