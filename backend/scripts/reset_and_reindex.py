"""
scripts/reset_and_reindex.py

Wipes all ChromaDB collections and re-indexes a GitHub repository from scratch.

Usage:
    python scripts/reset_and_reindex.py --repo-url https://github.com/santhoshkumars2004/Stacksense
    python scripts/reset_and_reindex.py --repo-url https://github.com/owner/repo --branch main
    python scripts/reset_and_reindex.py --nuke-only          # just clear DB, don't re-index

Run from the backend/ directory:
    cd backend
    python scripts/reset_and_reindex.py --repo-url https://github.com/santhoshkumars2004/Stacksense
"""

import argparse
import shutil
import sys
import time
from pathlib import Path

# ── Make sure app/ is importable when run from backend/ ───────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.ingestion.cloner import parse_repo_url, clone_repository
from app.ingestion.file_filter import (
    get_code_files,
    should_skip_directory,
    should_skip_file,
    SKIP_DIRECTORIES,
    MIN_FILE_SIZE_BYTES,
    MAX_FILE_SIZE_BYTES,
)
from app.chunking.chunker import chunk_file
from app.embeddings.embedder import embed_texts
from app.vectordb.vector_store import (
    get_chroma_client,
    store_chunks,
    delete_collection,
    _safe_collection_name,
)
from app.services.s3_service import save_repo_metadata

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger("reset_and_reindex")


# ─────────────────────────────────────────────────────────────────────
# Step 1: Nuke ChromaDB
# ─────────────────────────────────────────────────────────────────────

def nuke_chromadb() -> int:
    """
    Delete every collection in ChromaDB and confirm the DB is empty.

    Returns:
        Number of collections that were deleted.
    """
    print()
    print("=" * 60)
    print("  STEP 1 — CLEARING CHROMADB")
    print("=" * 60)

    client = get_chroma_client()
    collections = client.list_collections()

    if not collections:
        logger.info("chromadb_already_empty")
        print("  ChromaDB is already empty — nothing to delete.")
        return 0

    deleted = 0
    for col in collections:
        count = client.get_collection(col.name).count()
        client.delete_collection(col.name)
        logger.info("collection_deleted", name=col.name, vectors=count)
        print(f"  Deleted collection: {col.name}  ({count:,} vectors)")
        deleted += 1

    # Confirm
    remaining = client.list_collections()
    if remaining:
        print(f"  WARNING: {len(remaining)} collections still remain!")
    else:
        print(f"\n  ChromaDB cleared — {deleted} collection(s) deleted.")
        logger.info("chromadb_cleared", deleted=deleted)

    return deleted


def nuke_chromadb_files() -> None:
    """
    Also wipe the on-disk ChromaDB files for a truly clean slate.
    This is more thorough than just deleting via the client API.
    """
    chroma_path = Path(settings.chroma_persist_dir)
    if chroma_path.exists():
        shutil.rmtree(chroma_path)
        chroma_path.mkdir(parents=True, exist_ok=True)
        logger.info("chromadb_files_wiped", path=str(chroma_path))
        print(f"  On-disk data wiped: {chroma_path}")
    else:
        print(f"  ChromaDB directory not found at {chroma_path} — nothing to wipe.")


# ─────────────────────────────────────────────────────────────────────
# Step 2: Clone the repository
# ─────────────────────────────────────────────────────────────────────

def clone_repo(repo_url: str, branch: str | None) -> Path:
    print()
    print("=" * 60)
    print("  STEP 2 — CLONING REPOSITORY")
    print("=" * 60)

    repo_info = parse_repo_url(repo_url)
    logger.info("clone_start", repo_id=repo_info["repo_id"], branch=branch or "default")
    print(f"  Repo:   {repo_info['repo_id']}")
    print(f"  Branch: {branch or 'default'}")

    repo_path = clone_repository(repo_url, branch)
    print(f"  Cloned to: {repo_path}")
    return repo_path


# ─────────────────────────────────────────────────────────────────────
# Step 3: Discover files with verbose skip logging
# ─────────────────────────────────────────────────────────────────────

