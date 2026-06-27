"""
StackSense — Vector Store (app/vectordb/vector_store.py)

Manages the ChromaDB vector database:
  - Create/get collections per repository
  - Store chunk embeddings with context headers
  - Similarity search with optional metadata filtering
  - Delete collections on re-ingestion

Replaces: app/services/chromadb_service.py
"""

import hashlib
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Optional, Dict, Any

from app.config import get_settings
from app.utils.logger import get_logger
from app.vectordb.bm25_store import save_bm25_index, delete_bm25_index

logger = get_logger(__name__)
settings = get_settings()

# Singleton ChromaDB client
_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or initialize the ChromaDB client (singleton)."""
    global _client
    if _client is None:
        logger.info(
            "store_connecting",
            persist_dir=settings.chroma_persist_dir,
        )
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("store_connected", persist_dir=settings.chroma_persist_dir)
    return _client


def _safe_collection_name(repo_id: str) -> str:
    """Convert repo_id to a valid ChromaDB collection name."""
    name = repo_id.replace("/", "_").replace("-", "_").lower()
    if len(name) > 63:
        name = name[:63]
    if len(name) < 3:
        name = f"repo_{name}"
    return name


def get_or_create_collection(repo_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a repository."""
    client = get_chroma_client()
    collection_name = _safe_collection_name(repo_id)

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"repo_id": repo_id, "hnsw:space": "cosine"},
    )

    logger.info(
        "store_collection_ready",
        repo_id=repo_id,
        collection=collection_name,
        existing_vectors=collection.count(),
    )
    return collection


def store_chunks(
    repo_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
) -> int:
    """
    Store code chunks with their embeddings in ChromaDB.

    Each chunk gets a context header prepended to its document text so
    the embedding model knows which file and which type of code it is.

    Args:
        repo_id: Repository identifier.
        chunks: List of chunk dicts with content, file_path, etc.
        embeddings: Corresponding embedding vectors.

    Returns:
        Number of chunks stored.
    """
    collection = get_or_create_collection(repo_id)

    ids: List[str] = []
    documents: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for chunk in chunks:
        # Stable, unique ID based on content location — safe to re-ingest
        chunk_id = hashlib.md5(
            f"{repo_id}|{chunk['file_path']}|{chunk['start_line']}|{chunk['end_line']}"
            .encode()
        ).hexdigest()
        ids.append(chunk_id)

        # chunk["content"] already contains the context header from chunker.py:
        #   File: <path>
        #   Language: <lang>
        #   Function: <name>
        #
        #   <actual code>
        #
        # DO NOT add another header here — that causes a double-header which
        # confuses the embedding model and wastes token budget.
        documents.append(chunk["content"])

        metadatas.append({
            "file_path":  chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line":   chunk["end_line"],
            "language":   chunk["language"],
            "chunk_type": chunk.get("chunk_type", "generic"),
            "name":       chunk.get("name", ""),
        })

    # Insert in batches of 500 (ChromaDB limit)
    batch_size = 500
    total_batches = (len(ids) + batch_size - 1) // batch_size

    logger.info(
        "store_start",
        repo_id=repo_id,
        total_chunks=len(ids),
        batch_size=batch_size,
        total_batches=total_batches,
    )

    for b in range(total_batches):
        s = b * batch_size
        e = min(s + batch_size, len(ids))
        logger.info(
            "store_batch",
            batch=f"{b + 1}/{total_batches}",
            chunks=f"{s + 1}-{e}",
        )
        collection.add(
            ids=ids[s:e],
            documents=documents[s:e],
            embeddings=embeddings[s:e],
            metadatas=metadatas[s:e],
        )

    logger.info(
        "store_complete",
        repo_id=repo_id,
        stored=len(ids),
        total_in_collection=collection.count(),
    )
    
    # --- [NEW] Build and Save BM25 Index ---
    save_bm25_index(repo_id, ids, documents, metadatas)
    
    return len(ids)


def search_chunks(
    repo_id: str,
    query_embedding: List[float],
    top_k: int = 20,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Search for similar chunks in a repository's collection.

    Args:
        repo_id: Repository identifier.
        query_embedding: Query embedding vector.
        top_k: Number of results to return.
        where: Optional ChromaDB metadata filter dict.

    Returns:
        List of matching chunks with metadata and distance scores.
    """
    collection = get_or_create_collection(repo_id)

    if collection.count() == 0:
        logger.warning("store_empty_collection", repo_id=repo_id)
        return []

    query_args: Dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_args["where"] = where
        logger.info("store_search_with_filter", filter=str(where))

    logger.info(
        "store_search",
        repo_id=repo_id,
        top_k=top_k,
        collection_size=collection.count(),
    )

    results = collection.query(**query_args)

    chunks = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        relevance = round(1 - distance, 4)
        meta = results["metadatas"][0][i]
        chunks.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": meta,
            "distance": distance,
            "relevance_score": relevance,
        })

    # Log top-3 hits for transparency
    for rank, c in enumerate(chunks[:3], 1):
        logger.info(
            "store_search_hit",
            rank=rank,
            file=c["metadata"].get("file_path", "?"),
            name=c["metadata"].get("name", ""),
            relevance=c["relevance_score"],
        )

    return chunks


def delete_collection(repo_id: str) -> bool:
    """Delete a repository's collection from ChromaDB (called before re-ingestion)."""
    client = get_chroma_client()
    collection_name = _safe_collection_name(repo_id)
    
    # Also delete the BM25 index
    delete_bm25_index(repo_id)
    
    try:
        client.delete_collection(name=collection_name)
        logger.info("store_collection_deleted", repo_id=repo_id)
        return True
    except Exception as e:
        logger.warning("store_collection_delete_failed", repo_id=repo_id, error=str(e))
        return False


def list_collections() -> List[Dict[str, Any]]:
    """List all indexed repository collections."""
    client = get_chroma_client()
    collection_names = client.list_collections()
    result = []
    for col_name in collection_names:
        collection = client.get_collection(col_name)
        metadata = collection.metadata or {}
        result.append({
            "name": col_name,
            "repo_id": metadata.get("repo_id", col_name),
            "count": collection.count(),
        })
    return result


def is_connected() -> bool:
    """Check if ChromaDB is accessible."""
    try:
        client = get_chroma_client()
        client.list_collections()
        return True
    except Exception:
        return False
