"""
StackSense — Ingestion Pipeline (app/ingestion/pipeline.py)

Orchestrates the full ingestion flow:
  Clone repo → Discover files → Chunk → Embed → Store in ChromaDB.

Replaces: app/core/ingestion.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from app.config import get_settings
from app.utils.logger import get_logger, set_run_log_file
from app.ingestion.file_filter import get_code_files
from app.ingestion.cloner import clone_repository, parse_repo_url, cleanup_repository
from app.chunking.chunker import chunk_file
from app.embeddings.embedder import embed_texts
from app.vectordb.vector_store import store_chunks, delete_collection
from app.services.s3_service import save_repo_metadata
from app.utils.metrics import (
    ingestion_duration_seconds,
    files_indexed_total,
    chunks_stored_total,
    repos_indexed,
)

logger = get_logger(__name__)
settings = get_settings()

# In-memory ingestion status tracker (use Redis in production)
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
    repo_path  = None   # track so finally can clean up even if clone fails

    # ── Step 1: Parse repo URL ────────────────────────────────────────
    repo_info = parse_repo_url(repo_url)
    repo_id = repo_info["repo_id"]

    logger.info(
        "ingestion_started",
        repo_id=repo_id,
        branch=branch or "default",
    )

    # Create a dedicated log file for this ingestion run
    run_log = set_run_log_file(repo_id)
    logger.info(
        "ingestion_run_log",
        repo_id=repo_id,
        log_file=str(run_log),
    )

    _ingestion_status[repo_id] = {
        "status": "cloning",
        "progress": 0,
        "message": "Cloning repository...",
    }

    try:
        # ── Step 2: Clone ─────────────────────────────────────────────────────
        repo_path = clone_repository(repo_url, branch)

        # ── Step 3: Discover files ────────────────────────────────────
        _ingestion_status[repo_id] = {
            "status": "discovering",
            "progress": 15,
            "message": "Discovering code files...",
        }
        # Build manifest path alongside ChromaDB data
        safe_id = repo_id.replace("/", "_")
        manifest_path = Path(settings.chroma_persist_dir) / f"skip_manifest_{safe_id}.json"
        code_files = get_code_files(
            repo_path,
            settings.max_files_per_repo,
            manifest_path=manifest_path,
        )

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

        # ── Step 4: Chunk all files ───────────────────────────────────
        _ingestion_status[repo_id] = {
            "status": "chunking",
            "progress": 30,
            "message": f"Chunking {len(code_files)} files...",
        }

        all_chunks: List[Dict[str, Any]] = []
        languages_seen: set = set()
        files_processed = 0

        logger.info(
            "chunk_phase_start",
            total_files=len(code_files),
        )

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

                if chunks:
                    # chunk_file now returns list of dicts: {document, metadata}
                    for chunk in chunks:
                        meta = chunk["metadata"]
                        all_chunks.append({
                            "content":    chunk["document"],  # includes context header
                            "file_path":  meta["file_path"],
                            "start_line": meta["start_line"],
                            "end_line":   meta["end_line"],
                            "language":   meta["language"],
                            "chunk_type": meta["chunk_type"],
                            "name":       meta["chunk_name"],
                        })

                    # Log per-file chunk summary
                    type_counts: Dict[str, int] = {}
                    for c in chunks:
                        ct = c["metadata"]["chunk_type"]
                        type_counts[ct] = type_counts.get(ct, 0) + 1
                    type_str = "  ".join(f"{t}:{n}" for t, n in type_counts.items())
                    logger.info(
                        "chunk_file_done",
                        file=file_info["relative_path"],
                        chunks=len(chunks),
                        types=type_str,
                        language=file_info["language"],
                    )

                languages_seen.add(file_info["language"])
                files_processed += 1

                # Progress update every 10 files
                if files_processed % 10 == 0:
                    pct = 30 + int((files_processed / len(code_files)) * 30)
                    _ingestion_status[repo_id] = {
                        "status": "chunking",
                        "progress": pct,
                        "message": f"Chunked {files_processed}/{len(code_files)} files → {len(all_chunks)} chunks so far",
                    }

            except Exception as e:
                logger.warning(
                    "chunk_file_error",
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
            "chunk_phase_complete",
            total_chunks=len(all_chunks),
            files_processed=files_processed,
        )

        # ── [NEW] Dump chunks to disk for inspection ──────────────────
        safe_id = repo_id.replace("/", "_")
        dump_dir = Path(settings.chroma_persist_dir) / "chunk_dumps" / safe_id
        dump_dir.mkdir(parents=True, exist_ok=True)
        dump_file_json = dump_dir / "chunks.json"
        dump_file_txt = dump_dir / "chunks.txt"

        with open(dump_file_json, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, indent=2)
            
        with open(dump_file_txt, "w", encoding="utf-8") as f:
            for i, chunk in enumerate(all_chunks, 1):
                f.write(f"=== CHUNK {i} | FILE: {chunk.get('file_path')} | LINES: {chunk.get('start_line')}-{chunk.get('end_line')} ===\n")
                f.write(chunk.get("content", ""))
                f.write("\n\n" + "="*80 + "\n\n")
            
        logger.info(
            "chunks_dumped",
            path=str(dump_dir),
            chunk_count=len(all_chunks),
        )

        # ── Step 5: Embed ─────────────────────────────────────────────
        _ingestion_status[repo_id] = {
            "status": "embedding",
            "progress": 60,
            "message": f"Embedding {len(all_chunks)} chunks...",
        }

        chunk_texts = [c["content"] for c in all_chunks]
        embeddings = embed_texts(chunk_texts)

        # ── Step 6: Store in ChromaDB ─────────────────────────────────
        _ingestion_status[repo_id] = {
            "status": "storing",
            "progress": 85,
            "message": f"Storing {len(all_chunks)} vectors in ChromaDB...",
        }

        delete_collection(repo_id)
        stored_count = store_chunks(repo_id, all_chunks, embeddings)

        # ── Metrics + Metadata ────────────────────────────────────────
        duration = time.time() - start_time
        ingestion_duration_seconds.observe(duration)
        files_indexed_total.inc(files_processed)
        chunks_stored_total.inc(stored_count)
        repos_indexed.inc()

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
            "message": (
                f"Successfully indexed {files_processed} files "
                f"into {stored_count} chunks"
            ),
        }

        logger.info("ingestion_complete", **result)

        # Write a JSON summary to the run log for easy parsing
        summary = {
            "type": "ingestion_summary",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **result,
        }
        logger.info("ingestion_summary_json", summary=json.dumps(summary, indent=2))
        return result

    except Exception as e:
        _ingestion_status[repo_id] = {
            "status": "error",
            "progress": 0,
            "message": str(e),
        }
        logger.error("ingestion_failed", repo_id=repo_id, error=str(e))
        raise

    finally:
        # Always delete the cloned repo from disk — whether ingestion
        # succeeded or failed. This prevents unbounded disk growth.
        if repo_path is not None:
            try:
                cleanup_repository(repo_path)
                logger.info("ingestion_cleanup_done", repo_id=repo_id, path=str(repo_path))
            except Exception as cleanup_err:
                logger.warning(
                    "ingestion_cleanup_failed",
                    repo_id=repo_id,
                    error=str(cleanup_err),
                )


def ingest_repository_background(
    repo_url: str,
    branch: str | None = None,
) -> None:
    """
    Fire-and-forget wrapper for ingest_repository().
    Called via FastAPI BackgroundTasks so the API can return 202 immediately.
    Errors are logged and captured in _ingestion_status — they do NOT propagate
    back to the HTTP layer (the connection is already closed).
    """
    try:
        ingest_repository(repo_url=repo_url, branch=branch)
    except Exception as e:
        # Status dict already updated inside ingest_repository's except block.
        # Log here for visibility in case the inner logger missed it.
        logger.error(
            "ingestion_background_task_failed",
            repo_url=repo_url,
            error=str(e),
        )
