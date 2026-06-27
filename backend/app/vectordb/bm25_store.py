"""
CodeLens — BM25 Store (app/vectordb/bm25_store.py)

Manages BM25 lexical search indexes. Since rank_bm25 is completely
in-memory, we serialize the index alongside chunk metadata to disk
so we can load it quickly during retrieval.
"""

import os
import re
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

from rank_bm25 import BM25Okapi
from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

def _get_bm25_path(repo_id: str) -> Path:
    """Get the file path for a repository's BM25 index."""
    safe_id = repo_id.replace("/", "_").replace("-", "_").lower()
    base_dir = Path(settings.chroma_persist_dir) / "bm25"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{safe_id}.pkl"


def tokenize(text: str) -> List[str]:
    """Tokenizer for BM25. Extracts alphanumeric words, converting to lowercase."""
    # This splits on any non-alphanumeric character (including underscores if we didn't include them, 
    # but we want to keep underscores for variable names).
    return [w.lower() for w in re.findall(r'[a-zA-Z0-9_]+', text)]


def save_bm25_index(
    repo_id: str, 
    ids: List[str], 
    documents: List[str], 
    metadatas: List[Dict[str, Any]]
) -> bool:
    """
    Build and save a BM25 index to disk.
    
    Args:
        repo_id: Repository identifier
        ids: List of chunk IDs (same as ChromaDB)
        documents: List of chunk content texts
        metadatas: List of chunk metadata dicts
    """
    logger.info("bm25_build_start", repo_id=repo_id, chunk_count=len(ids))
    
    try:
        # Tokenize all documents
        tokenized_corpus = [tokenize(doc) for doc in documents]
        
        # Build BM25 index
        bm25 = BM25Okapi(tokenized_corpus)
        
        # Save to disk
        save_path = _get_bm25_path(repo_id)
        
        data_to_save = {
            "bm25_index": bm25,
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
        }
        
        with open(save_path, "wb") as f:
            pickle.dump(data_to_save, f)
            
        logger.info("bm25_build_complete", repo_id=repo_id, path=str(save_path))
        return True
        
    except Exception as e:
        logger.error("bm25_build_failed", repo_id=repo_id, error=str(e))
        return False


def load_bm25_index(repo_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a BM25 index from disk.
    
    Returns:
        Dict containing bm25_index, ids, documents, metadatas, or None if not found.
    """
    save_path = _get_bm25_path(repo_id)
    if not save_path.exists():
        logger.warning("bm25_index_not_found", repo_id=repo_id, path=str(save_path))
        return None
        
    try:
        with open(save_path, "rb") as f:
            data = pickle.load(f)
        return data
    except Exception as e:
        logger.error("bm25_load_failed", repo_id=repo_id, error=str(e))
        return None


def search_bm25(repo_id: str, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
    """
    Search the BM25 index for a query.
    
    Returns:
        List of dicts formatted similarly to ChromaDB search results.
    """
    data = load_bm25_index(repo_id)
    if not data:
        return []
        
    bm25: BM25Okapi = data["bm25_index"]
    ids = data["ids"]
    documents = data["documents"]
    metadatas = data["metadatas"]
    
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    
    # Get top_k indices sorted by score descending
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        score = scores[idx]
        if score > 0:  # Only return chunks that actually match some keywords
            results.append({
                "id": ids[idx],
                "content": documents[idx],
                "metadata": metadatas[idx],
                "bm25_score": float(score),
            })
            
    return results


def delete_bm25_index(repo_id: str) -> bool:
    """Delete the BM25 index file."""
    save_path = _get_bm25_path(repo_id)
    try:
        if save_path.exists():
            save_path.unlink()
            logger.info("bm25_index_deleted", repo_id=repo_id)
        return True
    except Exception as e:
        logger.error("bm25_index_delete_failed", repo_id=repo_id, error=str(e))
        return False
