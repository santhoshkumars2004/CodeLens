"""
CodeLens — Vector Store (app/vectordb/vector_store.py)

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

    seen_ids: Dict[str, int] = {}
    for i, chunk in enumerate(chunks):
        file_path = chunk.get("file_path", "")
        start_line = chunk.get("start_line", 0)
        end_line = chunk.get("end_line", 0)
        name = chunk.get("name", "")
        content = chunk.get("content", "")
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]

        # Base stable ID on repo, file, name, lines, and content hash
        base_id = hashlib.md5(
            f"{repo_id}|{file_path}|{name}|{start_line}|{end_line}|{content_hash}"
            .encode()
        ).hexdigest()

        # Guarantee absolute uniqueness in the batch even if location & content match
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            chunk_id = hashlib.md5(f"{base_id}_{seen_ids[base_id]}_{i}".encode()).hexdigest()
        else:
            seen_ids[base_id] = 0
            chunk_id = base_id

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
        collection.upsert(
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
    """List all indexed repository collections.

    Handles both old ChromaDB (<0.4) that returned string names and
    new ChromaDB (>=0.4) that returns Collection objects directly.
    """
    client = get_chroma_client()
    raw_list = client.list_collections()
    result = []
    for item in raw_list:
        try:
            # New ChromaDB (>=0.4, <0.6): item IS a Collection object
            # In v0.6, it's a CollectionName object that throws an exception if .name is accessed.
            if type(item).__name__ == "Collection":
                col = item
                col_name = col.name
                metadata = col.metadata or {}
            else:
                # Old ChromaDB or v0.6+: item is a string or CollectionName
                col_name = str(item)
                col = client.get_collection(col_name)
                metadata = col.metadata or {}

            repo_id = metadata.get("repo_id", col_name)
            count = col.count()
            result.append({
                "name": col_name,
                "repo_id": repo_id,
                "count": count,
            })
            logger.debug(
                "list_collections_item",
                col_name=col_name,
                repo_id=repo_id,
                count=count,
            )
        except Exception as e:
            logger.warning("list_collections_item_failed", item=str(item), error=str(e))
            continue
    return result


def is_connected() -> bool:
    """Check if ChromaDB is accessible."""
    try:
        client = get_chroma_client()
        client.list_collections()
        return True
    except Exception:
        return False


def get_repo_files(repo_id: str) -> Dict[str, Any]:
    """
    Get all unique indexed files for a repository, organized by language.

    Fetches all chunk metadata from ChromaDB, deduplicates by file_path,
    and returns a structured list grouped by language for the file explorer UI.

    Returns:
        Dict with:
          - files: list of {file_path, language, chunk_count} dicts
          - total_files: int
          - languages: list of distinct languages
          - total_chunks: int
    """
    collection = get_or_create_collection(repo_id)
    total_chunks = collection.count()

    if total_chunks == 0:
        return {"files": [], "total_files": 0, "languages": [], "total_chunks": 0}

    # Fetch ALL metadata (no embeddings needed, just metadata)
    all_data = collection.get(include=["metadatas"])
    metadatas = all_data.get("metadatas", [])

    # Deduplicate by file_path, count chunks per file
    file_map: Dict[str, Dict[str, Any]] = {}
    for meta in metadatas:
        if not meta:
            continue
        fp = meta.get("file_path", "")
        if not fp:
            continue
        if fp not in file_map:
            file_map[fp] = {
                "file_path": fp,
                "language": meta.get("language", "unknown"),
                "chunk_count": 0,
            }
        file_map[fp]["chunk_count"] += 1

    files = sorted(file_map.values(), key=lambda x: x["file_path"])
    languages = sorted({f["language"] for f in files})

    logger.info(
        "store_files_listed",
        repo_id=repo_id,
        total_files=len(files),
        languages=languages,
    )

    return {
        "files": files,
        "total_files": len(files),
        "languages": languages,
        "total_chunks": total_chunks,
    }

