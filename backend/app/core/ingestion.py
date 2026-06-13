"""
StackSense Ingestion Pipeline.

Orchestrates the full ingestion flow:
Clone repo → Discover files → Parse & chunk → Embed → Store in ChromaDB.
"""

import time
from pathlib import Path
from typing import Dict, Any, List

from app.config import get_settings
from app.utils.logger import get_logger
from app.utils.file_filter import get_code_files
from app.utils.chunker import chunk_file, CodeChunk
from app.services.github_service import clone_repository, parse_repo_url
from app.services.embedding_service import embed_texts
from app.services.chromadb_service import store_chunks, delete_collection
from app.services.s3_service import save_repo_metadata
from app.utils.metrics import (
    ingestion_duration_seconds,
    files_indexed_total,
    chunks_stored_total,
    repos_indexed,
)

logger = get_logger(__name__)
settings = get_settings()

# In-memory store for ingestion status (could be Redis in prod)
_ingestion_status: Dict[str, Dict[str, Any]] = {}


def get_ingestion_status(repo_id: str) -> Dict[str, Any] | None:
    """Get the current ingestion status for a repo."""
    return _ingestion_status.get(repo_id)


def ingest_repository(
    repo_url: str,
    branch: str | None = None,
) -> Dict[str, Any]:
    """
    Full ingestion pipeline for a GitHub repository.

    Steps:
    1. Parse and validate the repo URL
    2. Clone the repository (shallow clone)
    3. Discover all code files
    4. Parse and chunk each file
    5. Generate embeddings for all chunks
    6. Store chunks + embeddings in ChromaDB

    Args:
        repo_url: GitHub repository URL.
        branch: Optional branch name.

    Returns:
        Dict with ingestion results and statistics.
    """
    start_time = time.time()

    # Step 1: Parse repo URL
    repo_info = parse_repo_url(repo_url)
    repo_id = repo_info["repo_id"]

    _ingestion_status[repo_id] = {
        "status": "cloning",
        "progress": 0,
        "message": "Cloning repository...",
    }

    try:
        # Step 2: Clone the repository
        logger.info("ingestion_started", repo_id=repo_id)
        repo_path = clone_repository(repo_url, branch)

        # Step 3: Discover code files
        _ingestion_status[repo_id] = {
            "status": "discovering",
            "progress": 20,
            "message": "Discovering code files...",
        }
        code_files = get_code_files(repo_path, settings.max_files_per_repo)
        logger.info("files_discovered", repo_id=repo_id, count=len(code_files))

        if not code_files:
            return {
                "repo_id": repo_id,
                "status": "error",
                "message": "No indexable code files found in repository",
                "files_indexed": 0,
                "chunks_created": 0,
                "languages": [],
                "duration_seconds": time.time() - start_time,
            }

        # Step 4: Parse and chunk all files
        _ingestion_status[repo_id] = {
            "status": "chunking",
            "progress": 40,
            "message": f"Parsing {len(code_files)} files...",
        }

        all_chunks: List[Dict[str, Any]] = []
        languages_seen = set()
        files_processed = 0

        for file_info in code_files:
            try:
                file_path = Path(file_info["path"])
                content = file_path.read_text(encoding="utf-8", errors="ignore")

                if not content.strip():
                    continue

                chunks = chunk_file(
                    content=content,
                    file_path=file_info["relative_path"],
                    language=file_info["language"],
                )

                for chunk in chunks:
                    all_chunks.append({
                        "content": chunk.content,
                        "file_path": chunk.file_path,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "language": chunk.language,
                        "chunk_type": chunk.chunk_type,
                        "name": chunk.name or "",
                    })

                languages_seen.add(file_info["language"])
                files_processed += 1

            except Exception as e:
                logger.warning(
                    "file_parse_error",
                    file=file_info["relative_path"],
                    error=str(e),
                )
                continue

        if not all_chunks:
            return {
                "repo_id": repo_id,
                "status": "error",
                "message": "No chunks could be extracted from code files",
                "files_indexed": files_processed,
                "chunks_created": 0,
                "languages": list(languages_seen),
                "duration_seconds": time.time() - start_time,
            }

        logger.info(
            "chunks_created",
            repo_id=repo_id,
            total_chunks=len(all_chunks),
            files=files_processed,
        )

        # Step 5: Generate embeddings
        _ingestion_status[repo_id] = {
            "status": "embedding",
            "progress": 60,
            "message": f"Embedding {len(all_chunks)} code chunks...",
        }

        chunk_texts = [c["content"] for c in all_chunks]
        embeddings = embed_texts(chunk_texts)

        logger.info("embeddings_generated", repo_id=repo_id, count=len(embeddings))

        # Step 6: Store in ChromaDB (delete old collection first)
        _ingestion_status[repo_id] = {
            "status": "storing",
            "progress": 80,
            "message": "Storing in vector database...",
        }

        delete_collection(repo_id)  # Clean slate
        stored_count = store_chunks(repo_id, all_chunks, embeddings)

        # Update metrics
        duration = time.time() - start_time
        ingestion_duration_seconds.observe(duration)
        files_indexed_total.inc(files_processed)
        chunks_stored_total.inc(stored_count)
        repos_indexed.inc()

        # Save metadata to S3 (optional)
        metadata = {
            "repo_id": repo_id,
            "repo_url": repo_url,
            "files_indexed": files_processed,
            "chunks_count": stored_count,
            "languages": list(languages_seen),
            "branch": branch or "default",
        }
        save_repo_metadata(repo_id, metadata)

        _ingestion_status[repo_id] = {
            "status": "completed",
            "progress": 100,
            "message": "Repository indexed successfully!",
        }

        result = {
            "repo_id": repo_id,
            "status": "completed",
            "files_indexed": files_processed,
            "chunks_created": stored_count,
            "languages": sorted(languages_seen),
            "duration_seconds": round(duration, 2),
            "message": f"Successfully indexed {files_processed} files "
                       f"into {stored_count} chunks",
        }

        logger.info("ingestion_completed", **result)
        return result

    except Exception as e:
        _ingestion_status[repo_id] = {
            "status": "error",
            "progress": 0,
            "message": str(e),
        }
        logger.error("ingestion_failed", repo_id=repo_id, error=str(e))
        raise
