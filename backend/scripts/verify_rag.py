"""
scripts/verify_rag.py — RAG pipeline verification checks.

Run from backend/:
    python scripts/verify_rag.py
"""

import random
import sys
from pathlib import Path
from collections import Counter

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings
from app.utils.logger import setup_logging
from app.vectordb.vector_store import get_chroma_client, _safe_collection_name
from app.embeddings.embedder import embed_query

settings = get_settings()
setup_logging("WARNING")   # suppress noise during verification

SEP  = "=" * 62
SEP2 = "-" * 62


def get_collection():
    client = get_chroma_client()
    cols   = client.list_collections()
    if not cols:
        print("❌ No collections found — ChromaDB is empty. Run reset_and_reindex.py first.")
        sys.exit(1)
    # pick the largest collection (the most recently indexed repo)
    best = max(cols, key=lambda c: client.get_collection(c.name).count())
    return client.get_collection(best.name), best.name


# ─────────────────────────────────────────────────────────────────────
# CHECK 1: Total chunk count
# ─────────────────────────────────────────────────────────────────────

def check_chunk_count(col, col_name: str) -> int:
    total = col.count()
    print(SEP)
    print("CHECK 1 — Total chunks in ChromaDB")
    print(SEP)
    print(f"  Collection : {col_name}")
    print(f"  Total chunks stored : {total:,}")
    if total == 0:
        print("  ❌ FAIL — collection is empty!")
    else:
        print(f"  ✅ PASS — {total:,} vectors ready for retrieval")
    return total


# ─────────────────────────────────────────────────────────────────────
# CHECK 2: Sample 5 random chunks and validate
# ─────────────────────────────────────────────────────────────────────

def check_sample_chunks(col):
    print()
    print(SEP)
    print("CHECK 2 — Sample 5 random chunks (content + metadata validation)")
    print(SEP)

    total = col.count()
    result = col.get(
        limit=min(200, total),
        include=["documents", "metadatas"],
    )

    ids       = result["ids"]
    documents = result["documents"]
    metadatas = result["metadatas"]

    # pick 5 random indices
    sample_idx = random.sample(range(len(ids)), min(5, len(ids)))

    all_pass = True
    for rank, i in enumerate(sample_idx, 1):
        doc  = documents[i]
        meta = metadatas[i]
        doc_line0 = doc.splitlines()[0] if doc else ""

        passes = []
        fails  = []

        # Rule 1: document starts with "File:"
        if doc_line0.startswith("File:"):
            passes.append("header starts with 'File:'")
        else:
            fails.append(f"header wrong: {doc_line0!r}")

        # Rule 2: not from local_model/
        fp = meta.get("file_path", "")
        if "local_model" in fp:
            fails.append(f"from local_model/: {fp}")
        else:
            passes.append("not from local_model/")

        # Rule 3: not a .txt or .yml file
        if fp.endswith((".txt", ".yml", ".yaml")):
            fails.append(f"is .txt/.yml file: {fp}")
        else:
            passes.append("not .txt/.yml")

        # Rule 4: required metadata keys present
        required_keys = ["file_path", "start_line", "end_line", "language"]
        missing = [k for k in required_keys if k not in meta]
        if missing:
            fails.append(f"missing metadata: {missing}")
        else:
            passes.append("all metadata keys present")

        status = "✅" if not fails else "❌"
        if fails:
            all_pass = False

        print(f"\n  [{rank}] {status}  {fp}  (lines {meta.get('start_line','?')}-{meta.get('end_line','?')})")
        print(f"       language={meta.get('language','?')}  type={meta.get('chunk_type','?')}  name={meta.get('chunk_name','?')}")
        print(f"       doc[0]: {doc_line0}")
        for p in passes:
            print(f"         ✓ {p}")
        for f in fails:
            print(f"         ✗ {f}")

    print()
    if all_pass:
        print("  ✅ ALL SAMPLE CHECKS PASSED")
    else:
        print("  ❌ SOME SAMPLE CHECKS FAILED — see above")


# ─────────────────────────────────────────────────────────────────────
# CHECK 3: Test retrieval query
# ─────────────────────────────────────────────────────────────────────