def discover_files(repo_path: Path) -> tuple[list, dict]:
    """
    Walk the repo with per-file skip logging.

    Returns:
        (code_files, skip_summary) where skip_summary maps reason → count
    """
    import os
    from collections import defaultdict

    print()
    print("=" * 60)
    print("  STEP 3 — DISCOVERING FILES")
    print("=" * 60)

    code_files = []
    skip_summary: dict = defaultdict(int)
    total_seen = 0

    for root, dirs, files in os.walk(repo_path):
        # Prune directories
        before = list(dirs)
        dirs[:] = [d for d in dirs if not should_skip_directory(d)]
        for d in set(before) - set(dirs):
            skip_summary[f"dir:{d}"] += 1

        for filename in files:
            total_seen += 1
            file_path = Path(root) / filename
            relative  = str(file_path.relative_to(repo_path))

            try:
                size = file_path.stat().st_size
            except OSError as exc:
                reason = f"cannot stat ({exc})"
                logger.debug(f"Skipping {relative} — reason: {reason}")
                skip_summary["cannot_stat"] += 1
                continue

            if should_skip_file(str(file_path), size):
                # Determine the specific reason for the summary
                p    = file_path
                name = p.name
                ext  = p.suffix.lower()

                from app.ingestion.file_filter import (
                    SKIP_FILENAMES, SKIP_EXTENSIONS, SUPPORTED_EXTENSIONS,
                    ALLOWED_NO_EXTENSION,
                )

                if name in SKIP_FILENAMES:
                    reason = f"filename:{name}"
                elif ext in SKIP_EXTENSIONS:
                    reason = f"extension:{ext}"
                elif ext not in SUPPORTED_EXTENSIONS and name.lower() not in ALLOWED_NO_EXTENSION:
                    reason = f"unsupported_ext:{ext}"
                elif size < MIN_FILE_SIZE_BYTES:
                    reason = "too_small"
                elif size > MAX_FILE_SIZE_BYTES:
                    reason = "too_large"
                else:
                    reason = "other"

                skip_summary[reason] += 1
                continue

            from app.ingestion.file_filter import detect_language
            language = detect_language(str(file_path))
            code_files.append({
                "path":          str(file_path),
                "relative_path": relative,
                "language":      language,
                "size_bytes":    size,
            })

    print(f"  Total files seen:    {total_seen:,}")
    print(f"  Files to index:      {len(code_files):,}")
    print(f"  Files skipped:       {total_seen - len(code_files):,}")
    print()
    print("  Skip reasons breakdown:")
    for reason, count in sorted(skip_summary.items(), key=lambda x: -x[1]):
        print(f"    {count:>5}  {reason}")

    # Verify local_model/ was excluded
    local_model_files = [f for f in code_files if "local_model" in f["relative_path"]]
    if local_model_files:
        print(f"\n  WARNING: {len(local_model_files)} files from local_model/ slipped through!")
        for f in local_model_files[:5]:
            print(f"    {f['relative_path']}")
    else:
        print("\n  local_model/ correctly excluded from indexing.")

    logger.info(
        "discover_complete",
        total_seen=total_seen,
        to_index=len(code_files),
        skipped=total_seen - len(code_files),
    )

    return code_files, dict(skip_summary)


# ─────────────────────────────────────────────────────────────────────
# Step 4: Chunk
# ─────────────────────────────────────────────────────────────────────

def chunk_all_files(code_files: list) -> list:
    print()
    print("=" * 60)
    print("  STEP 4 — CHUNKING FILES")
    print("=" * 60)

    all_chunks = []
    errors     = 0

    for i, file_info in enumerate(code_files):
        try:
            content = Path(file_info["path"]).read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue

            chunks = chunk_file(content, file_info["relative_path"], file_info["language"])

            for chunk in chunks:
                meta = chunk["metadata"]
                all_chunks.append({
                    "content":    chunk["document"],
                    "file_path":  meta["file_path"],
                    "start_line": meta["start_line"],
                    "end_line":   meta["end_line"],
                    "language":   meta["language"],
                    "chunk_type": meta["chunk_type"],
                    "name":       meta["chunk_name"],
                })

        except Exception as exc:
            logger.warning("chunk_error", file=file_info["relative_path"], error=str(exc))
            errors += 1

        # Progress every 20 files
        if (i + 1) % 20 == 0 or (i + 1) == len(code_files):
            pct = round((i + 1) / len(code_files) * 100)
            print(f"  [{pct:>3}%] {i+1}/{len(code_files)} files chunked → {len(all_chunks):,} chunks", end="\r")

    print()
    print(f"  Total chunks created: {len(all_chunks):,}  (errors: {errors})")
    logger.info("chunk_complete", total_chunks=len(all_chunks), errors=errors)
    return all_chunks


# ─────────────────────────────────────────────────────────────────────
# Step 5: Embed + Store
# ─────────────────────────────────────────────────────────────────────

