"""
StackSense ChromaDB Service.

Manages vector storage using ChromaDB — a free, local vector database.
Handles creating collections, storing chunks, and similarity search.
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Optional, Dict, Any

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Singleton ChromaDB client
_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or initialize the ChromaDB client (singleton)."""
    global _client
    if _client is None:
        logger.info(
            "connecting_chromadb",
            persist_dir=settings.chroma_persist_dir,
        )
        _client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("chromadb_connected")
    return _client


def get_or_create_collection(repo_id: str) -> chromadb.Collection:
    """
    Get or create a ChromaDB collection for a repository.
    Collection names use underscores (ChromaDB restriction).
    """
    client = get_chroma_client()
    collection_name = repo_id.replace("/", "_").replace("-", "_").lower()

    # ChromaDB collection names must be 3-63 chars
    if len(collection_name) > 63:
        collection_name = collection_name[:63]
    if len(collection_name) < 3:
        collection_name = f"repo_{collection_name}"

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"repo_id": repo_id, "hnsw:space": "cosine"},
    )

    logger.info(
        "collection_ready",
        repo_id=repo_id,
        collection=collection_name,
        count=collection.count(),
    )
    return collection


def store_chunks(
    repo_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
) -> int:
    """
    Store code chunks with their embeddings in ChromaDB.

    Args:
        repo_id: Repository identifier.
        chunks: List of chunk dicts with content, file_path, etc.
        embeddings: Corresponding embedding vectors.

    Returns:
        Number of chunks stored.
    """
    collection = get_or_create_collection(repo_id)

    # Prepare data for batch insertion
    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{repo_id}_{i}_{chunk.get('start_line', 0)}"
        ids.append(chunk_id)
        
        # Prepend context header for better retrieval accuracy
        chunk_type = chunk.get("chunk_type", "generic")
        name_str = chunk.get("name") or "module-level"
        header = f"File: {chunk['file_path']}\nType: {chunk_type}\nName: {name_str}\n\n"
        
        documents.append(header + chunk["content"])
        metadatas.append({
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "language": chunk["language"],
            "chunk_type": chunk.get("chunk_type", "generic"),
            "name": chunk.get("name", ""),
        })

    # ChromaDB has a batch limit, insert in batches of 500
    batch_size = 500
    for start in range(0, len(ids), batch_size):
        end = min(start + batch_size, len(ids))
        collection.add(
            ids=ids[start:end],
            documents=documents[start:end],
            embeddings=embeddings[start:end],
            metadatas=metadatas[start:end],
        )

    logger.info(
        "chunks_stored",
        repo_id=repo_id,
        count=len(ids),
        total_in_collection=collection.count(),
    )
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

    Returns:
        List of matching chunks with metadata and distances.
    """
    collection = get_or_create_collection(repo_id)

    if collection.count() == 0:
        logger.warning("empty_collection", repo_id=repo_id)
        return []

    query_args = {
        "query_embeddings": [query_embedding],
        "n_results": min(top_k, collection.count()),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_args["where"] = where

    results = collection.query(**query_args)

    chunks = []
    for i in range(len(results["ids"][0])):
        chunks.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
            "relevance_score": 1 - results["distances"][0][i],
        })

    return chunks


def delete_collection(repo_id: str) -> bool:
    """Delete a repository's collection from ChromaDB."""
    client = get_chroma_client()
    collection_name = repo_id.replace("/", "_").replace("-", "_").lower()
    if len(collection_name) > 63:
        collection_name = collection_name[:63]
    if len(collection_name) < 3:
        collection_name = f"repo_{collection_name}"

    try:
        client.delete_collection(name=collection_name)
        logger.info("collection_deleted", repo_id=repo_id)
        return True
    except Exception as e:
        logger.error("collection_delete_failed", repo_id=repo_id, error=str(e))
        return False


def list_collections() -> List[Dict[str, Any]]:
    """List all indexed repository collections."""
    client = get_chroma_client()
    collections = client.list_collections()

    result = []
    for col in collections:
        collection = client.get_collection(col.name)
        metadata = col.metadata or {}
        result.append({
            "name": col.name,
            "repo_id": metadata.get("repo_id", col.name),
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