def check_retrieval(col):
    print()
    print(SEP)
    print("CHECK 3 — Test retrieval: 'which file contains the embedding service'")
    print(SEP)

    query   = "which file contains the embedding service"
    q_vec   = embed_query(query)

    results = col.query(
        query_embeddings=[q_vec],
        n_results=min(5, col.count()),
        include=["documents", "metadatas", "distances"],
    )

    ids       = results["ids"][0]
    documents = results["documents"][0]
    distances = results["distances"][0]
    metadatas = results["metadatas"][0]

    print(f"  Query: \"{query}\"")
    print(f"  Top {len(ids)} results:\n")

    top_file   = None
    top_score  = None

    for rank, (doc, dist, meta) in enumerate(zip(documents, distances, metadatas), 1):
        score    = round(1 - dist, 4)
        fp       = meta.get("file_path", "?")
        cname    = meta.get("chunk_name", "?")
        language = meta.get("language", "?")
        lines    = f"{meta.get('start_line','?')}-{meta.get('end_line','?')}"

        if rank == 1:
            top_file  = fp
            top_score = score

        # First 2 lines of the document for context
        doc_preview = "  ".join(doc.splitlines()[:2])[:80]

        print(f"  [{rank}] score={score:.4f}  {fp}  (lines {lines})")
        print(f"       name={cname}  language={language}")
        print(f"       preview: {doc_preview!r}")
        print()

    # Verdict
    print(SEP2)
    if top_file and "embedding_service" in top_file:
        print(f"  ✅ PASS — Top result is from embedding_service: {top_file}")
    else:
        print(f"  ❌ FAIL — Top result is NOT from embedding_service!")
        print(f"            Got: {top_file}  (score={top_score:.4f})")
        print()
        print("  DEBUG INFO:")
        print("  The wrong file ranked #1. Possible causes:")
        print("  1. ChromaDB not re-indexed after chunker fix (run reset_and_reindex.py)")
        print("  2. embedding_service.py chunks missing the 'File: ...' context header")
        print("  3. The file was excluded by file_filter.py (check skip rules)")
        print()
        # Check if embedding_service.py is in the index at all
        es_chunks = [
            m.get("file_path","") for m in metadatas
            if "embedding_service" in m.get("file_path","")
        ]
        if es_chunks:
            print(f"  embedding_service.py IS in top-5 results (rank {metadatas.index(metadatas[next(i for i,m in enumerate(metadatas) if 'embedding_service' in m.get('file_path',''))])+1})")
        else:
            print("  embedding_service.py is NOT in the top-5 results at all.")


# ─────────────────────────────────────────────────────────────────────
# CHECK 4: Language breakdown
# ─────────────────────────────────────────────────────────────────────

def check_language_breakdown(col):
    print()
    print(SEP)
    print("CHECK 4 — Indexed files by language")
    print(SEP)

    total   = col.count()
    result  = col.get(limit=total, include=["metadatas"])
    metas   = result["metadatas"]

    # Count chunks per language
    lang_chunks = Counter(m.get("language", "unknown") for m in metas)

    # Count unique files per language
    files_by_lang: dict[str, set] = {}
    for m in metas:
        lang = m.get("language", "unknown")
        fp   = m.get("file_path", "")
        files_by_lang.setdefault(lang, set()).add(fp)

    print(f"  {'Language':<15} {'Unique Files':>14} {'Chunks':>10}")
    print(f"  {'-'*15} {'-'*14} {'-'*10}")

    python_files = ts_files = other_files = 0
    for lang, count in sorted(lang_chunks.items(), key=lambda x: -x[1]):
        n_files = len(files_by_lang.get(lang, set()))
        marker  = ""
        if lang == "python":
            python_files = n_files
            marker = "  ← Python"
        elif lang in ("typescript", "javascript"):
            ts_files += n_files
            marker = "  ← JS/TS"
        else:
            other_files += n_files
        print(f"  {lang:<15} {n_files:>14,} {count:>10,}{marker}")

    print(f"\n  Python files: {python_files}  |  TypeScript/JS files: {ts_files}  |  Other: {other_files}")
    print()
    print("  ✅ Language breakdown complete")

    # Spot-check: warn if suspicious files got indexed
    bad_langs = {m.get("file_path","") for m in metas
                 if m.get("language","") == "unknown"}
    if bad_langs:
        print(f"\n  ⚠️  {len(bad_langs)} 'unknown' language chunks found:")
        for f in sorted(bad_langs)[:5]:
            print(f"     {f}")


# ─────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║         CodeLens — RAG Pipeline Verification           ║")
    print("╚══════════════════════════════════════════════════════════╝")

    col, col_name = get_collection()

    total = check_chunk_count(col, col_name)
    if total > 0:
        check_sample_chunks(col)
        check_retrieval(col)
        check_language_breakdown(col)

    print(SEP)
    print("  Verification complete.")
    print(SEP)
    print()