def embed_and_store(repo_id: str, all_chunks: list) -> int:
    print()
    print("=" * 60)
    print("  STEP 5 — EMBEDDING CHUNKS")
    print("=" * 60)
    print(f"  Embedding {len(all_chunks):,} chunks (batch_size=32)...")
    print("  This may take a few minutes on first run (model download).")

    texts      = [c["content"] for c in all_chunks]
    embeddings = embed_texts(texts)

    print()
    print("=" * 60)
    print("  STEP 6 — STORING IN CHROMADB")
    print("=" * 60)

    stored = store_chunks(repo_id, all_chunks, embeddings)
    print(f"  Stored {stored:,} vectors in collection: {_safe_collection_name(repo_id)}")
    logger.info("store_complete", repo_id=repo_id, stored=stored)
    return stored


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset ChromaDB and re-index a GitHub repository.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/reset_and_reindex.py --repo-url https://github.com/santhoshkumars2004/Stacksense
  python scripts/reset_and_reindex.py --repo-url https://github.com/owner/repo --branch develop
  python scripts/reset_and_reindex.py --nuke-only
        """,
    )
    parser.add_argument("--repo-url",   type=str, help="GitHub repository URL to index")
    parser.add_argument("--branch",     type=str, default=None, help="Branch to clone (default: repo default)")
    parser.add_argument("--nuke-only",  action="store_true", help="Only clear ChromaDB, skip re-indexing")
    parser.add_argument("--keep-files", action="store_true", help="Don't wipe on-disk ChromaDB files (API-only delete)")
    args = parser.parse_args()

    if not args.nuke_only and not args.repo_url:
        parser.error("--repo-url is required unless --nuke-only is specified.")

    start_time = time.time()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            StackSense — Reset & Re-index                 ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # ── Step 1: Nuke ChromaDB ─────────────────────────────────────
    deleted = nuke_chromadb()
    if not args.keep_files:
        nuke_chromadb_files()

    if args.nuke_only:
        print()
        print(f"✅ Done — {deleted} collection(s) cleared. ChromaDB is empty.")
        return

    # ── Step 2: Clone ─────────────────────────────────────────────
    repo_info  = parse_repo_url(args.repo_url)
    repo_id    = repo_info["repo_id"]
    repo_path  = clone_repo(args.repo_url, args.branch)

    # ── Step 3: Discover files ────────────────────────────────────
    code_files, skip_summary = discover_files(repo_path)

    if not code_files:
        print("\n❌ No indexable files found. Check your file filter settings.")
        sys.exit(1)

    # ── Step 4: Chunk ─────────────────────────────────────────────
    all_chunks = chunk_all_files(code_files)

    if not all_chunks:
        print("\n❌ No chunks could be extracted. Check your chunker settings.")
        sys.exit(1)

    # ── Steps 5 & 6: Embed + Store ────────────────────────────────
    stored = embed_and_store(repo_id, all_chunks)

    # ── Save metadata ─────────────────────────────────────────────
    from collections import Counter
    lang_counts = Counter(f["language"] for f in code_files)
    metadata = {
        "repo_id":       repo_id,
        "repo_url":      args.repo_url,
        "files_indexed": len(code_files),
        "chunks_count":  stored,
        "languages":     dict(lang_counts.most_common()),
        "branch":        args.branch or "default",
    }
    try:
        save_repo_metadata(repo_id, metadata)
    except Exception as exc:
        logger.warning("metadata_save_failed", error=str(exc))

    # ── Final summary ─────────────────────────────────────────────
    duration   = round(time.time() - start_time, 1)
    total_seen = len(code_files) + sum(skip_summary.values())
    skipped    = sum(skip_summary.values())

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║                      SUMMARY                             ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  Repo:          {repo_id:<41}║")
    print(f"║  Files found:   {total_seen:<41,}║")
    print(f"║  Files indexed: {len(code_files):<41,}║")
    print(f"║  Files skipped: {skipped:<41,}║")
    print(f"║  Chunks stored: {stored:<41,}║")
    print(f"║  Duration:      {duration:<38.1f}s ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print(f"✅ Indexed {len(code_files):,} files, {stored:,} chunks stored, {skipped:,} files skipped")
    print()

    logger.info(
        "reindex_complete",
        repo_id=repo_id,
        files_indexed=len(code_files),
        chunks_stored=stored,
        files_skipped=skipped,
        duration_seconds=duration,
    )


if __name__ == "__main__":
    main()
