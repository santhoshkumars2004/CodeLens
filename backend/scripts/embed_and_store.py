"""
scripts/embed_and_store.py

Skip cloning — use the already-cloned repo at \tmp\stacksense_repos\
to embed and store with the correct BGE model.

Run from backend/:
    python scripts/embed_and_store.py
"""

import sys
from pathlib import Path
from collections import Counter

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.ingestion.file_filter import get_code_files
from app.chunking.chunker import chunk_file
from app.embeddings.embedder import embed_texts
from app.vectordb.vector_store import get_chroma_client, store_chunks, _safe_collection_name

settings = get_settings()
setup_logging(settings.log_level)
logger = get_logger("embed_and_store")

REPO_ID   = "santhoshkumars2004/Stacksense"
REPO_PATH = Path(r"\tmp\stacksense_repos\santhoshkumars2004\Stacksense")


def main():
    print()
    print("=" * 62)
    print("  StackSense — Embed & Store (skip clone)")
    print("=" * 62)

    if not REPO_PATH.exists():
        print(f"❌ Repo not found at {REPO_PATH}")
        print("   Run: python scripts/reset_and_reindex.py --repo-url ...")
        sys.exit(1)

    # ── 1. Wipe existing collection ───────────────────────────────
    client = get_chroma_client()
    col_name = _safe_collection_name(REPO_ID)
    try:
        client.delete_collection(col_name)
        print(f"  Deleted old collection: {col_name}")
    except Exception:
        print(f"  No existing collection to delete.")

    # ── 2. Discover files ─────────────────────────────────────────
    print(f"\n  Walking: {REPO_PATH}")
    code_files = get_code_files(REPO_PATH)
    print(f"  Files to index: {len(code_files)}")

    lang_counts = Counter(f["language"] for f in code_files)
    for lang, n in sorted(lang_counts.items(), key=lambda x: -x[1]):
        print(f"    {lang}: {n}")

    # Verify local_model excluded
    bad = [f for f in code_files if "local_model" in f["relative_path"]]
    if bad:
        print(f"\n  ❌ WARNING: {len(bad)} local_model files got through!")
        for f in bad[:3]:
            print(f"     {f['relative_path']}")
    else:
        print("\n  ✅ local_model/ correctly excluded")

    # ── 3. Chunk ──────────────────────────────────────────────────
    print("\n  Chunking files...")
    all_chunks = []
    for file_info in code_files:
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

    print(f"  Total chunks: {len(all_chunks)}")

    # ── 4. Embed ──────────────────────────────────────────────────
    print(f"\n  Embedding {len(all_chunks)} chunks with BGE-base-en-v1.5...")
    print("  (model is cached — should take ~10-20 seconds)")
    texts      = [c["content"] for c in all_chunks]
    embeddings = embed_texts(texts)
    print(f"  Embedding dims: {len(embeddings[0])}")

    # ── 5. Store ──────────────────────────────────────────────────
    print(f"\n  Storing in ChromaDB collection: {col_name}")
    stored = store_chunks(REPO_ID, all_chunks, embeddings)
    print(f"  Stored: {stored} vectors")

    print()
    print(f"✅ Done! {len(code_files)} files indexed, {stored} chunks stored.")
    print(f"   Run: python scripts/verify_rag.py")


if __name__ == "__main__":
    main()
